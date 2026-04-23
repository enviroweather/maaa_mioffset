"""
tests/test_py

Unit tests for py.

Tests are split into two groups:
  - Pure / in-process functions: always run, no external resources needed.
  - Integration tests (@pytest.mark.integration): require real files or AWS.
    These are skipped automatically when the relevant env-var paths don't exist
    or AWS credentials are absent.

Run only fast tests:
    pytest -m "not integration"

Run everything (requires a valid .env and NARR data files):
    pytest
"""

import os
import json
import tempfile

import numpy as np
from numpy._typing._array_like import NDArray
import pytest

from aws import get_s3_client
from narr_data import * # read_narr_timeseries_s3, read_dataset_from_file



# ---------------------------------------------------------------------------
# Helpers / shared fixtures
# ---------------------------------------------------------------------------

MI_LAT = 44.0   # representative Michigan point used in legacy tests
MI_LON = -83.0


@pytest.fixture
def small_lat_lon_grid():
    """3×3 grid centred on a Michigan point, used by pure-function tests."""
    lats = np.array([[43.0, 43.0, 43.0],
                     [44.0, 44.0, 44.0],
                     [45.0, 45.0, 45.0]])
    lons = np.array([[-84.0, -83.0, -82.0],
                     [-84.0, -83.0, -82.0],
                     [-84.0, -83.0, -82.0]])
    return lats, lons



@pytest.fixture
def ts_by_year_dict():
    """Minimal year-keyed dict mimicking the JSON files stored in S3/disk."""
    rng = np.random.default_rng(42)
    return {
        str(yr): rng.uniform(0, 360, 10).tolist()
        for yr in range(1979, 1982)
    }


# ---------------------------------------------------------------------------
# get the lat/lon converter file
# without this the system won't work, so hard-code it here. 
# ---------------------------------------------------------------------------

class TestNarrFilename:
    def test_lowercase_dataset(self):
        result = narr_data_filename("PC", 12, 34)
        assert result == "pc/pc_012_034.json"

    def test_zero_padded_indices(self):
        result = narr_data_filename("ws", 1, 5)
        assert result == "ws/ws_001_005.json"

    def test_three_digit_indices(self):
        result = narr_data_filename("WD", 100, 200)
        assert result == "wd/wd_100_200.json"

    def test_returns_string(self):
        assert isinstance(narr_data_filename("pc", 0, 0), str)

class TestPathToNarrfile:
    def test_contains_year(self):
        path = path_to_h5_narrfile(1999, "/data/h5")
        assert "1999" in path

    def test_contains_dir(self):
        path = path_to_h5_narrfile(2008, "/some/dir")
        assert path.startswith("/some/dir")

    def test_filename_pattern(self):
        path = path_to_h5_narrfile(1979, "/data")
        assert path.endswith("narr_PSD_1979_BC.h5")


def narr_input_available():
    path = os.getenv("NARR_GRID_LATLON")
    if path and os.path.exists(path):
        return path
    return None

@pytest.fixture
def narr_input_file():
    path = os.getenv("NARR_GRID_LATLON")
    if path and os.path.exists(path):
        return path
    return None

@pytest.mark.integration
@pytest.mark.skipif(not narr_input_available(), reason="NARR_GRID_LATLON file not found")
def testReadNarrLatLon(narr_input_file: str | None):
    # the lat/lons in this file are not really lat/lons, but a combo 
    # so that they may be added to create a distance matrix
    # don't expect these limits to make sense in terms of real lat/long
    # narr_input = os.getenv("NARR_INPUT")
    LAT, LON = read_narr_lat_lon(narr_input_file)
        
    assert LAT is not None
    assert LON is not None
    assert isinstance(LAT, np.ndarray)
    assert isinstance(LON, np.ndarray)
    assert LAT.shape == LON.shape
    assert LAT.min() >= 0
    assert LAT.max() <= 90
    # using west longitude
    assert LON.min() >= -359
    assert LON.max() <= 0

@pytest.fixture
def narr_lat_lon(narr_input_file: str | None):
    return read_narr_lat_lon(narr_input_file)


