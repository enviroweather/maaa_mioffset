

import os
from unittest import result
import pytest
from fod3 import *
from aws import get_aws_config, get_s3_client
from narr_data import read_narr_timeseries_json, DATASETS, narr_data_filename

# env set in conftest

MI_LAT = 44.0   # representative Michigan point used in legacy tests
MI_LON = -83.0    
narr_file=os.getenv("NARR_FILE")

@pytest.fixture(scope="module")
def narr_bucket():
    return os.getenv("NARR_BUCKET")

@pytest.fixture()
def ts(narr_bucket):
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
        ts = read_narr_timeseries_json(MI_LAT, MI_LON, narr_bucket, narr_file)
        D = fod_model(pc=ts['pc'], wind_speed=ts['ws'], wind_direction=ts['wd'], odor_index=odor_index)
        assert type(D) == type(np.array([]))
        assert D.shape == (80, 3)
        assert float(D[1,1]) == float(np.float64(0.042728866663428844))

    
