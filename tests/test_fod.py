

import os
from unittest import result
from pathlib import Path
import pytest
from mioffset.fod3 import *
from mioffset.aws import get_aws_config, get_s3_client
from mioffset.narr_data import read_narr_lat_lon, read_narr_timeseries_json, DATASETS, narr_data_filename

# env set in conftest

TEST_DATA_DIR = str(Path(__file__).parent / "data")
TEST_NARR_GRID_LATLON = str(Path(TEST_DATA_DIR) / "narr_latlon.h5")

MI_LAT = 44.0   # representative Michigan point used in legacy tests
MI_LON = -83.0    


# how to test
# don't test any HDF5 stuff right now OR move to it's own test file, skip if HD5 files are not present
# A. use env to see if things are set
#    if the aws stuff is set, use AWS for everything
#    else:
#       if file locationset for grid? use that one else use one in test folder
#       if file location set for 


# @pytest.fixture(autouse=True)
# def use_test_narr_grid_latlon(monkeypatch):
#     """Force all tests (and called functions) to use test lat/lon grid file."""
#     monkeypatch.setenv("NARR_GRID_LATLON", TEST_NARR_GRID_LATLON)

@pytest.fixture(scope="module")
def narr_bucket():
    return os.getenv("NARR_BUCKET")


@pytest.fixture(autouse=True)
def test_narr_grid_latlon_path(monkeypatch):
    """Set all tests (and called functions) to use test lat/lon grid file."""
    
    # we use this b/c some code still looks to env in the middle of the function
    # this should rep
    # first look for an env var pointing to a test file
    # if that is empty use the default location for a test file
    test_narr_grid_latlon_path = os.getenv("TEST_NARR_GRID_LATLON", TEST_NARR_GRID_LATLON)
    # next check for an env var that pointing to the programs grid file
    # if that is not set, use the test one
    test_narr_grid_latlon_path = os.getenv("NARR_GRID_LATLON",test_narr_grid_latlon_path)
    # we've gone through and set the path to something.  Is is there
    if not os.path.exists(test_narr_grid_latlon_path):
        raise RuntimeError("can't find the grid file")
    
    monkeypatch.setenv("NARR_GRID_LATLON", test_narr_grid_latlon_path)
    yield test_narr_grid_latlon_path


@pytest.fixture(scope="module")
def narr_gridxy_data(test_narr_grid_latlon_path):
    MI_LAT, MI_LON = read_narr_lat_lon(test_narr_grid_latlon_path)
    return ({'lat':MI_LAT, 'lon':MI_LON})


@pytest.fixture(scope="module")
def ts(narr_gridxy_data):
    narr_bucket = os.getenv("NARR_BUCKET", "")
    if not narr_bucket:
        narr_folder = os.getenv("NARR_DATA_DIR", "")
        if os.path.exists(narr_folder):
            # use local files
            example_ts = read_narr_timeseries_h5(narr_gridxy_data['lat'], narr_gridxy_data['lon'], narr_folder)
        else:
            raise RuntimeError("NARR_BUCKET not set and NARR_DATA_DIR not found")


    else:
        example_ts = read_narr_timeseries_json(narr_gridxy_data['lat'], narr_gridxy_data['lon'], narr_bucket, narr_file)
    return(example_ts)
    
class TestFodModel():    
    def test_fod_model_from_s3_returns_something(self, ts):
        odor_index = 10
        # original code used D for output from this model
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        assert D is not None

        
    def test_fod_model_from_s3_returns_correct_data(self, narr_bucket):
        odor_index = 10
        MI_LAT = 44.0   # representative Michigan point used in legacy tests
        MI_LON = -83.0 
        narr_file = os.getenv("NARR_GRID_LATLON")
        ts = read_narr_timeseries_json(MI_LAT, MI_LON, narr_bucket, narr_file)
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        assert type(D) == type(np.array([]))
        assert D.shape == (80, 3)
        assert float(D[1,1]) == float(np.float64(0.042728866663428844))

    
