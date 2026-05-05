"""
tests/test_narr_data_json.py

Unit and integration tests for the WindData class (narr_data.py),
focused on JSON-based data access via FILE and S3 locations.

Test structure
--------------
Pure unit tests (always run, no external resources needed):
  - TestWindDataInit           — constructor parameter validation
  - TestWindDataJsonFilename   — narr_data_json_filename helper
  - TestWindDataReadFromFile   — read_dataset_json_from_file using test fixtures
  - TestWindDataReadFromS3     — read_dataset_json_from_s3 with a mocked S3 client
  - TestWindDataPrepForFod     — prep_dataset_for_fod
  - TestWindDataReadTimeseriesFile — read_narr_timeseries_json (FILE, mock GridIndex)

Integration tests (@pytest.mark.integration):
  - TestWindDataReadTimeseriesFileIntegration — needs narr_latlon.h5
  - TestWindDataReadTimeseriesS3Integration   — needs narr_latlon.h5 + AWS creds

Run only fast tests:
    pytest -m "not integration"

Run everything:
    pytest
"""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from botocore.exceptions import ClientError

from mioffset.narr_data import DATASETS, GridIndex, WindData

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

TEST_DATA_DIR = str(Path(__file__).parent / "data")
TEST_NARR_GRID_LATLON = str(Path(TEST_DATA_DIR) / "narr_latlon.h5")

TEST_MI_LAT = 44.0
TEST_MI_LON = -83.0
# Must match the filenames in tests/data/ (pc_232_131.json etc.)
TEST_GRID_X = 232
TEST_GRID_Y = 131
# The test JSON fixtures each have 3 years × 10 values
TEST_YEARS = 3
TEST_VALUES_PER_YEAR = 10
TEST_TOTAL_VALUES = TEST_YEARS * TEST_VALUES_PER_YEAR


def narr_grid_available() -> bool:
    return os.path.exists(TEST_NARR_GRID_LATLON)


