"""
tests/test_narr_data_json.py

Unit and integration tests for the WindData (local file) and WindDataS3 (S3)
classes from narr_data.py, focused on JSON-based data access.

Test structure
--------------
Pure unit tests (always run, no external resources needed):
  - TestWindDataInit           — WindData constructor validation
  - TestWindDataS3Init         — WindDataS3 constructor validation
  - TestWindDataJsonFilename   — narr_data_json_filename helper
  - TestWindDataReadDatasetJson     — WindData.read_dataset_json (file fixtures)
  - TestWindDataS3ReadDatasetJson   — WindDataS3.read_dataset_json (mocked S3)
  - TestWindDataPrepForFod          — prep_dataset_for_fod
  - TestWindDataReadTimeseriesFile  — read_narr_timeseries_json (mock GridIndex)
  - TestWindDataS3ReadTimeseries    — read_narr_timeseries_json (mocked S3)

Integration tests (@pytest.mark.integration):
  - TestWindDataReadTimeseriesFileIntegration — needs narr_latlon.h5
  - TestWindDataS3Integration                 — needs narr_latlon.h5 + AWS creds

Run only fast tests:
    pytest -m "not integration"

Run everything (including live S3):
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

from mioffset.narr_data import DATASETS, GridIndex, WindData, WindDataS3
from mioffset.aws import get_aws_config, get_s3_client

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
# The test JSON fixtures each have 30 years (1979–2008) × 2920 values
TEST_YEARS = 30
TEST_VALUES_PER_YEAR = 2920
TEST_TOTAL_VALUES = TEST_YEARS * TEST_VALUES_PER_YEAR


def narr_grid_available() -> bool:
    return os.path.exists(TEST_NARR_GRID_LATLON)


def aws_fully_configured() -> bool:
    """Return True only when get_aws_config() succeeds AND NARR_BUCKET is set."""
    try:
        get_aws_config()
    except (ValueError, Exception):
        return False
    return bool(os.getenv("NARR_BUCKET"))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_grid_index():
    """GridIndex mock pre-configured for TEST_MI_LAT/LON → (TEST_GRID_X, TEST_GRID_Y)."""
    gi = MagicMock(spec=GridIndex)
    gi.is_loaded = True
    gi.validate_latlon.return_value = True
    gi.latlon_to_gridyx.return_value = (TEST_GRID_X, TEST_GRID_Y)
    return gi


@pytest.fixture
def wind_data_file(mock_grid_index):
    """WindData (local file mode) pointing at the test data directory."""
    return WindData(mock_grid_index, narr_data_dir=TEST_DATA_DIR)


@pytest.fixture
def wind_data_s3(mock_grid_index):
    """WindDataS3 with a mocked S3 client for unit tests.

    The s3_client attribute is a MagicMock so per-test responses can be
    configured via wind_data_s3.s3_client.get_object.return_value = ...
    """
    with patch("mioffset.narr_data.get_s3_client") as mock_get_client:
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        wd = WindDataS3(mock_grid_index, bucket="test-bucket", narr_data_dir=TEST_DATA_DIR)
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
# TestWindDataInit — WindData (local file) constructor
# ---------------------------------------------------------------------------

class TestWindDataInit:
    """Constructor stores attributes and raises ValueError for bad inputs."""

    def test_valid_construction_does_not_raise(self, mock_grid_index):
        wd = WindData(mock_grid_index, narr_data_dir=TEST_DATA_DIR)
        assert wd is not None

    def test_grid_index_stored(self, mock_grid_index):
        wd = WindData(mock_grid_index, narr_data_dir=TEST_DATA_DIR)
        assert wd.grid_index is mock_grid_index

    def test_narr_data_dir_stored(self, mock_grid_index):
        wd = WindData(mock_grid_index, narr_data_dir=TEST_DATA_DIR)
        assert wd.narr_data_dir == TEST_DATA_DIR

    def test_location_is_file(self, mock_grid_index):
        wd = WindData(mock_grid_index, narr_data_dir=TEST_DATA_DIR)
        assert wd.location == "FILE"

    def test_missing_dir_raises_value_error(self, mock_grid_index):
        with pytest.raises(ValueError):
            WindData(mock_grid_index, narr_data_dir="/nonexistent/data")


# ---------------------------------------------------------------------------
# TestWindDataS3Init — WindDataS3 constructor
# ---------------------------------------------------------------------------

class TestWindDataS3Init:
    """WindDataS3 constructor stores attributes and handles failures gracefully."""

    def test_location_is_s3(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client"):
            wd = WindDataS3(mock_grid_index, bucket="my-bucket", narr_data_dir=TEST_DATA_DIR)
        assert wd.location == "S3"

    def test_bucket_stored(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client"):
            wd = WindDataS3(mock_grid_index, bucket="my-bucket", narr_data_dir=TEST_DATA_DIR)
        assert wd.bucket == "my-bucket"

    def test_grid_index_stored(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client"):
            wd = WindDataS3(mock_grid_index, bucket="my-bucket", narr_data_dir=TEST_DATA_DIR)
        assert wd.grid_index is mock_grid_index

    def test_s3_client_created(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client") as mock_get:
            mock_get.return_value = MagicMock()
            WindDataS3(mock_grid_index, bucket="my-bucket", narr_data_dir=TEST_DATA_DIR)
        mock_get.assert_called_once()

    def test_failed_s3_client_raises_value_error(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client", side_effect=Exception("no creds")):
            with pytest.raises(ValueError, match="S3 client"):
                WindDataS3(mock_grid_index, bucket="my-bucket", narr_data_dir=TEST_DATA_DIR)

    def test_missing_dir_raises_value_error(self, mock_grid_index):
        with patch("mioffset.narr_data.get_s3_client"):
            with pytest.raises(ValueError):
                WindDataS3(mock_grid_index, bucket="my-bucket", narr_data_dir="/nonexistent")


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
# TestWindDataReadDatasetJson — WindData.read_dataset_json (local file)
# ---------------------------------------------------------------------------

class TestWindDataReadDatasetJson:
    """WindData.read_dataset_json reads from per-dataset JSON fixture files."""

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_returns_dict(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert isinstance(result, dict)

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_year_keys_are_digit_strings(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        for key in result:
            assert str(key).isdigit(), f"Key {key!r} is not a year string"

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_values_are_non_empty_lists(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        for yr, values in result.items():
            assert isinstance(values, list)
            assert len(values) > 0, f"{dataset}[{yr}] is empty"

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_expected_years(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert len(result) == TEST_YEARS

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_expected_values_per_year(self, wind_data_file, dataset):
        result = wind_data_file.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        for yr, values in result.items():
            assert len(values) == TEST_VALUES_PER_YEAR, (
                f"{dataset}[{yr}] has {len(values)} values, expected {TEST_VALUES_PER_YEAR}"
            )

    def test_missing_grid_point_returns_empty_dict(self, wind_data_file):
        """A grid coordinate with no matching file returns {} rather than raising."""
        result = wind_data_file.read_dataset_json(0, 0, "pc")
        assert result == {}

    def test_reads_from_narr_data_dir(self, mock_grid_index):
        """WindData respects narr_data_dir — data is read from the right location."""
        payload = {"1979": [1.0, 2.0], "1980": [3.0, 4.0]}
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "pc", "pc_005_010.json")
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, "w") as fh:
                json.dump(payload, fh)

            wd = WindData(mock_grid_index, narr_data_dir=tmpdir)
            result = wd.read_dataset_json(5, 10, "pc")

        assert result == payload


# ---------------------------------------------------------------------------
# TestWindDataS3ReadDatasetJson — WindDataS3.read_dataset_json (mocked S3)
# ---------------------------------------------------------------------------

class TestWindDataS3ReadDatasetJson:
    """WindDataS3.read_dataset_json delegates to self.s3_client.get_object."""

    def test_returns_year_keyed_dict(self, wind_data_s3):
        expected = {"1979": [1.0, 2.0, 3.0], "1980": [4.0, 5.0]}
        wind_data_s3.s3_client.get_object.return_value = _s3_body(expected)
        result = wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")
        assert result == expected

    def test_calls_correct_bucket_and_key(self, wind_data_s3):
        expected_key = f"pc/pc_{TEST_GRID_X:03}_{TEST_GRID_Y:03}.json"
        wind_data_s3.s3_client.get_object.return_value = _s3_body({"1979": []})
        wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")
        wind_data_s3.s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket", Key=expected_key
        )

    def test_s3_error_returns_empty_dict(self, wind_data_s3):
        """A ClientError from S3 (e.g. key not found) returns {} rather than raising."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "Not Found"}}, "GetObject"
        )
        result = wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")
        assert result == {}

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_all_datasets_can_be_fetched(self, wind_data_s3, dataset):
        payload = {"1979": [1.0, 2.0]}
        wind_data_s3.s3_client.get_object.return_value = _s3_body(payload)
        result = wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert isinstance(result, dict)

    def test_bad_bucket_raises_value_error(self, wind_data_s3):
        """A NoSuchBucket ClientError raises ValueError — it is a configuration error."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "GetObject",
        )
        with pytest.raises(ValueError, match="[Bb]ucket"):
            wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")

    def test_bad_bucket_error_mentions_bucket_name(self, wind_data_s3):
        """ValueError message includes the bucket name to aid diagnosis."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchBucket", "Message": "The bucket does not exist"}},
            "GetObject",
        )
        with pytest.raises(ValueError) as exc_info:
            wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")
        assert "test-bucket" in str(exc_info.value)

    def test_bad_credentials_raises_value_error(self, wind_data_s3):
        """An InvalidClientTokenId ClientError raises ValueError — bad AWS credentials."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {
                "Code": "InvalidClientTokenId",
                "Message": "The security token included in the request is invalid",
            }},
            "GetObject",
        )
        with pytest.raises(ValueError, match="[Cc]redentials"):
            wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")

    def test_access_denied_raises_value_error(self, wind_data_s3):
        """AccessDenied (e.g. wrong secret key) also raises ValueError."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access Denied"}},
            "GetObject",
        )
        with pytest.raises(ValueError):
            wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")

    def test_no_such_key_returns_empty_dict(self, wind_data_s3):
        """A NoSuchKey error (missing data file) returns {} rather than raising."""
        wind_data_s3.s3_client.get_object.side_effect = ClientError(
            {"Error": {"Code": "NoSuchKey", "Message": "The key does not exist"}},
            "GetObject",
        )
        result = wind_data_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, "pc")
        assert result == {}


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
        data = {"1979": [1.5, 2.5], "1980": [3.5, 4.5]}
        result = wind_data_file.prep_dataset_for_fod(data)
        assert np.issubdtype(result.dtype, np.number), (
            f"Expected numeric dtype, got {result.dtype}."
        )


