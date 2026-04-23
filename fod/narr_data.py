"""
narr_data.py — NARR wind-climate data access layer for the MI Odor Print (MIOFFSET) model.

Provides functions to:
  - Locate the nearest NARR grid point for a given latitude/longitude.
  - Read PC (pressure class), WS (wind speed), and WD (wind direction) time-series
    from either local HDF5 files or JSON files stored in AWS S3.
  - Convert raw year-keyed dictionaries into concatenated NumPy arrays ready for
    the FOD model.

Expected environment variables (set via .env / dotenv):
  NARR_INPUT      — path or S3 key to the HDF5 lat/lon reference file (narr_latlon.h5)
  NARR_INPUT_DIR  — local directory containing per-year HDF5 files (narr_PSD_<yr>_BC.h5)
  NARR_BUCKET     — S3 bucket name holding JSON climate data files
  AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, REGION_NAME — standard AWS credentials
"""

from logging import warning
import numpy as np
import h5py
import os, json, tempfile
from dotenv import load_dotenv
from aws import get_s3_client


# the original HDF5 files each had 3 datasets or types of date
# for the timeseries at each gridpoint: PC = ? WS=Windspeed and WD=Wind Direction
#TODO make these upper case to match original HDF5 datasets
# but ensure that will work throughout the code
DATASETS = ['pc', 'ws', 'wd']

# ws, 10, 120

def narr_data_filename(dataset:str, x:int,y:int )->str:
    """
    helper function for standard naming of the JSON formatted narr file 
    for one coordinate and all years.  The file always has a folder prepending it
    (w.g. pc/pc_001_002.json) for more efficient access on S3
    
    
    Args:
        dataset (str): The specific dataset name, upper or lower case (PC, WS, WD)
        x (int): The x-coordinate
        y (int): The y-coordinate
    Returns:
        str: The filename for the JSON formatted narr file
    """
    one_coord_filename=f"{dataset.lower()}/{dataset.lower()}_{x:03}_{y:03}.json"
    return(one_coord_filename)


def read_narr_lat_lon(narr_grid_latlon: str = "", source: str = "file"):
    """read in lat,lon for converting lat lon to climatology grid indices

    Args:
        narr_grid_latlon (str): For source="file": full path to the NARR input file.
            For source="s3": S3 key for the file.
            Defaults to env var NARR_GRID_LATLON (file) or NARR_GRID_LATLON_S3 (s3).
        source (str): Where to read from - "file" (local disk) or "s3" (AWS S3).
            Defaults to "file".
    """
    if source == "s3":
        load_dotenv()
        bucket = os.getenv('NARR_BUCKET', '')
        s3_key = narr_grid_latlon or os.getenv('NARR_GRID_LATLON_S3', 'narr_latlon.h5')

        if not bucket:
            Warning("NARR_BUCKET not set.")
            return None, None

        s3_client = get_s3_client()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.h5')
        os.close(tmp_fd)
        try:
            s3_client.download_file(bucket, s3_key, tmp_path)
            with h5py.File(tmp_path, 'r') as hf:
                LAT = np.array(hf.get('LAT'))
                LON = np.array(hf.get('LON'))
        finally:
            os.unlink(tmp_path)
        return LAT, LON

    # file-based (existing behaviour)
    if not narr_grid_latlon:
        narr_grid_latlon = os.getenv('NARR_GRID_LATLON', "")

    if not narr_grid_latlon or not os.path.exists(narr_grid_latlon):
        Warning("NARR file not provided or not found.")
        return None, None

    with h5py.File(narr_grid_latlon, 'r') as hf:
        data = hf.get('LAT')
        LAT = np.array(data)
        data = hf.get('LON')
        LON = np.array(data)

    return(LAT, LON)
        

def read_dataset_from_file(grid_x:int, grid_y:int, dataset:str,narr_input_dir:str):
    """read a dataset for all years, one coordinate from s3

    Args
        grid_x (int): grid point
        grid_y (int): grid point
        narr_input_dir (str): directory containing NARR files

    Returns:    
        dict[int, float]: A dictionary mapping years to the dataset values at the specified coordinate
    """

    ts_by_year_file = narr_data_filename(dataset, grid_x, grid_y) 
    with open(os.path.join(narr_input_dir, ts_by_year_file), 'r') as f:
        ts_by_year = json.load(f)
        
    return ts_by_year


