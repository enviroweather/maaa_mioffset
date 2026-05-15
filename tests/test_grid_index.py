"""
tests/test_grid_index.py

Unit and integration tests for GridIndex (local file) and GridIndexS3 (S3)
classes from narr_data.py.

Usage patterns:

  Local file:
      grid_index = GridIndex("narr_latlon.h5")
      idx, idy = grid_index.latlon_to_gridyx(lat, lon)

  S3 file:
      grid_index = GridIndexS3(grid_key, bucket=bucket)
      idx, idy = grid_index.latlon_to_gridyx(lat, lon)

Tests are split into two groups:
  - Pure / in-process: always run, no external resources needed.
  - Integration (@pytest.mark.integration): require the real narr_latlon.h5
    test fixture. Skipped automatically when the file is absent.

Run only fast tests:
    pytest -m "not integration"

Run everything:
    pytest
"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from botocore.exceptions import ClientError

from mioffset.narr_data import GridIndex, GridIndexS3

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TEST_DATA_DIR = str(Path(__file__).parent / "data")
TEST_NARR_GRID_LATLON = str(Path(TEST_DATA_DIR) / "narr_latlon.h5")

# Representative Michigan location and its expected NARR grid indices
TEST_MI_LAT = 44.0
TEST_MI_LON = -83.0
TEST_GRID_X = 232
TEST_GRID_Y = 131


def narr_grid_available() -> bool:
    return os.path.exists(TEST_NARR_GRID_LATLON)


def narr_s3_available() -> bool:
    """Return True when AWS credentials and NARR S3 env vars are all present.

    Loads the .env file (via get_aws_config) so the check works whether or not
    the variables were already exported to the shell.
    """
    from mioffset.aws import get_aws_config
    try:
        get_aws_config()  # raises ValueError when credentials are missing
    except Exception:
        return False
    bucket = os.getenv("NARR_BUCKET", "")
    key = os.getenv("NARR_GRID_LATLON_S3", "")
    return bool(bucket and key)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def small_lat_lon_arrays():
    """3×3 NumPy grid centred on a Michigan point, for in-process tests."""
    lats = np.array([[43.0, 43.0, 43.0],
                     [44.0, 44.0, 44.0],
                     [45.0, 45.0, 45.0]])
    lons = np.array([[-84.0, -83.0, -82.0],
                     [-84.0, -83.0, -82.0],
                     [-84.0, -83.0, -82.0]])
    return lats, lons


@pytest.fixture
def grid_index_small(small_lat_lon_arrays):
    """GridIndex whose LAT/LON are injected directly from the small grid,
    bypassing all file I/O. Used for pure in-process unit tests."""
    lats, lons = small_lat_lon_arrays
    gi = GridIndex.__new__(GridIndex)
    gi.narr_grid_file = ""
    gi._LAT = lats
    gi._LON = lons
    return gi


@pytest.fixture
def grid_index_real():
    """GridIndex loaded from the real narr_latlon.h5 test fixture."""
    return GridIndex(TEST_NARR_GRID_LATLON)


@pytest.fixture(scope="module")
def grid_index_s3_real():
    """GridIndexS3 loaded from the real S3 bucket using .env config.

    Reuses a single connection across all tests in this module.
    Only used by test classes guarded by narr_s3_available().
    """
    from mioffset.aws import get_aws_config
    get_aws_config()          # ensures .env is loaded
    bucket = os.getenv("NARR_BUCKET", "")
    key = os.getenv("NARR_GRID_LATLON_S3", "")
    return GridIndexS3(key, bucket=bucket)


# ---------------------------------------------------------------------------
# TestGridIndexInit — GridIndex (local file) constructor and attribute setup
# ---------------------------------------------------------------------------

class TestGridIndexInit:
    """Test GridIndex __init__ stores parameters and handles missing data gracefully."""

    def test_location_is_file(self):
        gi = GridIndex("/nonexistent/path.h5")
        assert gi.location == "FILE"

    def test_narr_grid_file_attribute_stored(self):
        gi = GridIndex("/nonexistent/path.h5")
        assert gi.narr_grid_file == "/nonexistent/path.h5"

    def test_missing_local_file_leaves_lat_lon_none(self):
        # load_grid_file logs a warning rather than raising when the file
        # is not found, so LAT/LON remain None
        gi = GridIndex("/nonexistent/narr_latlon.h5")
        assert gi.LAT is None
        assert gi.LON is None

    def test_is_loaded_false_when_file_missing(self):
        gi = GridIndex("/nonexistent/narr_latlon.h5")
        assert gi.is_loaded is False


# ---------------------------------------------------------------------------
# TestGridIndexS3Init — GridIndexS3 constructor and attribute setup
# ---------------------------------------------------------------------------

class TestGridIndexS3Init:
    """Test GridIndexS3 __init__ stores parameters and handles missing data gracefully."""

    def test_location_is_s3(self):
        gi = GridIndexS3("some/s3/key.h5", bucket="my-bucket")
        assert gi.location == "S3"

    def test_narr_grid_file_attribute_stored(self):
        gi = GridIndexS3("some/s3/key.h5", bucket="my-bucket")
        assert gi.narr_grid_file == "some/s3/key.h5"

    def test_bucket_attribute_stored(self):
        gi = GridIndexS3("some/s3/key.h5", bucket="my-bucket")
        assert gi.bucket == "my-bucket"

    def test_missing_bucket_leaves_lat_lon_none(self):
        # bucket is required; when empty GridIndexS3 cannot connect to S3
        gi = GridIndexS3("some/s3/key.h5", bucket="")
        assert gi.LAT is None
        assert gi.LON is None

    def test_is_loaded_false_when_bucket_missing(self):
        gi = GridIndexS3("some/s3/key.h5", bucket="")
        assert gi.is_loaded is False


# ---------------------------------------------------------------------------
# TestGridIndexReadLocalFile — integration: real narr_latlon.h5
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not narr_grid_available(), reason="NARR grid test file not found")
class TestGridIndexReadLocalFile:
    """Load the real lat/lon HDF5 fixture and verify the arrays it produces."""

    def test_lat_loaded_as_ndarray(self, grid_index_real):
        assert isinstance(grid_index_real.LAT, np.ndarray)

    def test_lon_loaded_as_ndarray(self, grid_index_real):
        assert isinstance(grid_index_real.LON, np.ndarray)

    def test_lat_lon_same_shape(self, grid_index_real):
        assert grid_index_real.LAT.shape == grid_index_real.LON.shape

    def test_lat_range_plausible(self, grid_index_real):
        assert grid_index_real.LAT.min() >= 0
        assert grid_index_real.LAT.max() <= 90

    def test_lon_range_plausible(self, grid_index_real):
        # NARR uses negative (west) longitudes
        assert grid_index_real.LON.min() >= -360
        assert grid_index_real.LON.max() <= 0

    def test_is_loaded_true_after_real_file(self, grid_index_real):
        assert grid_index_real.is_loaded is True


# ---------------------------------------------------------------------------
# TestGridIndexValidateLatlon — in-process (no file required)
# ---------------------------------------------------------------------------

class TestGridIndexValidateLatlon:
    """validate_latlon checks whether a point falls inside the loaded grid."""

    def test_valid_centre_point(self, grid_index_small):
        assert grid_index_small.validate_latlon(44.0, -83.0) is True

    def test_lat_below_minimum_returns_false(self, grid_index_small):
        assert grid_index_small.validate_latlon(42.0, -83.0) is False

    def test_lat_above_maximum_returns_false(self, grid_index_small):
        assert grid_index_small.validate_latlon(46.0, -83.0) is False

    def test_lon_below_minimum_returns_false(self, grid_index_small):
        assert grid_index_small.validate_latlon(44.0, -85.0) is False

    def test_lon_above_maximum_returns_false(self, grid_index_small):
        assert grid_index_small.validate_latlon(44.0, -81.0) is False

    def test_boundary_min_returns_true(self, grid_index_small):
        # Grid min corner: lat=43.0, lon=-84.0
        assert grid_index_small.validate_latlon(43.0, -84.0) is True

    def test_boundary_max_returns_true(self, grid_index_small):
        # Grid max corner: lat=45.0, lon=-82.0
        assert grid_index_small.validate_latlon(45.0, -82.0) is True

    def test_returns_bool_type(self, grid_index_small):
        result = grid_index_small.validate_latlon(44.0, -83.0)
        assert isinstance(result, bool)


# ---------------------------------------------------------------------------
# TestGridIndexLatLonToGridyx — integration: real narr_latlon.h5
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not narr_grid_available(), reason="NARR grid test file not found")
class TestGridIndexLatLonToGridyx:
    """latlon_to_gridyx returns the (idx, idy) for a real Michigan location."""

    def test_returns_tuple(self, grid_index_real):
        result = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert isinstance(result, tuple)

    def test_returns_two_values(self, grid_index_real):
        result = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert len(result) == 2

    def test_returns_ints(self, grid_index_real):
        idx, idy = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert isinstance(idx, int)
        assert isinstance(idy, int)

    def test_known_michigan_point_grid_x(self, grid_index_real):
        idx, idy = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idx == TEST_GRID_X

    def test_known_michigan_point_grid_y(self, grid_index_real):
        idx, idy = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idy == TEST_GRID_Y

    def test_out_of_bounds_raises_value_error(self, grid_index_real):
        with pytest.raises(ValueError):
            grid_index_real.latlon_to_gridyx(0.0, 0.0)

    def test_result_indices_are_non_negative(self, grid_index_real):
        idx, idy = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idx >= 0
        assert idy >= 0


# ---------------------------------------------------------------------------
# TestGridIndexLoadErrors — exception handling for GridIndex (local file)
# ---------------------------------------------------------------------------

class TestGridIndexLoadErrors:
    """Correct exceptions are raised when loading from a local file path.
    Tests call the private read method directly on an instance built with
    __new__ so that the constructor's exception-swallowing wrapper does not
    hide the error."""

    def _file_instance(self, path: str = "/nonexistent/narr_latlon.h5") -> GridIndex:
        """GridIndex built with __new__, bypassing __init__."""
        gi = GridIndex.__new__(GridIndex)
        gi.narr_grid_file = path
        gi._LAT = None
        gi._LON = None
        return gi

    def test_file_not_found_raises_runtime_error(self):
        gi = self._file_instance("/nonexistent/narr_latlon.h5")
        with pytest.raises(RuntimeError, match="not found"):
            gi._read_narr_grid_file_hdf5()


# ---------------------------------------------------------------------------
# TestGridIndexS3LoadErrors — exception handling for GridIndexS3
# ---------------------------------------------------------------------------

class TestGridIndexS3LoadErrors:
    """Correct exceptions are raised for each S3 failure mode.
    Tests call the private S3 read method directly on an instance built with
    __new__ to bypass the constructor's exception-swallowing wrapper."""

    def _s3_instance(self, bucket: str = "test-bucket", key: str = "narr_latlon.h5") -> GridIndexS3:
        """GridIndexS3 built with __new__, bypassing __init__."""
        gi = GridIndexS3.__new__(GridIndexS3)
        gi.narr_grid_file = key
        gi.bucket = bucket
        gi.s3_client = None
        gi._LAT = None
        gi._LON = None
        return gi

    def test_no_bucket_raises_runtime_error(self):
        gi = self._s3_instance(bucket="")
        with pytest.raises(RuntimeError, match="bucket"):
            gi._read_narr_grid_file_s3()

    def test_s3_client_creation_failure_raises_runtime_error(self):
        gi = self._s3_instance(bucket="test-bucket")
        with patch("mioffset.narr_data.get_s3_client", side_effect=Exception("No credentials")):
            with pytest.raises(RuntimeError, match="S3 client initialization failed"):
                gi._read_narr_grid_file_s3()

    def test_s3_key_not_found_raises_runtime_error(self):
        # The S3 reader wraps all download failures (including ClientError)
        # in RuntimeError
        gi = self._s3_instance(bucket="test-bucket", key="missing/key.h5")
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "download_file"
        )
        gi.s3_client = mock_s3
        with pytest.raises(RuntimeError):
            gi._read_narr_grid_file_s3()

    def test_bad_bucket_raises_runtime_error_with_code(self):
        """NoSuchBucket ClientError is wrapped in RuntimeError with the error code."""
        gi = self._s3_instance(bucket="nonexistent-bucket-xyz")
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "download_file",
        )
        gi.s3_client = mock_s3
        with pytest.raises(RuntimeError, match="NoSuchBucket"):
            gi._read_narr_grid_file_s3()

    def test_bad_credentials_raises_runtime_error_with_code(self):
        """Auth ClientError is wrapped in RuntimeError with the error code."""
        gi = self._s3_instance()
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {
                "Code": "InvalidClientTokenId",
                "Message": "The security token included in the request is invalid",
            }},
            "download_file",
        )
        gi.s3_client = mock_s3
        with pytest.raises(RuntimeError, match="InvalidClientTokenId"):
            gi._read_narr_grid_file_s3()


