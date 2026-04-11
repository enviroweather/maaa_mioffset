#! /usr/bin/env python3 

import os, sys
import json

# requirements python_dotenv, h5py, boto3, numpy
from dotenv import load_dotenv
import h5py
import boto3
import numpy as np

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
    # extract all values for one year
    return(h5f)
    # pc_1year = h5f['PC']
    # ws_1year = h5f['WS']
    # wd_1year = h5f['WD']
    # return pc_1year, ws_1year, wd_1year



# AWS setup

# reload .env file to accommodate changes during development
def get_s3_client():
    load_dotenv(override = True)
    print(os.getenv("REGION_NAME"))
    print(os.getenv("NARR_INPUT_DIR"))
    os.path.exists(os.getenv("NARR_INPUT_DIR"))
    aws_config = { 
        "aws_access_key_id" : os.getenv("AWS_ACCESS_KEY_ID"), 
        "aws_secret_access_key" : os.getenv("AWS_SECRET_ACCESS_KEY"), 
        "region_name" : os.getenv("REGION_NAME") 
    }


    session = boto3.Session(**aws_config)
    s3_client = session.client('s3')
    return(s3_client)


def check_bucket(s3_client, bucket_name):
    try:
        s3_client.head_bucket(Bucket=bucket_name)
        print(f"Bucket {bucket_name} exists")
        return(True)
    except s3_client.exceptions.NoSuchBucket:
        print(f"Bucket {bucket_name} does not exist")
        return(False)

#### main


load_dotenv()

###### set up AWS and check for bucket presence
s3_client = get_s3_client()
narr_bucket = os.getenv('BUCKET_NAME')

if not check_bucket(s3_client, narr_bucket):
    sys.exit(1)
 


narr_input_dir = h5folder = os.getenv('NARR_INPUT_DIR')
if not os.path.exists(path_to_narrfile(2001, narr_input_dir)):
    print("can't access NARR files")
    sys.exit(1)
    


years = list(range(1979, 2009))

##### read in all NARR data
narr_data = {}
for yr in years:
    print(yr)
    narr_data = read_one_year_grid(yr, narr_input_dir)
 
########## build coordinates
# one_year = read_one_year_grid(1979, narr_input_dir=narr_input_dir)
one_year = narr_data[years[0]]['PC']

grid_size_x = one_year.shape[0]
grid_size_y = one_year.shape[1]
       
xdx = list(range(grid_size_x))
ydx = list(range(grid_size_y))

coords = []

for a in xdx:
    for b in  ydx:
        coords.append( [ a, b ] )
    

### main data transform loop
## all 3 datasets are in single dict narr_data[yr][dataset][x][y](ts)
datasets = ['PC', 'WS', 'WD']
for coord in coords:     
    print(coord)
    x,y = coord
    
    # extract all yrs timeseries's for one coordinate per dataset
    one_coord = {'PC': {}, 'WS': {}, 'WD': {}}
    for yr in years:
        print(f"\t {yr}")
        for dataset in datasets :
            one_coord[dataset][yr] = list(map(float, narr_data[yr][dataset][x][y]))        
            # one_coord['WS'][yr] = list(map(float, WS[yr][x][y]))
            # one_coord['WD'][yr] = list(map(float, PC[yr][x][y]))
        
    # save 3 files in s3 for each dataset for this coordinate
    for dataset in datasets :
        print(s3_client.put_object(
            Body=json.dumps(one_coord[dataset]),
            Bucket=narr_bucket,
            Key=f"{dataset.lower()}/{dataset.lower()}_{x}_{y}.json"
        ))

    # print(
    #     s3_client.put_object(
    #         Body=json.dumps(wd_years),
    #         Bucket=narr_bucket,
    #         Key=f"wd/wd_{x}_{y}.json"
    #         )
    # )

    # print(
    #     s3_client.put_object(
    #         Body=json.dumps(ws_years),
    #         Bucket=narr_bucket,
    #         Key=f"ws/ws_{x}_{y}.json"
    #     )
    # )
  
# move these to FOD program  
def read_dataset_from_file(grid_x:int, grid_y:int, dataset:str,narr_input_dir:str):
    """read a dataset for all years, one coordinate from s3

    Args:     
        grid_x (int): grid point
        grid_y (int): grid point
        narr_input_dir (str): directory containing NARR files
        
    Returns:    
        dict[int, float]: A dictionary mapping years to the dataset values at the specified coordinate
    """
    
    # ts = time series
    ts_by_year_file = f"{dataset.lower()}/{dataset.lower()}_{grid_x}_{grid_y}.json"
    with open(os.path.join(narr_input_dir, ts_by_year_file), 'r') as f:
        ts_by_year = json.load(f)
        
    return ts_by_year

def read_dataset_from_s3(grid_x:int, grid_y:int, dataset:str, bucket:str, s3_client:boto3.client):
    """read a dataset for all years, one coordinate from s3

    Args:     
        grid_x (int): grid point
        grid_y (int): grid point
        dataset (str): dataset name (PC, WS, WD)
        bucket (str): name of bucket to read from
        s3_client (boto3.client): s3 client created from a valid session

    Returns:    
        dict[int, float]: A dictionary mapping years to the dataset values at the specified coordinate
    """
    
    # ts = time series
    ts_by_year_file = f"{dataset.lower()}/{dataset.lower()}_{grid_x}_{grid_y}.json"
    response = s3_client.get_object(Bucket=bucket, Key=ts_by_year_file)
    ts_by_year = response['Body'].read()
    ts_by_year = json.loads(ts_by_year)
    return ts_by_year


def prep_dataset_for_fod(ts_by_year: dict[int, float]):
    """convert dictionary of timeserize by year into single
    np array with them all smashed together

    Args:
        ts_by_year (dict[int, float]): dictionary of time series keyed by year

    Returns:
        np.array: time series of floats as expected by FOD 
    """
    
    ts_by_year_nparray = list(map(np.array, list(ts_by_year.values())))
    ts_by_year_merged = np.array(np.concatenate(ts_by_year_nparray))
    return ts_by_year_merged