def read_dataset_from_s3(grid_x:int, grid_y:int, dataset:str, bucket:str, s3_client):
    """read a dataset for all years, one coordinate from s3

    Args:     
        grid_x (int): grid point
        grid_y (int): grid point
        dataset (str): dataset name (PC, WS, WD)
        bucket (str): name of bucket to read from
        s3_client (boto3_client): s3 client created from a valid session

    Returns:    
        dict[int, float]: A dictionary mapping years to the dataset values at the specified coordinate
    """
    
    # ts = time series
    ts_by_year_file = narr_data_filename(dataset, grid_x, grid_y)
    
    try:
        response = s3_client.get_object(Bucket=bucket, Key=ts_by_year_file)
    except Exception as e:
        print(f"Error occurred while fetching object from S3: {e}")
        return None
    
    ts_by_year = response['Body'].read()
    ts_by_year = json.loads(ts_by_year)
    return ts_by_year

def validate_latlon(latval: float, lonval: float, LAT: np.ndarray, LON: np.ndarray) -> bool:
    """determine latitude, longitude params are withing boundary

    Args:
        latval (float): latitude value
        lonval (float): longitude value 
        LAT (np.ndarray): latitude grid
        LON (np.ndarray): longitude grid
    """
    
    if((latval <np.min(np.min(LAT))) or ( latval > np.max(np.max(LAT))) \
    or (lonval < np.min(np.min(LON))) or (lonval > np.max(np.max(LON)))):
        return(False)
    
    return(True)

def path_to_h5_narrfile(yr:str|int, narr_input_dir:str)->str:
    """
    very simple helper to create path to narr file by year
    for use in different parts of the program or for file mgmt
    
    Args:
        yr (int): year of data to read, embedded in filename
        narr_input_dir (str): directory containing NARR files

    Returns:
        str: Path to the NARR file for the specified year.

    """
    
    narr_file_name = f"narr_PSD_{yr}_BC.h5"
    h5f_annual_filename = os.path.join(narr_input_dir, narr_file_name)
    return(h5f_annual_filename)

# read one year WHOLE grid
def read_one_year_grid(yr:str|int,narr_input_dir:str):
    """read one year hf5 file, extra 3 datasets, return whole grid
    Files must be named like narr_PSD_1980_BC.h5
    
    Args:
        yr (int): year of data to read, embedded in filename
        narr_input_dir (str): path to NARR input files
    Returns:
        tuple of np arrays: timeseries values for PC, WD and WS 
    """
    
    yr = str(yr)
    h5f_annual_filename = path_to_h5_narrfile(yr, narr_input_dir)
    h5f = h5py.File(h5f_annual_filename, 'r')
    return(h5f)


# called before and inside the loop by years
# this returns one grid coordinate
def read_one_year(yr:int,idy: int, idx: int, narr_input_dir:str):
    """read one year hf5 file, extra 3 datasets and filter just one coordinate
    Files must be named like narr_PSD_1980_BC.h5
    
    Args:
        yr (int): year of data to read, embedded in filename
        idy (int): index of grid y coordinate (North/South)
        idx (int): index of grid x coordinate (East/West)
        narr_input_dir (str): path to NARR input files
    Returns:
        tuple of np arrays: timeseries values for PC, WD and WS from one grid point, all hours
    """
    

    h5f_annual_filename = path_to_h5_narrfile(yr, narr_input_dir  ) 
    
    # TODO rew-write this to use 
    h5f = h5py.File(h5f_annual_filename, 'r')
    # extract all values for one year
    # previously filtered at read time, like
    #  pc_1year = h5f['pc'][idy,idx,ts:te]
    pc_1year = h5f['PC'][idy,idx,]  #type:ignore
    ws_1year = h5f['WS'][idy,idx,]  #type:ignore
    wd_1year = h5f['WD'][idy,idx,]  #type:ignore
    
    h5f.close()        
    return pc_1year, ws_1year, wd_1year

