

import os
from unittest import result
from pathlib import Path
import pytest
from mioffset.fod3 import *
from mioffset.aws import get_aws_config, get_s3_client
from mioffset.narr_data import GridIndex, WindData

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

@pytest.fixture(autouse=True, )
def test_narr_grid_latlon_path(monkeypatch):
    """Set all tests (and called functions) to use test lat/lon grid file."""
    
    # we use this b/c some code still looks to env in the middle of the function
    # this should rep
    # first look for an env var pointing to a test file
    # if that is empty use the default location for a test file
    test_path = os.getenv("TEST_NARR_GRID_LATLON", TEST_NARR_GRID_LATLON)
    # next check for an env var that pointing to the programs grid file
    # if that is not set, use the test one
    test_path = os.getenv("NARR_GRID_LATLON",test_path)
    # we've gone through and set the path to something.  Is is there
    if not os.path.exists(test_path):
        raise RuntimeError("can't find the grid file")
    
    monkeypatch.setenv("NARR_GRID_LATLON", test_path)
    yield test_path


@pytest.fixture()
def narr_bucket():
    return os.getenv("NARR_BUCKET")

@pytest.fixture()
def narr_grid_index(test_narr_grid_latlon_path):
    # assuming there is a test version of the grid file in the test folder
    try:
        grid_index = GridIndex(test_narr_grid_latlon_path)
    except Exception as e:
        raise RuntimeError(f"Error occurred while initializing GridIndex: {e}")
    yield grid_index


@pytest.fixture()
def ts(narr_grid_index):
    try:
        wind_data = WindData(narr_grid_index, location="FILE", narr_data_dir=TEST_DATA_DIR)
    except Exception as e:
        raise RuntimeError(f"could not get wind data : {e}")
    
    example_ts = wind_data.read_narr_timeseries_json(MI_LAT, MI_LON, format = "FOD")
    return(example_ts)
    
class TestFodModel():    
    def test_fod_model_returns_something(self, ts):
        odor_index = 10
        # original code used D for output from this model
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        assert D is not None

        
    def test_fod_model_returns_correct_data(self, ts):
        odor_index = 10
        
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        assert type(D) == type(np.array([]))
        assert D.shape == (80, 3)
        assert float(D[1,1]) == float(np.float64(0.042728866663428844))
        
    def test_fod_model_handles_edge_cases(self, ts):
        odor_index = 0
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        assert D is not None
        
    def test_fod_model_json(self, ts):
        odor_index = 10
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        json_data = fod2json(D)
        assert json_data is not None
        assert type(json_data) == str

