"""
tests/test_grid_index.py

Unit and integration tests for the GridIndex class (narr_data.py).

GridIndex docstring shows two usage patterns:

  Local file:
      grid_index = GridIndex("narr_latlon.h5")
      idx, idy = grid_index.latlon_to_gridyx(lat, lon)

  S3 file:
      grid_index = GridIndex(grid_key, location="S3", bucket=bucket)
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

from mioffset.narr_data import GridIndex

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
    gi.location = "File"
    gi.narr_grid_file = ""
    gi.bucket = ""
    gi._LAT = lats
    gi._LON = lons
    return gi


@pytest.fixture
def grid_index_real():
    """GridIndex loaded from the real narr_latlon.h5 test fixture."""
    return GridIndex(TEST_NARR_GRID_LATLON)


# ---------------------------------------------------------------------------
# TestGridIndexInit — constructor and attribute setup
# ---------------------------------------------------------------------------

class TestGridIndexInit:
    """Test __init__ stores parameters and handles missing data gracefully."""

    def test_default_location_is_file(self):
        # docstring example: GridIndex("narr_latlon.h5") uses File location
        gi = GridIndex("/nonexistent/path.h5")
        assert gi.location == "FILE"

    def test_narr_grid_file_attribute_stored(self):
        gi = GridIndex("/nonexistent/path.h5")
        assert gi.narr_grid_file == "/nonexistent/path.h5"

    def test_bucket_attribute_stored(self):
        gi = GridIndex("/nonexistent/path.h5", bucket="my-bucket")
        assert gi.bucket == "my-bucket"

    def test_location_attribute_stored_s3(self):
        gi = GridIndex("some/s3/key.h5", location="S3", bucket="")
        assert gi.location == "S3"

    def test_missing_local_file_leaves_lat_lon_none(self):
        # load_grid_file logs a warning rather than raising when the file
        # is not found, so LAT/LON remain None
        gi = GridIndex("/nonexistent/narr_latlon.h5")
        assert gi.LAT is None
        assert gi.LON is None

    def test_s3_location_without_bucket_leaves_lat_lon_none(self):
        # docstring S3 example: bucket must be supplied; missing bucket is
        # handled gracefully (RuntimeError caught inside load_grid_file)
        gi = GridIndex("some/s3/key.h5", location="S3", bucket="")
        assert gi.LAT is None
        assert gi.LON is None


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
        # docstring usage: calling with invalid lat/lon raises ValueError
        with pytest.raises(ValueError):
            grid_index_real.latlon_to_gridyx(0.0, 0.0)

    def test_result_indices_are_non_negative(self, grid_index_real):
        idx, idy = grid_index_real.latlon_to_gridyx(TEST_MI_LAT, TEST_MI_LON)
        assert idx >= 0
        assert idy >= 0


# ---------------------------------------------------------------------------
# TestGridIndexLoadErrors — exception handling during grid file loading
# ---------------------------------------------------------------------------

class TestGridIndexLoadErrors:
    """Correct exceptions are raised for each failure mode when loading the
    lat/lon grid file.  Each test calls the relevant method directly on an
    instance built with __new__ so that the constructor's exception-swallowing
    wrapper does not hide the error."""

    def _file_instance(self, path: str = "/nonexistent/narr_latlon.h5") -> GridIndex:
        """GridIndex wired for File mode, bypassing __init__."""
        gi = GridIndex.__new__(GridIndex)
        gi.location = "File"
        gi.narr_grid_file = path
        gi.bucket = ""
        gi._LAT = None
        gi._LON = None
        return gi

    def _s3_instance(self, bucket: str = "test-bucket", key: str = "narr_latlon.h5") -> GridIndex:
        """GridIndex wired for S3 mode, bypassing __init__."""
        gi = GridIndex.__new__(GridIndex)
        gi.location = "S3"
        gi.narr_grid_file = key
        gi.bucket = bucket
        gi._LAT = None
        gi._LON = None
        return gi

    # 1. source=File, file path does not exist
    def test_file_not_found_raises_runtime_error(self):
        gi = self._file_instance("/nonexistent/narr_latlon.h5")
        with pytest.raises(RuntimeError, match="not found"):
            gi.read_narr_grid_file_hdf5()

    # 2. source=S3, bucket not set
    def test_s3_no_bucket_raises_runtime_error(self):
        gi = self._s3_instance(bucket="")
        with pytest.raises(RuntimeError, match="bucket"):
            gi.read_narr_lat_lon_s3()

    # 3. source=S3, S3 client cannot be created (e.g. missing credentials)
    def test_s3_client_creation_failure_raises_runtime_error(self):
        gi = self._s3_instance(bucket="test-bucket")
        with patch("mioffset.narr_data.get_s3_client", side_effect=Exception("No credentials")):
            with pytest.raises(RuntimeError, match="S3 client initialization failed"):
                gi.read_narr_lat_lon_s3()

    # 4. source=S3, bucket set but key (file) not found in the bucket
    def test_s3_key_not_found_raises_client_error(self):
        gi = self._s3_instance(bucket="test-bucket", key="missing/key.h5")
        mock_s3 = MagicMock()
        mock_s3.download_file.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}}, "download_file"
        )
        with patch("mioffset.narr_data.get_s3_client", return_value=mock_s3):
            with pytest.raises(ClientError):
                gi.read_narr_lat_lon_s3()