def latlon_to_gridyx(latval: float, lonval: float, narr_grid_latlon: str = "", source: str = "file") -> tuple:
    """Convert latitude and longitude to grid indices.

    Args:
        latval (float): Latitude value.
        lonval (float): Longitude value.
        narr_grid_latlon (str): For source="file": path to the NARR file.
            For source="s3": S3 key for the file (defaults to NARR_GRID_LATLON_S3).
            If empty, uses environment variables.
        source (str): Where to read from - "file" (local disk) or "s3" (AWS S3).
            Defaults to "file".

    Returns:
        tuple: Grid indices (idx, idy).
    """
    # get coordinate to grid index map arrays
    if not narr_grid_latlon and source == "file":
        load_dotenv()
        narr_grid_latlon = os.getenv('NARR_GRID_LATLON', "")

    LAT, LON = read_narr_lat_lon(narr_grid_latlon, source=source)

    if LAT is not None and LON is not None:
        if not validate_latlon(latval, lonval, LAT, LON):
            Warning("Location outside the Michigan.")
            return (-1, -1)
    else:
        return (-1, -1)
        
    
    # get grid index point for closest grid point using simplified euclidean dist
    distance:np.ndarray = (LAT-latval)**2 + (LON-lonval)**2
    # if input lat and/or lon are equidistant from grid point, this defaults
    # to the most SW corner (I think )
    idy_array, idx_array = np.where(distance==distance.min()) # tuple of arrays
    idy:int=int(idy_array[0]) 
    idx:int=int(idx_array[0]) 
    
    return(idx,idy)
            
def get_narr_timeseries_s3(latval: float, lonval: float, narr_bucket:str|None = None, narr_grid_latlon:str|None = None):
    """Read NARR timeseries data from S3 for a given latitude and longitude.

    Args:
        latval (float): Latitude value.
        lonval (float): Longitude value.
        narr_bucket (str, optional): S3 bucket name. Defaults to None.
        narr_grid_latlon (str | None, optional): Path to the NARR file. Defaults to None.

    Returns:
        dict: A dictionary containing the timeseries data for each dataset.
    """

    load_dotenv()
    if not narr_bucket:
        narr_bucket = os.getenv('NARR_BUCKET', '')
    
    if not narr_grid_latlon: 
        narr_grid_latlon = os.getenv('NARR_FILE', '')
        
    # this will use stuff in .env with no args
    s3_client = get_s3_client()

    (grid_x, grid_y) =  latlon_to_gridyx(latval=latval, lonval=lonval, narr_grid_latlon=narr_grid_latlon)
    
    if grid_x == -1 or grid_y == -1:
        raise ValueError("Grid coordinates could not be determined. Invalid lat/lon.")
    
    narr_timeseries = {}
    for dataset in DATASETS:
         narr_timeseries[dataset]=  read_dataset_from_s3(grid_x, grid_y, dataset, bucket= narr_bucket, s3_client= s3_client)

    return(narr_timeseries)


def save_narr_timeseries_s3_to_local(latval: float, lonval: float, narr_bucket:str, narr_grid_latlon:str, local_filefolder:str)->dict[str, str]:
    """this is used primarily for saving data locally for testing with, given 
    it is 50+ gb of files
    
    Args:
        latval (float): Latitude value.
        lonval (float): Longitude value.
        narr_bucket (str): S3 bucket name.
        narr_grid_latlon (str): Path to the NARR file.
        local_filefolder (str): Path to the local file folder.


    Returns:
        dict[str, str]: A dictionary mapping dataset names to their corresponding 
            local file paths, which are named for grid x,y, not lat/lon
    """
    (grid_x, grid_y) =  latlon_to_gridyx(latval=latval, lonval=lonval, narr_grid_latlon=narr_grid_latlon)
    
    files_written = {}
    
    narr_timeseries = get_narr_timeseries_s3(latval, lonval, narr_bucket, narr_grid_latlon)
    for dataset in DATASETS:
        ts_filename =  narr_data_filename(dataset, grid_x, grid_y)
        local_file_path = os.path.join(local_filefolder, ts_filename)
        with open(local_file_path, "w") as f:
            f.writelines(narr_timeseries[dataset])
            files_written[dataset] = local_file_path
            
    return files_written
 
    
