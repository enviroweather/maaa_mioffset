#!python3
"""
This script runs the fod model with specific conditions and allows output in
different formats but does not save files, only send output to stdout
"""

import sys
from venv import create

from dotenv import load_dotenv
import os
from datetime import datetime
import numpy as np

##### import for type checking only
import typing as t
if t.TYPE_CHECKING:
    import numpy as np    

from mioffset.aws import get_aws_config, get_s3_client
from mioffset.narr_data import WindData, wind_data_factory, filter_narr_timeseries
from mioffset.fod3 import fod_model, fod2dict, fod_plot_to_ll
from mioffset.setback_geojson import fod_geojson
    
load_dotenv()

def config_from_env()->dict:
    load_dotenv()
    return {
        "narr_bucket": os.getenv("NARR_BUCKET",""),
        "narr_data_dir": os.getenv("NARR_DATA_DIR",""),
        "narr_grid_file": os.getenv("NARR_GRID_LATLON_S3")
    }

    
def config_from_context(context)->dict:
    # this first round only works from JSON on S3
    return {
        "narr_bucket": context.get("narr_bucket", ""),
        "narr_data_dir": context.get("narr_data_dir", ""),
        "narr_grid_file": context.get("narr_grid_file", "")
    }


def fod_run_s3(lat, lon, odor_index,s3_client, narr_bucket, narr_data_dir, narr_grid_file)->np.ndarray:    
    wind_data:WindData = wind_data_factory(location = "S3", 
                      narr_grid_file = narr_grid_file, 
                      narr_data_dir = narr_data_dir,
                      narr_bucket = narr_bucket, 
                      s3_client = s3_client)    
    wd = wind_data.read_narr_timeseries_json(latval = lat, lonval = lon, format = "FOD")
    D = fod_model(odor_index= odor_index,
                       pc = wd["pc"], wind_speed=wd["ws"], wind_direction=wd["wd"]
                       )
    
    return(D)

def build_fod_response(D, lat:float, lon:float, odor_index:int, topt = 1, version:str = "0.1")->dict:
    """create visualizations
    """
    
    # create objects to return
    # data
    fod_results = fod2dict(D)
    
    # plot
    latslons = fod_plot_to_ll(D,lat, lon)
    geo_json = fod_geojson(latslons, E= odor_index, lat = lat, lon = lon)
    
    fod_response = {}

    fod_response["meta"] = {
        "version" : str(version),   # version of package
        "timestamp" : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    fod_response["inputs"] = {
        "lat":lat, 
        "lon":lon, 
        "oef":odor_index 
    }
    
    fod_response["outputs"] = {
        "raw" : {"format": "application/json",  "data": fod_results },
        "map" : {"format" : "application/geo+json", "data" : geo_json },
    }
                        
    return(fod_response)



def api_handler(event, context):
    # Extract parameters from the event
    lat = event.get("lat")
    lon = event.get("lon")
    odor_index = event.get("odor_index")
    
    config = config_from_env()
    
    s3_client = get_s3_client(get_aws_config())
    # Call the FOD run function
    D = fod_run_s3(lat, lon, odor_index, s3_client, config["narr_bucket"], config["narr_data_dir"], config["narr_grid_file"])

    # Build the response
    response = build_fod_response(D, lat, lon, odor_index)
    return response