class TestValidateLatlon:
    def test_valid_point(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(44.0, -83.0, LAT, LON) is True

    def test_lat_too_low(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(42.0, -83.0, LAT, LON) is False

    def test_lat_too_high(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(46.0, -83.0, LAT, LON) is False

    def test_lon_too_low(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(44.0, -85.0, LAT, LON) is False

    def test_lon_too_high(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(44.0, -80.0, LAT, LON) is False

    def test_boundary_min(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(43.0, -84.0, LAT, LON) is True

    def test_boundary_max(self, small_lat_lon_grid):
        LAT, LON = small_lat_lon_grid
        assert validate_latlon(45.0, -82.0, LAT, LON) is True


# ---------------------------------------------------------------------------
# prep_dataset_for_fod
# ---------------------------------------------------------------------------

class TestPrepDatasetForFod:
    def test_returns_ndarray(self, ts_by_year_dict):
        result = prep_dataset_for_fod(ts_by_year_dict)
        assert isinstance(result, np.ndarray)

    def test_length_equals_sum_of_values(self, ts_by_year_dict):
        total = sum(len(v) for v in ts_by_year_dict.values())
        result = prep_dataset_for_fod(ts_by_year_dict)
        assert len(result) == total

    def test_single_year(self):
        data = {"1979": [1.0, 2.0, 3.0]}
        result = prep_dataset_for_fod(data)
        assert type(result) == type(np.array([]))
        np.testing.assert_array_equal(result, np.array([1.0, 2.0, 3.0]))


# ---------------------------------------------------------------------------
# filter_narr_timeseries
# ---------------------------------------------------------------------------

class TestFilterNarrTimeseries:
    @pytest.fixture
    def arrays(self):
        n = 100
        rng = np.random.default_rng(0)
        return (rng.integers(1, 7, n).astype(float),
                rng.uniform(0, 15, n),
                rng.uniform(0, 360, n))

    def test_default_returns_all(self, arrays):
        pc, ws, wd = arrays
        pc_f, ws_f, wd_f = filter_narr_timeseries(pc, ws, wd)
        np.testing.assert_array_equal(pc_f, pc[0:2920])

    def test_slice_correct_length(self, arrays):
        pc, ws, wd = arrays
        pc_f, ws_f, wd_f = filter_narr_timeseries(pc, ws, wd, ts=10, te=50)
        assert len(pc_f) == 40
        assert len(ws_f) == 40
        assert len(wd_f) == 40

    def test_values_preserved(self, arrays):
        pc, ws, wd = arrays
        pc_f, _, _ = filter_narr_timeseries(pc, ws, wd, ts=5, te=15)
        np.testing.assert_array_equal(pc_f, pc[5:15])


# ---------------------------------------------------------------------------
# read_dataset_from_file  (needs a temporary JSON file on disk)
# ---------------------------------------------------------------------------

class TestReadDatasetFromFile:
    def test_reads_valid_json(self, ts_by_year_dict):
        with tempfile.TemporaryDirectory() as tmpdir:
            dataset = "pc"
            grid_x, grid_y = 5, 10
            # narr_filename creates "pc/pc_005_010.json"
            key = narr_data_filename(dataset, grid_x, grid_y)
            full_path = os.path.join(tmpdir, key)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                json.dump(ts_by_year_dict, f)

            result = read_dataset_from_file(grid_x, grid_y, dataset, tmpdir)

        assert isinstance(result, dict)
        assert set(result.keys()) == set(ts_by_year_dict.keys())


# ---------------------------------------------------------------------------
# Integration tests — require real NARR HDF5 lat/lon file (NARR_INPUT env var)
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(not narr_input_available(), reason="NARR_GRID_LATLON file not found")
class TestLatLonToGridyx:
    def test_returns_two_ints(self):
        grid_x, grid_y = latlon_to_gridyx(MI_LAT, MI_LON)
        assert isinstance(grid_x, int)
        assert isinstance(grid_y, int)

    def test_values_positive(self):
        grid_x, grid_y = latlon_to_gridyx(MI_LAT, MI_LON)
        assert grid_x >= 0
        assert grid_y >= 0

    def test_out_of_bounds_returns_none(self):
        # Clearly outside NARR domain
        grid_x, grid_y = latlon_to_gridyx(0.0, 0.0)
        assert grid_x is -1
        assert grid_y is -1


# ---------------------------------------------------------------------------
# Integration tests — require AWS credentials + S3 bucket (NARR_BUCKET + AWS_*)
# ---------------------------------------------------------------------------

def s3_available():
    return bool(os.getenv("NARR_BUCKET") and os.getenv("AWS_ACCESS_KEY_ID"))

@pytest.fixture(scope="module")
def grid_x_y(): 
    return latlon_to_gridyx(MI_LAT, MI_LON)

@pytest.mark.integration
@pytest.mark.skipif(not s3_available(), reason="AWS credentials or NARR_BUCKET not configured")
class TestReadDatasetFromS3:
    
    grid_x:int = 0
    grid_y:int = 0
    grid_x, grid_y = latlon_to_gridyx(MI_LAT, MI_LON)
    
    s3_client = get_s3_client()
    bucket = os.getenv("NARR_BUCKET", "")
    
    def test_returns_dict(self):                
        result = read_dataset_from_s3(self.grid_x, self.grid_y, "PC", self.bucket, self.s3_client) # type: ignore
        assert isinstance(result, dict)
        assert len(result) > 0

    def test_years_are_keys(self):        
        result:dict = read_dataset_from_s3(self.grid_x, self.grid_y, "WS", self.bucket, self.s3_client) # type: ignore
        for key in result:
            assert str(key).isdigit()
    
    def test_ts_values_are_lists(self):
        result:dict = read_dataset_from_s3(self.grid_x, self.grid_y, "WS", self.bucket, self.s3_client) # type: ignore
        for key, values in result.items():
            assert isinstance(values, list), f"Values for key {key} should be a list"
            assert len(values) > 0, f"Values for key {key} list is empty"



def narr_grid_latlon_s3_available():
    """Return True when AWS creds, NARR_BUCKET, and NARR_GRID_LATLON_S3 are all set."""
    return bool(
        os.getenv("NARR_BUCKET")
        and os.getenv("AWS_ACCESS_KEY_ID")
        and os.getenv("NARR_GRID_LATLON_S3")
    )


@pytest.mark.integration
@pytest.mark.skipif(
    not narr_grid_latlon_s3_available(),
    reason="AWS credentials, NARR_BUCKET, or NARR_GRID_LATLON_S3 not configured",
)
class TestReadNarrLatLonFromS3:
    """Integration tests: read the NARR lat/lon reference file from S3."""

    def test_returns_two_arrays(self):
        LAT, LON = read_narr_lat_lon(source="s3")
        assert LAT is not None
        assert LON is not None
        assert isinstance(LAT, np.ndarray)
        assert isinstance(LON, np.ndarray)

    def test_shapes_match(self):
        LAT, LON = read_narr_lat_lon(source="s3")
        assert LAT.shape == LON.shape

    def test_lat_bounds(self):
        LAT, LON = read_narr_lat_lon(source="s3")
        assert LAT.min() >= 0
        assert LAT.max() <= 90

    def test_lon_bounds(self):
        LAT, LON = read_narr_lat_lon(source="s3")
        assert LON.min() >= -359
        assert LON.max() <= 0

    def test_explicit_s3_key(self):
        """Passing the S3 key explicitly should produce the same result."""
        s3_key = os.getenv("NARR_GRID_LATLON_S3", "narr_latlon.h5")
        LAT1, LON1 = read_narr_lat_lon(source="s3")
        LAT2, LON2 = read_narr_lat_lon(narr_grid_latlon=s3_key, source="s3")
        np.testing.assert_array_equal(LAT1, LAT2)
        np.testing.assert_array_equal(LON1, LON2)


@pytest.mark.integration
@pytest.mark.skipif(
    not narr_grid_latlon_s3_available(),
    reason="AWS credentials, NARR_BUCKET, or NARR_GRID_LATLON_S3 not configured",
)
class TestLatLonToGridyxS3:
    """Integration tests: convert lat/lon to grid indices using S3 for the reference file."""

    def test_returns_two_ints(self):
        grid_x, grid_y = latlon_to_gridyx(MI_LAT, MI_LON, source="s3")
        assert isinstance(grid_x, int)
        assert isinstance(grid_y, int)

    def test_values_non_negative(self):
        grid_x, grid_y = latlon_to_gridyx(MI_LAT, MI_LON, source="s3")
        assert grid_x >= 0
        assert grid_y >= 0

    def test_out_of_bounds_returns_minus_one(self):
        grid_x, grid_y = latlon_to_gridyx(0.0, 0.0, source="s3")
        assert grid_x == -1
        assert grid_y == -1

    def test_file_and_s3_agree(self):
        """Grid indices from S3 and local file should be identical."""
        narr_grid_latlon = os.getenv("NARR_GRID_LATLON", "")
        if not narr_grid_latlon or not os.path.exists(narr_grid_latlon):
            pytest.skip("NARR_GRID_LATLON local file not available for comparison")
        x_s3, y_s3 = latlon_to_gridyx(MI_LAT, MI_LON, source="s3")
        x_file, y_file = latlon_to_gridyx(MI_LAT, MI_LON, source="file")
        assert x_s3 == x_file
        assert y_s3 == y_file


@pytest.mark.integration
@pytest.mark.skipif(
    not (s3_available() and narr_input_available()),
    reason="AWS credentials, NARR_BUCKET, and NARR_GRID_LATLON are all required",
)
class TestReadNarrTimeseriesS3:
    """Integration tests for get_narr_timeseries_s3.

    Requires a valid .env with NARR_BUCKET, NARR_FILE, and AWS credentials.
    """
    
    narr_ts = get_narr_timeseries_s3(MI_LAT, MI_LON)

    def test_returns_dict(self):    
        assert isinstance(self.narr_ts, dict)
    
    def test_has_all_three_datasets(self):
        assert set(self.narr_ts.keys()) == {'pc', 'ws', 'wd'}

    def test_each_dataset_is_dict(self):
        for key in ('pc', 'ws', 'wd'):
            assert isinstance(self.narr_ts[key], dict), f"{key} should be a year-keyed dict"

    def test_each_dataset_nonempty(self):
        for key in ('pc', 'ws', 'wd'):
            assert len(self.narr_ts[key]) > 0, f"{key} dataset is empty"

    def test_year_keys_are_digit_strings(self):
        for key in ('pc', 'ws', 'wd'):
            for yr in self.narr_ts[key]:
                assert str(yr).isdigit(), f"Year key {yr!r} in {key} is not numeric"

    def test_year_values_are_lists(self):
        for key in ('pc', 'ws', 'wd'):
            for yr, values in self.narr_ts[key].items():
                assert isinstance(values, list), f"{key}[{yr}] should be a list"
                assert len(values) > 0, f"{key}[{yr}] list is empty"

    def test_all_datasets_cover_same_years(self):
        year_sets = [set(self.narr_ts[k].keys()) for k in ('pc', 'ws', 'wd')]
        assert year_sets[0] == year_sets[1] == year_sets[2]
    
    def test_timeseries_values_are_floats(self):
        for dataset in ('pc', 'ws', 'wd'):
            random_year = str(1985) # make this actually random!
            random_position = 1000
            x = self.narr_ts[dataset][random_year][random_position]
            assert isinstance(x, float), f"Value at {dataset}[{random_year}][{random_position}] should be a float"
    
    def test_timeseries_are_correct_length(self):
        ts_items = int(24/3 * 365)
        for dataset in ('pc', 'ws', 'wd'):
            random_year = str(1985) # make this actually random!
            ts = self.narr_ts[dataset][random_year]            
            assert len(ts) == ts_items
            

@pytest.mark.integration
@pytest.mark.skipif(
    not (s3_available() and narr_input_available()),
    reason="AWS credentials, NARR_BUCKET, and NARR_GRID_LATLON are all required",
)
class TestDataForFODfromS3(): 
    bucket=os.getenv("NARR_BUCKET")
    narr_grid_latlon=os.getenv("NARR_GRID_LATLON")
    
    def test_read_narr_timeseries_s3(self):
        
        fod_dict = read_narr_timeseries_json(latval=MI_LAT, lonval=MI_LON, bucket = self.bucket, narr_grid_latlon= self.narr_grid_latlon) #type:ignore
        
        assert type(fod_dict) == dict
        for time_series in fod_dict.values():
            assert type(time_series) == np.ndarray
            assert time_series.size > 0
            assert time_series.shape[0] > 0
            # datasets are 3 hourly, so min 3 hours for 365 days big
            
    def test_fod_data_has_at_least_one_year_data(self):
        fod_dict = read_narr_timeseries_json(latval=MI_LAT, lonval=MI_LON, bucket = self.bucket, narr_grid_latlon = self.narr_grid_latlon)
        for time_series in fod_dict.values():
            assert time_series.size >= (24/3 * 365)
        
        # note: these data_sets are times series of 3 hours for N years, 
        # so we should test that they are big and 