def filter_narr_timeseries(pc, ws, wd, ts:int=0, te:int=2920):
    """filter NARR timeseries data

    Args:
        pc (np.ndarray): Pressure data
        ws (np.ndarray): Wind speed data
        wd (np.ndarray): Wind direction data
        ts (int): time start index default=0, start of data
        te (int): time endindex, default 2920, all data

    Returns:
        tuple: Filtered data (pc, ws, wd).  If using default ts,te, return all data
    """
    return pc[ts:te], ws[ts:te], wd[ts:te]

def prep_dataset_for_fod(ts_by_year: dict[int, float]):
    """convert dictionary of timeseries by year (for one data set) into single
    np array with them all smashed together

    Args:
        ts_by_year (dict[int, float]): dictionary of time series keyed by year

    Returns:
        np.array: time series of floats as expected by FOD 
    """
    
    # if 'numpy' not in sys.modules:
    #     import numpy as np
    
    ts_by_year_nparray = [item for ts in list(ts_by_year.values()) for item in ts] 
    ts_by_year_merged = np.array(ts_by_year_nparray)
    return ts_by_year_merged


######### main reading functions #########

def read_narr_timeseries_json(latval: float, lonval: float, bucket: str|None, narr_grid_latlon: str|None)->dict[str, np.ndarray]:
    """Get FOD data for a given latitude and longitude.

    Args:
        latval (float): Latitude value.
        lonval (float): Longitude value.
        bucket (str | None): S3 bucket name.
        narr_grid_latlon (str | None): Path to the NARR file.

    Returns:
        dict: A tuple of np arrays for use in the FOD model
    """
    
    # a dict of each data set 
    narr_timeseries = get_narr_timeseries_s3(latval=latval, lonval=lonval, narr_bucket=bucket, narr_grid_latlon=narr_grid_latlon)
    fod_data = {}
    for dataset in DATASETS:
        fod_data[dataset] = prep_dataset_for_fod(narr_timeseries[dataset])
    
    # pc, wind_speed, wind_direction
    return fod_data #  (fod_data['pc'], fod_data['ws'], fod_data['wd'])


def read_narr_timeseries_h5(latval: float, lonval: float,narr_input_dir:str, narr_grid_latlon:str)->dict[str, np.ndarray]:
    """read in wind data for all available years  from HDF5 files

    Args:
        latval (float): _description_
        lonval (float): _description_
        narr_input_dir (str, optional): _description_. Defaults to narr_input_dir.
        narr_grid_latlon (str, optional): _description_. Defaults to NARR_INPUT.

    Raises:
        ValueError: _description_
    """

    # note on variable names:I don't know what "PC" stands for so made is pc 
    # pc =?, ws = wind speed, wd = wind direction

    # get coordinate to grid index map arrays
    idx, idy  = latlon_to_gridyx(latval, lonval, narr_grid_latlon)
    
    # move this to a parameter if data is updated
    available_years = list(range(1979,2009,1))
   
    # since all caps vars are for constants
  
    # start the time series arrays by reading the first year, removing it from the list
    yr:int=available_years.pop(0)
    pc, ws, wd = read_one_year(yr=yr, idx=idx, idy=idy, narr_input_dir=narr_input_dir) #type:ignore
    
    # TODO refactor read_one_year to return a dict keyed by DATASETS 
    # and then use store everything in a dictionary and return a dictionary
    # ts[dataset] = np.concatenate(ts[dataset], ts_1year[dataset])
    # etc 
    # return ts
    
    for yr in available_years:
        pc_1year, ws_1year, wd_1year = read_one_year(yr=yr, idx=idx, idy=idy, narr_input_dir= narr_input_dir)
        # note on py2 to 3 conversion: 
        # it was axis=1 in original script but that doesn't work on 1-d arrays
        # axis=0 combines row-wise for 1-d array, which following code uses
        pc=np.concatenate((pc,pc_1year),axis=0) #type:ignore    
        ws=np.concatenate((ws,ws_1year),axis=0) #type:ignore
        wd=np.concatenate((wd,wd_1year),axis=0) #type:ignore
                
    return({'pc': pc, 'ws': ws, 'wd': wd}) 