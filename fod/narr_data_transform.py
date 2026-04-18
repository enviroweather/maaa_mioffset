#! /usr/bin/env python3 

import os, sys
import json

# requirements python_dotenv, h5py, boto3, optional numpy
from dotenv import load_dotenv
import h5py
# this is only needed when reading data in
#import numpy as np
from aws import get_s3_client, check_bucket, boto3 # get_aws_config
from fod3 import path_to_narrfile # read_narr_lat_lon,validate_latlon,read_one_year,read_narr_timeseries, 

def read_one_year_grid(yr:str,narr_input_dir:str):
    """read one year hf5 file, extra 3 datasets
    return whole grid
    Files must be named like narr_PSD_1980_BC.h5
    
    Args:
        yr (int): year of data to read, embedded in filename
        narr_input_dir (str): path to NARR input files
    Returns:
        tuple of np arrays: timeseries values for PC, WD and WS 
    """
    
    h5f_annual_filename = path_to_narrfile(yr, narr_input_dir)
    h5f = h5py.File(h5f_annual_filename, 'r')
    return(h5f)


def build_grid_coordinates(grided_data, grid_x:int|None=None):
    """create a list of 2D coordinate tuples (x,y) given a grid file
    

    Args:
        grided_data (_type_): grid hd5 file with x and y as first two elements
        
        grid_x (int or list, optional): either a single int or a list of ints that
        will be used for the x-coordinates for creating a subset of the list. Defaults to None which means use whole grid
        grid_y (int or list, optional): either a single int or a list of ints that
        will be used for the y-coordinates for creating a subset of the list. Defaults to None which means use whole grid   
    """
    
    # is there a better way than to filter the list here when we make the 
    # coordinate list? this wil work for this one-off
    
    # previously got the grid from reading a single year and filtering
    # one_year = read_one_year_grid(1979, narr_input_dir=narr_input_dir)
    # then it was 
    # one_year = narr_data[years[0]]['PC']
    grid_size_x = grided_data.shape[0]
    grid_size_y = grided_data.shape[1]
    xdx = list(range(grid_size_x))
    ydx = list(range(grid_size_y))
    coords = []

    if grid_x:
        # x value was sent, just build for one x and all y
        xdx = int(grid_x)
        for y in  ydx:
            coords.append( [xdx, y ] )
        
    else:
        # no x value, build whole list of coords
        for a in xdx:
            for b in  ydx:
                coords.append( [ a, b ] )
        
    return(coords)
            
            

def narr_filename(dataset:str, x:int,y:int ):
    """
    helper function for standard naming of a narr file for one coordinate and all years
    """
    one_coord_filename=f"{dataset.lower()}/{dataset.lower()}_{x:03}_{y:03}.json"
    return(one_coord_filename)


def transform_by_coordinate(grid_x, grid_y=None, narr_bucket=None, config=None):

    load_dotenv()
    
    print("AWS setup")
    
    s3_client = get_s3_client()  # use default dot-env
    
    # check that the bucket is in there
    if not narr_bucket:
        narr_bucket = os.getenv('BUCKET_NAME')
    if not check_bucket(s3_client, narr_bucket):
        sys.exit(1)
 
    # constants
    years = list(range(1979, 2009))
    datasets = ['PC', 'WS', 'WD']
    

    ## set up narr files
    narr_input_dir = h5folder = os.getenv('NARR_INPUT_DIR')
    if not os.path.exists(path_to_narrfile(2001, narr_input_dir)):
        print("can't access NARR files")
        sys.exit(1)
    

    ##########
    print("reading narr data")
    narr_data = {}
    for yr in years:
        print(yr)
        narr_data[yr] = read_one_year_grid(yr, narr_input_dir)
 
    one_year = narr_data[years[0]]['PC']
    coords = build_grid_coordinates(one_year,grid_x=grid_x)

    ######
    print(" main data transform loop")
    ## we  3 datasets from the F5 files, in single dict narr_data[yr][dataset][x][y](ts)

    # check these are all in the h5 file! 

    for coord in coords:
        print(coord)
        x,y = coord
        
        # extract one coordinate's timeseries' for all years per dataset
        # into new dict structure
        one_coord = {'PC': {}, 'WS': {}, 'WD': {}}
        for yr in years:
            print(f"\t {yr}")
            for dataset in datasets :
                # timeseries data read in as a NP value, convert these to float new storage
                one_coord[dataset][yr] = list( map(float, narr_data[yr][dataset][x][y]) )

        # save 3 files in s3 for each dataset for this coordinate
        for dataset in datasets :
            try:
                resp = s3_client.put_object(
                    Body = json.dumps(one_coord[dataset]),
                    Bucket = narr_bucket,
                    Key = narr_filename(dataset, x,y)
                )
                
                if resp['ResponseMetadata']['HTTPStatusCode'] != 200:
                    print(f"error writing to S3 for coordinates ({x}, {y}) and dataset {dataset}")
                    return False
                else:
                    print(f"({x}, {y}) {dataset}")
            except Exception as e:
                print(f"error S3 {e} for ({x}, {y}) dataset {dataset}")
                return False
            
    return True


if __name__ == "__main__":
    
    # load config from environment, .env file
    result = load_dotenv()
    if not result:
        print("could not load .env file")
        sys.exit(1)
        
    if len(sys.argv) > 1:
        x_coordinate = float(sys.argv[1])
    else:
        x_coordinate = None
    
    result = transform_by_coordinate(grid_x = x_coordinate, narr_bucket=os.getenv('BUCKET_NAME'))
    if not result:
        print(f"ERROR x = {x_coordinate}")
        sys.exit(1)
    