# ---------------------------------------------------------------------------
# TestGridIndexS3LoadErrorMessages — _load_error attribute and _check_loaded
# ---------------------------------------------------------------------------

class TestGridIndexS3LoadErrorMessages:
    """Failed S3 loads store the reason in _load_error and propagate it via
    _check_loaded so callers get a useful diagnostic instead of a generic message."""

    def _s3_instance(self, bucket: str = "test-bucket", key: str = "narr_latlon.h5") -> GridIndexS3:
        """GridIndexS3 built with __new__, bypassing __init__ but fully initialised."""
        gi = GridIndexS3.__new__(GridIndexS3)
        gi.narr_grid_file = key
        gi.bucket = bucket
        gi.s3_client = None
        gi._LAT = None
        gi._LON = None
        gi._load_error = None
        gi._grid_reader = gi._read_narr_grid_file_s3
        return gi

    def test_missing_bucket_stores_load_error(self):
        """Empty bucket → _load_error is set after _load_grid_file."""
        gi = self._s3_instance(bucket="")
        gi._load_grid_file()
        assert gi._load_error is not None

    def test_missing_bucket_load_error_mentions_bucket(self):
        gi = self._s3_instance(bucket="")
        gi._load_grid_file()
        assert "bucket" in gi._load_error.lower()

    def test_bad_bucket_stores_load_error(self):
        """NoSuchBucket error is captured in _load_error."""
        gi = self._s3_instance(bucket="nonexistent-bucket-xyz")
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "download_file",
        )
        gi.s3_client = mock_s3
        gi._load_grid_file()
        assert gi._load_error is not None
        assert "NoSuchBucket" in gi._load_error

    def test_bad_credentials_stores_load_error(self):
        """Auth error is captured in _load_error."""
        gi = self._s3_instance()
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {
                "Code": "InvalidClientTokenId",
                "Message": "The security token is invalid",
            }},
            "download_file",
        )
        gi.s3_client = mock_s3
        gi._load_grid_file()
        assert gi._load_error is not None
        assert "InvalidClientTokenId" in gi._load_error

    def test_check_loaded_includes_reason_keyword(self):
        """RuntimeError from _check_loaded contains the word 'Reason'."""
        gi = self._s3_instance(bucket="")
        gi._load_grid_file()
        with pytest.raises(RuntimeError, match="[Rr]eason"):
            gi._check_loaded()

    def test_check_loaded_message_includes_load_error_detail(self):
        """RuntimeError from _check_loaded embeds the stored _load_error text."""
        gi = self._s3_instance()
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "does not exist"}},
            "download_file",
        )
        gi.s3_client = mock_s3
        gi._load_grid_file()
        with pytest.raises(RuntimeError, match="NoSuchBucket"):
            gi._check_loaded()

    def test_no_load_error_after_successful_load(self, grid_index_real):
        """_load_error stays None when file loads successfully."""
        assert grid_index_real._load_error is None


