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

# package config

from mioffset.aws import get_aws_config, get_s3_client
from mioffset.narr_data import WindData, wind_data_factory
from mioffset.fod3 import fod_model,fod2dict,setback_text_table, \
    footprint_plots,matplotlib_to_svg,fod_geojson,fod_plot_to_ll
import numpy as np
    
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
                       pc = wd['pc'], wind_speed=wd['ws'], wind_direction=wd['wd']
                       )
    
    return(D)


def build_fod_response(D, lat:float, lon:float, odor_index:int, topt = 1, version:str = "0.1")->dict:
    """create visualizations
    
    """
    
    # create objects to return
    # data
    fod_results = fod2dict(D)
    table_text = setback_text_table(D)
    # plot
    plot = footprint_plots(D, E = odor_index, topt = topt)
    plot_svg = matplotlib_to_svg(plot)
    plot_svg_encoded = plot_svg.encode(encoding='utf-8')
    # map
    latslons = fod_plot_to_ll(D,lat, lon)
    geo_json = fod_geojson(latslons, E= odor_index, lat = lat, lon = lon)
    
    # build response
    fod_response = {}

    fod_response['meta'] = {
        'version' : str(version),   # version of package
        'timestamp' : datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    fod_response['inputs'] = {
        'lat':lat, 
        'lon':lon, 
        'oef':odor_index 
    }
    
    fod_response['outputs'] = {
        'raw' : {'format': 'application/json',  'data': fod_results },
        'table' : {'format': 'text/plain', 'data': table_text },
        'map' : {'format' : 'application/geo+json', 'data' : geo_json },
        'plot' : {'format' : 'image/svg+xml;charset=utf-8', 'data': plot_svg_encoded }                           
    }
                        
    return(fod_response)


def api_handler(event, context):
    # Extract parameters from the event
    lat = event.get('lat')
    lon = event.get('lon')
    odor_index = event.get('odor_index')
    
    config = config_from_env()
    
    s3_client = get_s3_client(get_aws_config())
    # Call the FOD run function
    D = fod_run_s3(lat, lon, odor_index, s3_client, config["narr_bucket"], config["narr_data_dir"], config["narr_grid_file"])

    # Build the response
    response = build_fod_response(D, lat, lon, odor_index)
    return response

#TODO create a runner that outputs a full HTML page

#TODO update this for new FOD code!  Do we ever really want to save these files?
def oldfodrun():
    load_dotenv()
    lat:float = float(sys.argv[1])
    lon:float = float(sys.argv[2])
    odor_index:int = int(float(sys.argv[3]))
    file_prefix:str = sys.argv[4]
    narr_data_location:str = sys.argv[5] if len(sys.argv) > 5 else os.getenv("NARR_DATA_LOCATION", "S3")
    output_offset_dir=sys.argv[6] if len(sys.argv) > 6 else  os.getenv("OUTPUT_OFFSET_DIR")    
    # raises exception if location is outside the NARR domain
    # gather additional params from "config" python script
    
    time_flag = os.getenv("TIME_FLAG", "F")
    output_offset_dir=os.getenv("OUTPUT_OFFSET_DIR")
    if not output_offset_dir:
        raise ValueError("OUTPUT_OFFSET_DIR environment variable is not set")

    
    # this reduces the number of params but re-using the "narr_data_dir" as 
    # either the folder where the H5 files are the bucket name
    
    narr_bucket:str = os.getenv("NARR_BUCKET", "")
    narr_data_dir:str = os.getenv("NARR_DATA_DIR", "")
    narr_grid_file = os.getenv("NARR_GRID_LATLON_S3", "")
    

    
    if narr_data_location=="S3":
        narr_bucket:str = os.getenv("NARR_BUCKET", "")
        narr_data_dir:str = os.getenv("NARR_DATA_DIR", "")
        narr_json_dir:str = os.getenv("NARR_JSON_DIR", "")

        narr_grid_file = os.getenv("NARR_GRID_LATLON_S3", "")
        from mioffset.aws import get_aws_config, get_s3_client, S3Client
        try:
            aws_config:dict = get_aws_config()
            s3_client:S3Client = get_s3_client(aws_config)
        except Exception as e:
            raise ValueError(f"Location S3 but error occurred while initializing AWS config: {e}")  
        
        wind_data:WindData = wind_data_factory(location = "S3", 
                narr_grid_file = narr_grid_file, 
                narr_data_dir = narr_data_dir,
                narr_bucket = narr_bucket, 
                s3_client = s3_client)   

    else:
        narr_data_dir = os.getenv("NARR_DATA_DIR","")
        narr_grid_file = os.getenv("NARR_GRID_LATLON", "")
        
        if not os.path.exists(narr_grid_file):
            raise ValueError(f"NARR_GRID_LATLON '{narr_grid_file}' not found")
        if not os.path.exists(narr_data_dir):
            raise ValueError(f"NARR_DATA_DIR '{narr_data_dir}' not found")
        
        wind_data:WindData = wind_data_factory(location = "FILE", 
                                               narr_grid_file = narr_grid_file, 
                                               narr_data_dir = narr_data_dir)

    
    file_locations = fod(lat, lon, odor_index, file_prefix, time_flag, output_offset_dir, wind_data)


##### PREVIOUS MAIN RUNNER
def fod(latval:float, lonval:float, odor_index:int, file_prefix:str, time_flag:str, output_offset_dir:str, wind_data:WindData):
    """runs the FOD model, generates visualizations and saves them to disk

    Args:
        latval (float): latitude of point source   
        lonval (float): longitude of point source
        odor_index (int): odor index value
        file_prefix (str): prefix for output files
        LAT (np.ndarray): array of latitudes
        LON (np.ndarray): array of longitudes
        time_flag (str, optional): time flag for dataset selection. Defaults to TIME_FLAG on config file
        output_offset_dir (str, optional): directory for output files  Defaults to OUTPUT_OFFSET_DIR.
    
    Returns: 
        dictionary of file locations
    """
    
    E = odor_index # doing this here to match legacy code and downstream fn's
    
    if(time_flag == 'F'):
        tfs=1;tfe=1 #Full year dataset: 1 Jan - 31 Dec; run program once.
    elif(time_flag == 'W'):
        tfs=2;tfe=2;#Warm season dataset: 1 Apr - 31 Oct ; run program once.
    elif(time_flag == 'B'):
        tfs=1;tfe=2 #Run program twice, once for 1 Jan - 31 Dec (tfs=1), and a second time, for 1 Apr - 31 Oct. (tfe=2)
    else:
        print('Incorrect time flag option, defaulting to full year')
        tfs=1;tfe=1				

    # read in wind data for coordinates from a 
    # previously configured class 
    narr_timeseries = wind_data.read_narr_timeseries_json(latval, lonval, format = "FOD")

    # this runs once for flags F and W and twice for B
    for topt in range(tfs,tfe+1):
        if(topt == 1):
            # Use full dataset: 00 UCT 1 Jan to 21 UCT 31 Dec
            ts,te=(0,2920)
        elif(topt == 2):
            # Restrict to 00 UTC 1 Apr (point #721, i.e., #720 in pythonese)
            # to 21 UTC 31 Oct (point #2432, i.e., #2431 in pythonese).
            # Recall that Xindi's data omits leap days.  So each year
            # contains the same number of hours.
            ts,te=(720,2432)
        
        narr_timeseries =  filter_narr_timeseries(narr_timeseries, ts, te)
        
        pc: np.ndarray = narr_timeseries['pc']
        wind_speed: np.ndarray = narr_timeseries['ws']
        wind_direction: np.ndarray = narr_timeseries['wd']    
        
        # run model        
        D = fod_model(pc=pc, wind_speed=wind_speed, wind_direction=wind_direction, odor_index=odor_index)
        
        footprints_plot_file_path, five_percent_plot_file_path = write_footprint_plots(D=D, E=E, topt=topt, output_offset_dir=output_offset_dir, file_prefix=file_prefix)


        #---------Print formatted table to text file--------        
        if(topt == 1):            
            text_file_name:str = 'table_setbackdistance_FY.txt'            
        elif(topt == 2):
            text_file_name:str = 'table_setbackdistance_WS.txt' 
        else:
            text_file_name:str = 'table_setbackdistance.txt'
        
            
        text_file_name = add_prefix_to_filename(
            os.path.join(output_offset_dir, text_file_name), file_prefix)
        
        table_text = setback_text_table(D)
        # write_setback_text_table(text_file_name=text_file_name, table_text=table_text)
        
        # make a Lat/Lon array, used by both KML and shape file writers
        # this is not the same as 2018 version:
        #   b/c uses geodesic fn since vincenty was deprecated
        
        LL = fod_plot_to_ll(D=D, lat = latval, lon = lonval)
        
        #-----------Generate KML file with footprints drawn as polygons----------
        if(topt == 2):
            file_name = "kml_footprint_WS.kml" 
        else:
            file_name = "kml_footprint_FY.kml"
            
        kml_file_name = add_prefix_to_filename(os.path.join(output_offset_dir, file_name), file_prefix)
        write_kml(LL, E, latval, lonval, kml_file_name)


        #----------Create ESRI shapefile (only output 5% footprint)--------------

        # point source
        if(topt == 1):
            shapefile_name_stem = SHAPE_SOURCE_FY = 'shp_source_FY' 
        elif(topt == 2):
            shapefile_name_stem = SHAPE_SOURCE_WS = 'shp_source_WS' 

        shapefile_name_stem = add_prefix_to_filename(os.path.join(output_offset_dir, shapefile_name_stem), file_prefix)

        pointsource_shape_files = write_pointsource_shapefile(shapefile_name_stem, lonval, latval)
        
        # polygon
        if(topt == 1):
            shapefile_name_stem = SHAPE_FOOTPRINT_FY = 'shp_footprint_FY' 
        elif(topt == 2):                   
            shapefile_name_stem = SHAPE_FOOTPRINT_WS = 'shp_footprint_WS'      

        shapefile_name_stem = add_prefix_to_filename(os.path.join(output_offset_dir, shapefile_name_stem), file_prefix)
        footprint_shape_files = write_footprint_shapefile(shape_file_name_stem=shapefile_name_stem, LL=LL)

        #---- create zip of shape file ---#
        
        zip_files = pointsource_shape_files + footprint_shape_files
        if(topt == 1):
            zipfile_name = 'fy_shapefile.zip' 
        elif(topt == 2):                   
            zipfile_name = 'ws_shapefile.zip' 
        
        zipfile_path =  add_prefix_to_filename(os.path.join(output_offset_dir,  zipfile_name), file_prefix)
    
        zipfile_path = write_zipfile(zipfile_path, zip_files)
        
    # end for loop