def s3_available() -> bool:
    return bool(os.getenv("NARR_BUCKET") and os.getenv("AWS_ACCESS_KEY_ID"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_grid_index():
    """GridIndex mock pre-configured for TEST_MI_LAT/LON → (TEST_GRID_X, TEST_GRID_Y).

    Bypasses all file I/O so tests can focus on WindData behaviour.
    """
    gi = MagicMock(spec=GridIndex)
    gi.is_loaded = True
    gi.validate_latlon.return_value = True
    gi.latlon_to_gridyx.return_value = (TEST_GRID_X, TEST_GRID_Y)
    return gi


@pytest.fixture
def wind_data_file(mock_grid_index):
    """WindData in FILE mode pointing at the test data directory."""
    return WindData(mock_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)


@pytest.fixture
def wind_data_s3(mock_grid_index):
    """WindData in S3 mode with both the grid_index and S3 client mocked.

    The s3_client attribute is a MagicMock so per-test responses can be
    configured via wind_data_s3.s3_client.get_object.return_value = ...
    """
    with patch("mioffset.narr_data.get_s3_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        wd = WindData(mock_grid_index, location="S3", bucket="test-bucket")
    # wd.s3_client is the mock_client; the patch has been removed but the
    # stored reference survives, so tests can configure it freely.
    return wd


@pytest.fixture
def real_grid_index():
    """GridIndex loaded from the real narr_latlon.h5 test fixture."""
    return GridIndex(TEST_NARR_GRID_LATLON)


def _s3_body(data: dict):
    """Return a minimal mock s3.get_object response body for *data*."""
    body = MagicMock()
    body.read.return_value = json.dumps(data).encode()
    return {"Body": body}


# ---------------------------------------------------------------------------
# TestWindDataInit
# ---------------------------------------------------------------------------

class TestWindDataInit:
    """Constructor stores attributes and raises ValueError for bad inputs."""

    def test_valid_file_location_does_not_raise(self, mock_grid_index):
        wd = WindData(mock_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)
        assert wd is not None

    def test_grid_index_stored(self, mock_grid_index):
        wd = WindData(mock_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)
        assert wd.grid_index is mock_grid_index

    def test_narr_data_dir_stored(self, mock_grid_index):
        wd = WindData(mock_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)
        assert wd.narr_data_dir == TEST_DATA_DIR

    def test_location_stored(self, mock_grid_index):
        wd = WindData(mock_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)
        assert wd.location == "FILE"

    def test_invalid_location_raises_value_error(self, mock_grid_index):
        with pytest.raises(ValueError):
            WindData(mock_grid_index, location="DISK", narr_data_dir=TEST_DATA_DIR)

    def test_file_location_with_missing_dir_raises_value_error(self, mock_grid_index):
        with pytest.raises(ValueError):
            WindData(mock_grid_index, location="FILE", narr_data_dir="/nonexistent/data")

    def test_s3_location_stores_bucket(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client"):
            wd = WindData(mock_grid_index, location="S3", bucket="my-bucket")
        assert wd.bucket == "my-bucket"

    def test_s3_location_creates_s3_client(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client") as mock_get:
            mock_get.return_value = MagicMock()
            WindData(mock_grid_index, location="S3", bucket="my-bucket")
        mock_get.assert_called_once()

    def test_s3_location_with_failed_client_raises_value_error(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client", side_effect=Exception("no creds")):
            with pytest.raises(ValueError, match="S3 client"):
                WindData(mock_grid_index, location="S3", bucket="my-bucket")


# ---------------------------------------------------------------------------
# TestWindDataJsonFilename
# ---------------------------------------------------------------------------

class TestWindDataJsonFilename:
    """narr_data_json_filename returns a correctly formatted relative path."""

    def test_lowercase_dataset(self, wind_data_file):
        assert wind_data_file.narr_data_json_filename("PC", 12, 34) == "pc/pc_012_034.json"

    def test_zero_padded_single_digit(self, wind_data_file):
        assert wind_data_file.narr_data_json_filename("ws", 1, 5) == "ws/ws_001_005.json"

    def test_three_digit_indices(self, wind_data_file):
        assert wind_data_file.narr_data_json_filename("WD", 100, 200) == "wd/wd_100_200.json"

    def test_returns_string(self, wind_data_file):
        assert isinstance(wind_data_file.narr_data_json_filename("pc", 0, 0), str)

    def test_known_grid_point(self, wind_data_file):
        """Must match the actual test fixture filenames in tests/data/."""
        assert wind_data_file.narr_data_json_filename(
            "pc", TEST_GRID_X, TEST_GRID_Y
        ) == f"pc/pc_{TEST_GRID_X:03}_{TEST_GRID_Y:03}.json"


# ---------------------------------------------------------------------------
# TestWindDataReadFromFile
# ---------------------------------------------------------------------------

class TestWindDataReadFromFile:
    """read_dataset_json_from_file reads from the per-dataset JSON fixture files."""

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_returns_dict(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json_from_file(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert isinstance(result, dict)

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_year_keys_are_digit_strings(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json_from_file(TEST_GRID_X, TEST_GRID_Y, dataset)
        for key in result:
            assert str(key).isdigit(), f"Key {key!r} is not a year string"

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_values_are_non_empty_lists(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json_from_file(TEST_GRID_X, TEST_GRID_Y, dataset)
        for yr, values in result.items():
            assert isinstance(values, list)
            assert len(values) > 0, f"{dataset}[{yr}] is empty"

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_expected_years(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json_from_file(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert len(result) == TEST_YEARS

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_expected_values_per_year(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json_from_file(TEST_GRID_X, TEST_GRID_Y, dataset)
        for yr, values in result.items():
            assert len(values) == TEST_VALUES_PER_YEAR, (
                f"{dataset}[{yr}] has {len(values)} values, expected {TEST_VALUES_PER_YEAR}"
            )

    def test_missing_grid_point_raises(self, wind_data_file):
        """A grid coordinate with no matching file should raise an error."""
        with pytest.raises(Exception):
            wind_data_file.read_dataset_json_from_file(0, 0, "pc")

    def test_reads_from_temp_dir(self, mock_grid_index):
        """WindData respects narr_data_dir — data is read from the right location."""
        payload = {"1979": [1.0, 2.0], "1980": [3.0, 4.0]}
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "pc", "pc_005_010.json")
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "w") as fh:
                json.dump(payload, fh)

            wd = WindData(mock_grid_index, location="FILE", narr_data_dir=tmpdir)
            result = wd.read_dataset_json_from_file(5, 10, "pc")

        assert result == payload


# ---------------------------------------------------------------------------
# TestWindDataReadFromS3
# ---------------------------------------------------------------------------

class TestWindDataReadFromS3:
    """read_dataset_json_from_s3 delegates to self.s3_client.get_object."""

    def test_returns_year_keyed_dict(self, wind_data_s3):
        expected = {"1979": [1.0, 2.0, 3.0], "1980": [4.0, 5.0]}
        wind_data_s3.s3_client.get_object.return_value = _s3_body(expected)
        result = wind_data_s3.read_dataset_json_from_s3(TEST_GRID_X, TEST_GRID_Y, "pc")
        assert result == expected

    def test_calls_correct_bucket_and_key(self, wind_data_s3):
        expected_key = f"pc/pc_{TEST_GRID_X:03}_{TEST_GRID_Y:03}.json"
        wind_data_s3.s3_client.get_object.return_value = _s3_body({"1979": []})
        wind_data_s3.read_dataset_json_from_s3(TEST_GRID_X, TEST_GRID_Y, "pc")
        wind_data_s3.s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key=expected_key
        )

    def test_s3_error_returns_none(self, wind_data_s3):
        """A ClientError from S3 (e.g. key not found) returns None rather than raising."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )
        result = wind_data_s3.read_dataset_json_from_s3(TEST_GRID_X, TEST_GRID_Y, "pc")
        assert result is None

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_all_datasets_can_be_fetched(self, wind_data_s3, dataset):
        payload = {"1979": [1.0, 2.0]}
        wind_data_s3.s3_client.get_object.return_value = _s3_body(payload)
        result = wind_data_s3.read_dataset_json_from_s3(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# TestWindDataPrepForFod
# ---------------------------------------------------------------------------

class TestWindDataPrepForFod:
    """prep_dataset_for_fod flattens a year-keyed dict into a single ndarray."""

    def test_returns_ndarray(self, wind_data_file):
        data = {"1979": [1.0, 2.0, 3.0], "1980": [4.0, 5.0, 6.0]}
        result = wind_data_file.prep_dataset_for_fod(data)
        assert isinstance(result, np.ndarray)

    def test_concatenates_all_values(self, wind_data_file):
        data = {"1979": [1.0, 2.0, 3.0], "1980": [4.0, 5.0, 6.0]}
        result = wind_data_file.prep_dataset_for_fod(data)
        assert len(result) == 6

    def test_single_year_values_preserved(self, wind_data_file):
        data = {"1979": [10.0, 20.0, 30.0]}
        result = wind_data_file.prep_dataset_for_fod(data)
        np.testing.assert_array_equal(result, np.array([10.0, 20.0, 30.0]))

    def test_values_are_numeric(self, wind_data_file):
        """Result values must be numbers, not year-key strings."""
        data = {"1979": [1.5, 2.5], "1980": [3.5, 4.5]}
        result = wind_data_file.prep_dataset_for_fod(data)
        assert np.issubdtype(result.dtype, np.number), (
            f"Expected numeric dtype, got {result.dtype}. "
            "Check prep_dataset_for_fod list comprehension — inner loop should be "
            "'for item in ts', not 'for item in ts_by_year'."
        )


# ---------------------------------------------------------------------------
# TestWindDataReadTimeseriesFile  (unit — mock GridIndex, reads real fixtures)
# ---------------------------------------------------------------------------

class TestWindDataReadTimeseriesFile:
    """Unit tests for read_narr_timeseries_json in FILE mode.

    Uses a mock GridIndex that returns (TEST_GRID_X, TEST_GRID_Y) so the real
    JSON fixtures in tests/data/ are exercised without needing narr_latlon.h5.
    """

    def test_returns_dict(self, wind_data_file):
        result = wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert isinstance(result, dict)

    def test_returns_all_datasets(self, wind_data_file):
        result = wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert set(result.keys()) == set(DATASETS)

    def test_values_are_ndarrays(self, wind_data_file):
        result = wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert isinstance(result[ds], np.ndarray), f"{ds} should be an ndarray"

    def test_all_datasets_same_length(self, wind_data_file):
        result = wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        lengths = {ds: len(result[ds]) for ds in DATASETS}
        assert len(set(lengths.values())) == 1, f"Dataset lengths differ: {lengths}"

    def test_arrays_are_nonempty(self, wind_data_file):
        result = wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert result[ds].size > 0, f"{ds} array is empty"

    def test_invalid_latlon_returns_empty_dict(self, mock_grid_index):
        """Out-of-bounds coordinates produce an empty dict rather than raising."""
        mock_grid_index.validate_latlon.return_value = False
        wd = WindData(mock_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)
        result = wd.read_narr_timeseries_json(0.0, 0.0)
        assert result == {}

    def test_does_not_call_s3(self, wind_data_file):
        """FILE mode must never touch S3."""
        with patch("mioffset.narr_data.get_s3_client") as mock_get:
            wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# TestWindDataReadTimeseriesS3  (unit — fully mocked S3)
# ---------------------------------------------------------------------------

class TestWindDataReadTimeseriesS3:
    """Unit tests for read_narr_timeseries_json in S3 mode with mocked client."""

    def _mock_all_datasets(self, wind_data_s3, payload: dict):
        """Configure the mock S3 client to return *payload* for every get_object call."""
        wind_data_s3.s3_client.get_object.return_value = _s3_body(payload)

    def test_returns_dict(self, wind_data_s3):
        self._mock_all_datasets(wind_data_s3, {"1979": [1.0, 2.0]})
        result = wind_data_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert isinstance(result, dict)

    def test_returns_all_datasets(self, wind_data_s3):
        self._mock_all_datasets(wind_data_s3, {"1979": [1.0, 2.0]})
        result = wind_data_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert set(result.keys()) == set(DATASETS)

    def test_s3_fetched_once_per_dataset(self, wind_data_s3):
        self._mock_all_datasets(wind_data_s3, {"1979": [1.0]})
        wind_data_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert wind_data_s3.s3_client.get_object.call_count == len(DATASETS)


# ---------------------------------------------------------------------------
# TestWindDataReadTimeseriesFileIntegration
# (integration — requires narr_latlon.h5 to resolve lat/lon)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(not narr_grid_available(), reason="NARR grid test file not found")
class TestWindDataReadTimeseriesFileIntegration:
    """Integration tests that use the real narr_latlon.h5 to convert lat/lon to
    grid indices, then read from the JSON test fixtures in tests/data/."""

    @pytest.fixture
    def wind_data(self, real_grid_index):
        return WindData(real_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)

    def test_returns_all_datasets(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert set(result.keys()) == set(DATASETS)

    def test_values_are_ndarrays(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert isinstance(result[ds], np.ndarray)

    def test_arrays_are_nonempty(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert result[ds].size > 0

    def test_all_datasets_same_length(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        sizes = {ds: result[ds].size for ds in DATASETS}
        assert len(set(sizes.values())) == 1, f"Dataset sizes differ: {sizes}"

    def test_out_of_bounds_lat_lon_returns_empty(self, wind_data):
        result = wind_data.read_narr_timeseries_json(0.0, 0.0)
        assert result == {}


# ---------------------------------------------------------------------------
# TestWindDataReadTimeseriesS3Integration
# (integration — requires narr_latlon.h5 + AWS credentials + NARR_BUCKET)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.skipif(
    not (s3_available() and narr_grid_available()),
    reason="AWS credentials, NARR_BUCKET, and narr_latlon.h5 are all required",
)
class TestWindDataReadTimeseriesS3Integration:
    """Integration tests that read real data from S3."""

    @pytest.fixture
    def wind_data(self, real_grid_index):
        bucket = os.getenv("NARR_BUCKET", "")
        return WindData(real_grid_index, location="S3", bucket=bucket)

    def test_returns_all_datasets(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert set(result.keys()) == set(DATASETS)

    def test_values_are_ndarrays(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert isinstance(result[ds], np.ndarray)

    def test_arrays_are_nonempty(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert result[ds].size > 0

    def test_all_datasets_same_length(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        sizes = {ds: result[ds].size for ds in DATASETS}
        assert len(set(sizes.values())) == 1, f"Dataset sizes differ: {sizes}"