# ---------------------------------------------------------------------------
# TestGridIndexS3ReadS3 — integration: live S3 bucket
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.s3
@pytest.mark.skipif(not narr_s3_available(), reason="AWS credentials or NARR S3 config not available")
class TestGridIndexS3ReadS3:
    """Load the real lat/lon HDF5 from S3 and verify the arrays it produces.

    Requires NARR_BUCKET, NARR_GRID_LATLON_S3, AWS_ACCESS_KEY_ID, and
    AWS_SECRET_ACCESS_KEY to be set (typically via .env).
    """

    def test_is_loaded_after_s3_read(self, grid_index_s3_real):
        assert grid_index_s3_real.is_loaded is True

    def test_lat_loaded_as_ndarray(self, grid_index_s3_real):
        assert isinstance(grid_index_s3_real.LAT, np.ndarray)

    def test_lon_loaded_as_ndarray(self, grid_index_s3_real):
        assert isinstance(grid_index_s3_real.LON, np.ndarray)

    def test_lat_lon_same_shape(self, grid_index_s3_real):
        assert grid_index_s3_real.LAT.shape == grid_index_s3_real.LON.shape

    def test_lat_range_plausible(self, grid_index_s3_real):
        assert grid_index_s3_real.LAT.min() >= 0
        assert grid_index_s3_real.LAT.max() <= 90

    def test_lon_range_plausible(self, grid_index_s3_real):
        # NARR uses negative (west) longitudes
        assert grid_index_s3_real.LON.min() >= -360
        assert grid_index_s3_real.LON.max() <= 0


