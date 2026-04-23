

import os
from unittest import result
from pathlib import Path
import pytest
from mioffset.fod3 import *
from mioffset.aws import get_aws_config, get_s3_client
from mioffset.narr_data import read_narr_timeseries_json, DATASETS, narr_data_filename

# env set in conftest

TEST_DATA_DIR = str(Path(__file__).parent / "data")
TEST_NARR_GRID_LATLON = str(Path(TEST_DATA_DIR) / "narr_latlon.h5")

MI_LAT = 44.0   # representative Michigan point used in legacy tests
MI_LON = -83.0    


@pytest.fixture(autouse=True)
def use_test_narr_grid_latlon(monkeypatch):
    """Force all tests (and called functions) to use test lat/lon grid file."""
    monkeypatch.setenv("NARR_GRID_LATLON", TEST_NARR_GRID_LATLON)

@pytest.fixture(scope="module")
def narr_bucket():
    return os.getenv("NARR_BUCKET")

@pytest.fixture()
def ts(narr_bucket):
    narr_file = os.getenv("NARR_GRID_LATLON")
    example_ts = read_narr_timeseries_json(MI_LAT, MI_LON, narr_bucket, narr_file)
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

    