# ---------------------------------------------------------------------------
# TestWindDataReadTimeseriesFile  (unit — mock GridIndex, reads real fixtures)
# ---------------------------------------------------------------------------

class TestWindDataReadTimeseriesFile:
    """Unit tests for WindData.read_narr_timeseries_json (file mode).

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
        wd = WindData(mock_grid_index, narr_data_dir=TEST_DATA_DIR)
        result = wd.read_narr_timeseries_json(0.0, 0.0)
        assert result == {}

    def test_does_not_call_s3(self, wind_data_file):
        """FILE mode must never touch S3."""
        with patch("mioffset.narr_data.get_s3_client") as mock_get:
            wind_data_file.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# TestWindDataS3ReadTimeseries  (unit — fully mocked S3)
# ---------------------------------------------------------------------------

class TestWindDataS3ReadTimeseries:
    """Unit tests for WindDataS3.read_narr_timeseries_json with mocked client."""

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

    def test_invalid_latlon_returns_empty_dict(self, mock_grid_index):
        mock_grid_index.validate_latlon.return_value = False
        with patch("mioffset.narr_data.get_s3_client"):
            wd = WindDataS3(mock_grid_index, bucket="test-bucket", narr_data_dir=TEST_DATA_DIR)
        result = wd.read_narr_timeseries_json(0.0, 0.0)
        assert result == {}


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
        return WindData(real_grid_index, narr_data_dir=TEST_DATA_DIR)

    def test_returns_all_datasets(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert set(result.keys()) == set(DATASETS)

    def test_values_are_ndarrays(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert isinstance(result[ds], np.ndarray)

    def test_arrays_correct_total_length(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert result[ds].size == TEST_TOTAL_VALUES, (
                f"{ds}: expected {TEST_TOTAL_VALUES}, got {result[ds].size}"
            )

    def test_all_datasets_same_length(self, wind_data):
        result = wind_data.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        sizes = {ds: result[ds].size for ds in DATASETS}
        assert len(set(sizes.values())) == 1, f"Dataset sizes differ: {sizes}"

    def test_out_of_bounds_lat_lon_returns_empty(self, wind_data):
        result = wind_data.read_narr_timeseries_json(0.0, 0.0)
        assert result == {}


# ---------------------------------------------------------------------------
# TestWindDataS3Integration
# (integration — requires narr_latlon.h5 + valid AWS credentials + NARR_BUCKET)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.s3
@pytest.mark.skipif(
    not aws_fully_configured(),
    reason="Valid AWS credentials (.env) and NARR_BUCKET are required",
)
@pytest.mark.skipif(not narr_grid_available(), reason="NARR grid test file not found")
class TestWindDataS3Integration:
    """End-to-end tests against the real S3 bucket using credentials from .env.

    Confirms the live bucket is accessible and WindDataS3 returns the expected
    data shape.  Skipped automatically when get_aws_config() fails or
    NARR_BUCKET is unset.
    """

    @pytest.fixture(scope="class")
    def wind_data_real_s3(self):
        """WindDataS3 wired to the live S3 bucket; GridIndex from real lat/lon file."""
        gi = GridIndex(TEST_NARR_GRID_LATLON)
        bucket = os.getenv("NARR_BUCKET", "")
        return WindDataS3(gi, bucket=bucket, narr_data_dir=TEST_DATA_DIR)

    # -- credential / connectivity checks -----------------------------------

    def test_s3_client_can_be_created(self):
        """get_s3_client() must not raise with the current .env credentials."""
        client = get_s3_client()
        assert client is not None

    def test_aws_config_returns_required_keys(self):
        config = get_aws_config()
        assert isinstance(config, dict)
        assert "aws_access_key_id" in config
        assert "aws_secret_access_key" in config

    def test_narr_bucket_is_accessible(self, wind_data_real_s3):
        """NARR_BUCKET exists and the credentials can reach it."""
        bucket = os.getenv("NARR_BUCKET", "")
        try:
            wind_data_real_s3.s3_client.head_bucket(Bucket=bucket)
        except ClientError as exc:
            pytest.fail(f"Cannot reach bucket '{bucket}': {exc}")

    # -- read_dataset_json --------------------------------------------------

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_read_dataset_returns_dict(self, wind_data_real_s3, dataset):
        result = wind_data_real_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert isinstance(result, dict), f"{dataset}: expected dict, got {type(result)}"

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_read_dataset_year_keys_are_digits(self, wind_data_real_s3, dataset):
        result = wind_data_real_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        for key in result:
            assert str(key).isdigit(), f"{dataset}: key {key!r} is not a year string"

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_read_dataset_expected_years(self, wind_data_real_s3, dataset):
        result = wind_data_real_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        assert len(result) == TEST_YEARS, (
            f"{dataset}: expected {TEST_YEARS} years, got {len(result)}"
        )

    @pytest.mark.parametrize("dataset", ["pc", "ws", "wd"])
    def test_read_dataset_expected_values_per_year(self, wind_data_real_s3, dataset):
        result = wind_data_real_s3.read_dataset_json(TEST_GRID_X, TEST_GRID_Y, dataset)
        for yr, values in result.items():
            assert len(values) == TEST_VALUES_PER_YEAR, (
                f"{dataset}[{yr}]: expected {TEST_VALUES_PER_YEAR} values, got {len(values)}"
            )

    # -- read_narr_timeseries_json (full pipeline) --------------------------

    def test_timeseries_returns_all_datasets(self, wind_data_real_s3):
        result = wind_data_real_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        assert set(result.keys()) == set(DATASETS)

    def test_timeseries_values_are_ndarrays(self, wind_data_real_s3):
        result = wind_data_real_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert isinstance(result[ds], np.ndarray)

    def test_timeseries_arrays_correct_total_length(self, wind_data_real_s3):
        result = wind_data_real_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert result[ds].size == TEST_TOTAL_VALUES, (
                f"{ds}: expected {TEST_TOTAL_VALUES}, got {result[ds].size}"
            )

    def test_timeseries_all_datasets_same_length(self, wind_data_real_s3):
        result = wind_data_real_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        sizes = {ds: result[ds].size for ds in DATASETS}
        assert len(set(sizes.values())) == 1, f"Dataset sizes differ: {sizes}"

    def test_timeseries_values_are_numeric(self, wind_data_real_s3):
        result = wind_data_real_s3.read_narr_timeseries_json(TEST_MI_LAT, TEST_MI_LON)
        for ds in DATASETS:
            assert np.issubdtype(result[ds].dtype, np.number), (
                f"{ds} array dtype is {result[ds].dtype}, expected numeric"
            )