# ---------------------------------------------------------------------------
# TestGridIndexS3LatLonToGridyx — integration: live S3 bucket
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.s3
@pytest.mark.skipif(not narr_s3_available(), reason="AWS credentials or NARR S3 config not available")
class TestGridIndexS3LatLonToGridyx:
    """latlon_to_gridyx returns correct (idx, idy) when the grid was loaded from S3."""

    def test_returns_tuple(self, grid_index_s3_real):
        result = grid_index_s3_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert isinstance(result, tuple)

    def test_returns_two_values(self, grid_index_s3_real):
        result = grid_index_s3_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert len(result) == 2

    def test_returns_ints(self, grid_index_s3_real):
        idx, idy = grid_index_s3_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert isinstance(idx, int)
        assert isinstance(idy, int)

    def test_known_michigan_point_grid_x(self, grid_index_s3_real):
        idx, idy = grid_index_s3_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idx == TEST_GRID_X

    def test_known_michigan_point_grid_y(self, grid_index_s3_real):
        idx, idy = grid_index_s3_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idy == TEST_GRID_Y

    def test_out_of_bounds_raises_value_error(self, grid_index_s3_real):
        with pytest.raises(ValueError):
            grid_index_s3_real.latlon_to_gridyx(0.0, 0.0)

    def test_result_indices_are_non_negative(self, grid_index_s3_real):
        idx, idy = grid_index_s3_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idx >= 0
        assert idy >= 0
