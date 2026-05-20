"""
narr_data.py — NARR wind-climate data access layer for the MI Odor Print (MIOFFSET) model.

Provides functions to:
  - Locate the nearest NARR grid point for a given latitude/longitude.
  - Read PC (pressure class), WS (wind speed), and WD (wind direction) time-series
    from either local HDF5 files or JSON files stored in AWS S3.
  - Convert raw year-keyed dictionaries into concatenated NumPy arrays ready for
    the FOD model.

Expected environment variables (set via .env / dotenv):
  Grid file location: one of either
    - NARR_GRID_LATLON  — local path to the HDF5 lat/lon reference file (narr_latlon.h5), OR 
    - NARR_GRID_LATLON_S3 — S3 key for the same file when using S3 (requires NARR_BUCKET to be set, also requires AWS credentials,)

  Data file locations: one of either 
    - NARR_DATA_DIR    — aka NARR_H5_DIR local directory containing per-year HDF5 files (narr_PSD_<yr>_BC.h5)
    - NARR_BUCKET       — S3 bucket name holding JSON climate data files (also requires AWS credentials) 
    - NARR_JSON_DIR     — local directory containing per-gridpoint JSON timeseries files;
                      when set, JSON reads use local files instead of S3

  AWS access - if using must have all of 
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, REGION_NAME — standard AWS credentials
"""

from logging import warning
from dotenv import load_dotenv
import numpy as np
import h5py
import os, json

from types_boto3_s3.client import S3Client
from .aws import get_s3_client, read_hdf5_from_s3, check_bucket
from botocore.exceptions import ClientError




# the original HDF5 files each had 3 datasets or types of date
# for the timeseries at each gridpoint: PC = ? WS=Windspeed and WD=Wind Direction
#TODO make these upper case to match original HDF5 datasets
# but ensure that will work throughout the code
DATASETS = ['pc', 'ws', 'wd']
LOCATIONS = ["FILE", "S3"]


# ws, 10, 120
def valid_location(location: str) -> bool:
    """ this is a cheap enum style check that it's one of options 
    this code currently supports
    """
    if type(location) != str:
        return False

    return location.upper() in LOCATIONS


### INDEX data
class GridIndex():
    """class for reading grid x,y converter file from file
    
    typical Usage for local file in this package:   
        grid_file = os.getenv('NARR_GRID_LATLON', "data/narr_latlon.h5")
        grid_index = GridIndex( "narr_latlon.h5") 
        try:
            idx, idy = grid_index(lat, lon)
        except Exception as e:
            warning(f"Error occurred while converting lat/lon to grid indices: {e}")

        # ... use idx,idy in model
        
    
    """
    
    location = "FILE"
    
    def __init__(self, narr_grid_file: str):
        """class for reading the grid file for wind data

        Args:
            narr_grid_file (str): the path to local file OR the key to file in an s3 bucket
            bucket (str, optional): name of S3 bucket Defaults to "" but requires if source
        """

        
        self.narr_grid_file = narr_grid_file  # this is a key for s3
        self._LAT: np.ndarray | None = None
        self._LON: np.ndarray | None = None
        self._load_error: str | None = None
        # Only set the default reader if a subclass hasn't already chosen one.
        # GridIndexS3.__init__ sets _grid_reader before calling super().__init__,
        # so we must not override it here.
        if not hasattr(self, '_grid_reader'):
            self._grid_reader = self._read_narr_grid_file_hdf5
        # try to load the lat/lon data structures for conversion
        self._load_grid_file()


    @property
    def LAT(self) -> np.ndarray | None:
        """Latitude grid array, or None if not yet loaded."""
        return self._LAT

    @property
    def LON(self) -> np.ndarray | None:
        """Longitude grid array, or None if not yet loaded."""
        return self._LON

    @property
    def is_loaded(self) -> bool:
        """True if lat/lon grid arrays have been successfully loaded."""
        return self._LAT is not None and self._LON is not None

    def _check_loaded(self) -> None:
        """Raise RuntimeError if the lat/lon grid data has not been loaded."""
        if not self.is_loaded:
            reason = getattr(self, '_load_error', None)
            detail = f" Reason: {reason}" if reason else ""
            raise RuntimeError(
                f"Grid conversion data was not loaded. "
                f"Check that the grid file path and AWS configuration are correct.{detail}"
            )

    def _load_grid_file(self):
        try:
            return self._grid_reader()
        except Exception as e:
            self._load_error = str(e)
            warning(f"Error occurred while loading grid file using location {self.location} and narr_grid_file {self.narr_grid_file}: {e}")
                
    def _read_narr_grid_file_hdf5(self):
        """
        Read the NARR grid file and extract latitude and longitude arrays.
        
        Returns:
            tuple: A tuple containing the latitude and longitude arrays.
        """
        if not os.path.exists(self.narr_grid_file):
            raise RuntimeError("NARR grid file not found.")        

        with h5py.File(self.narr_grid_file, 'r') as hf:
            data = hf.get('LAT')
            self._LAT = np.array(data)
            data = hf.get('LON')
            self._LON = np.array(data)

        return (self._LAT, self._LON)  
                
    def validate_latlon(self, latval: float, lonval: float) -> bool:
        """determine latitude, longitude params are withing boundary

        Args:
            latval (float): latitude value
            lonval (float): longitude value 
            LAT (np.ndarray): latitude grid
            LON (np.ndarray): longitude grid
        """
        self._check_loaded()

        if((latval <np.min(np.min(self.LAT))) or ( latval > np.max(np.max(self.LAT))) or (lonval < np.min(np.min(self.LON))) or (lonval > np.max(np.max(self.LON)))):  #type:ignore
            return(False)
        
        return(True)

    def latlon_to_gridyx(self, latval: float, lonval: float) -> tuple:
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
        self._check_loaded()

        if not self.validate_latlon(latval, lonval):
            raise ValueError("Location outside the Michigan.")            

        # get grid index point for closest grid point using simplified euclidean dist
        distance:np.ndarray = (self.LAT-latval)**2 + (self.LON-lonval)**2   # type:ignore
        # if input lat and/or lon are equidistant from grid point, this defaults
        # to the most SW corner (I think )
        idy_array, idx_array = np.where(distance==distance.min()) # tuple of arrays
        idy:int=int(idy_array[0]) 
        idx:int=int(idx_array[0]) 

        return(idx,idy)


##################################

class GridIndexS3(GridIndex):
    """
    class for reading grid x,y converter file from file, 
    adapted for reading from S3 instead of file,
    subclass of GridIndex
    
    typical use for S3 file: 

        grid_key = os.getenv("NARR_GRID_LATLON_S3")
        bucket=os.getenv("NARR_BUCKET")
        s3_client = get_s3_client()
        grid_index = GridIndex( narr_grid_file = grid_key, bucket=bucket, s3_client = s3_client )
        try:
            idx, idy = grid_index(lat, lon)
        except Exception as e:
            warning(f"Error occurred while converting lat/lon to grid indices: {e}")
    """
    
    location = "S3"
        
    def __init__(self, narr_grid_file: str, bucket:str, s3_client:S3Client|None = None):
        """initialize grid indexer, reading from s3

        Args:
            narr_grid_file (str): name/key of file in bucket
            bucket (str): name of bucket to use
            aws_client (_type_, optional): an AWS S3 client. Defaults to None.
        """
    
        self.bucket = bucket
        
        if not s3_client:
            try:
                s3_client = get_s3_client()
            except Exception as e:
                raise RuntimeError(f"S3 client initialization failed: {e}")
            
        self.s3_client = s3_client
        
        if not check_bucket(s3_client, self.bucket):
            raise  RuntimeError(f"S3 bucket {self.bucket} invalid or not found")
        
        # class customization: set the method that actually reads the file
        self._grid_reader = self._read_narr_grid_file_s3

        super().__init__(narr_grid_file)
        
    def _read_narr_grid_file_s3(self):
        """
        read in lat,lon for converting lat lon to climatology grid indices
        
        Returns:
            tuple[float]: A tuple containing the latitude and longitude arrays.
        """

        # defensive - check the bucket every time to let user know it's a bucket issue not file issue
        if not check_bucket(s3_client = self.s3_client, bucket_name= self.bucket):
            raise  RuntimeError(f"S3 bucket {self.bucket} invalid or not found")
        
        try:
            # read_hdf5_from_s3 is a generator that yields the open h5py.File
            # and cleans up the temp file in its finally block,which is why we are using a loop
            for hf5 in read_hdf5_from_s3(self.s3_client, bucket=self.bucket, filename=self.narr_grid_file):
                self._LAT = np.array(hf5.get('LAT'))  # type: ignore
                self._LON = np.array(hf5.get('LON'))  # type: ignore
        except Exception as e:
            raise RuntimeError(f"could not get H5 file from S3 {self.narr_grid_file}: {e}")

        return (self._LAT, self._LON)
        


##################################

# TODO 'location' used here and in the grid_index class is a enum with values ['FILE]
# note on variable names:I don't know what "PC" stands for so made is pc 
# pc =?, ws = wind speed, wd = wind direction
class WindData():
    """class to retrieve wind data for FOD model.  It mixes both formats
    JSON/HDF5 and for JSON, can read from disk or from S3. 
    
    
    sample Usage JSON, File:
    grid_file = os.getenv('NARR_GRID_LATLON', "data/narr_latlon.h5")
    grid_index = GridIndex( "narr_latlon.h5") 
    narr_data_dir = os.getenv('NARR_DATA_DIR', "data")
    wind_data = WindData(grid_index, location="FILE", narr_data_dir=narr_data_dir)
    narr_data = wind_data.read_narr_timeseries_json(latval=-83.0, lonval=44.0)
    # send narr_data to FOD model
    
    
    """
    _datasets =  ['pc', 'ws', 'wd']
    
    location:str="FILE"
    
    def __init__(self, grid_index: GridIndex, narr_data_dir:str):
        """_summary_

        Args:
            grid_index (GridIndex): GridIndex class that can translate lat/lon 
                into grid y,x
            narr_data_dir (str): directory that contains the
                per-gridpoint JSON files organised as
                ``<dataset>/<dataset>_<x>_<y>.json``.  

        Raises:
            ValueError: _description_
        """

        self.grid_index = grid_index
        self.narr_data_dir = narr_data_dir
            
        if not os.path.exists(self.narr_data_dir):
            raise ValueError(f"Location is FILE but {self.narr_data_dir} is not found")

    ############### JSON METHODS ##################
    def narr_data_json_filename(self, dataset:str, x:int,y:int )->str:
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

    def read_dataset_json(self,grid_x:int, grid_y:int, dataset:str)->dict[int, np.ndarray]:
        """read a dataset for all years for one coordinate from a JSON file

        Args
            grid_x (int): grid point
            grid_y (int): grid point
            narr_data_dir (str): directory containing NARR files

        Returns:    
            dict[int, float]: A dictionary mapping years to the dataset values at the specified coordinate
        """

        ts_by_year_file = self.narr_data_json_filename(dataset, grid_x, grid_y) 
        try:
            with open(os.path.join(self.narr_data_dir, ts_by_year_file), 'r') as f:
                ts_by_year = json.load(f)
        except Exception as e:
            print(f"Error occurred while fetching {ts_by_year_file}: {e}")
            return {}
            
        return ts_by_year


    def read_narr_timeseries_json(self, latval: float, lonval: float, format = "FOD"):
        """Read NARR timeseries JSON data for a given latitude and longitude.

        Reads from a local directory when *narr_json_dir* is provided (or the
        ``NARR_JSON_DIR`` environment variable is set); otherwise reads from S3.

        Args:
            latval (float): Latitude value.
            lonval (float): Longitude value.

        Returns:
            dict: Year-keyed timeseries for each dataset (``pc``, ``ws``, ``wd``).
                if there is a problem, return empty data (rather than raising an error)
        """
        
        if not self.grid_index.validate_latlon(latval, lonval):
            warning("Invalid latitude or longitude values.")
            return {}

        try:
            (grid_x, grid_y) = self.grid_index.latlon_to_gridyx(latval, lonval)
        except Exception as E: 
            warning("Error occurred while converting lat/lon to grid coordinates.")
            return {}
        
        if grid_x == -1 or grid_y == -1:
            warning("Grid coordinates could not be determined. Invalid lat/lon.")
            return {}


        narr_timeseries = {}

        if not self.narr_data_dir:
            raise ValueError("when using File, Local JSON directory must be specified in NARR_JSON_DIR or as a parameter.")        

        for dataset in self._datasets:
            narr_timeseries[dataset] = self.read_dataset_json(grid_x, grid_y, dataset)
                
        ### the data at this point are useful, keyed by year
        ### but the FOD model doesn't do this, it expects a long list of numbers
        ### just don't have a use case right now for data keyed by year
        if format == "FOD":
            fod_data = {}
            for dataset in self._datasets:
                fod_data[dataset] = self.prep_dataset_for_fod(narr_timeseries[dataset])
            
            return fod_data
        else:
            return narr_timeseries

    
    def prep_dataset_for_fod(self,ts_by_year: dict[int, float])->np.ndarray:
        """convert dictionary of timeseries by year (for one data set) into single
        np array with them all smashed together

        Args:
            ts_by_year (dict[int, float]): dictionary of time series keyed by year as returned from read_narr_timeseries_json

        Returns:
            np.ndarray: time series of floats in a single array,expected by FOD
        """
        ts_by_year_merged = np.concatenate(list(ts_by_year.values()))
        return ts_by_year_merged

    ############### hdf5 METHODS ##################

    def path_to_h5_narrfile(self,yr:str|int)->str:
        """
        very simple helper to create path to narr file by year
        for use in different parts of the program or for file mgmt
        
        Args:
            yr (int): year of data to read, embedded in filename
            narr_data_dir (str): directory containing NARR files

        Returns:
            str: Path to the NARR file for the specified year.

        """

        narr_file_name = f"narr_PSD_{yr}_BC.h5"
        h5f_annual_filename = os.path.join(self.narr_data_dir, narr_file_name)
        return(h5f_annual_filename)

    # read one year WHOLE grid
    def read_one_year_grid(self, yr:str|int):
        """read one year hf5 file, extra 3 datasets, return whole grid
        Files must be named like narr_PSD_1980_BC.h5
        
        Args:
            yr (int): year of data to read, embedded in filename
            narr_data_dir (str): path to NARR input files
        Returns:
            tuple of np arrays: timeseries values for PC, WD and WS 
        """
        
        h5f_annual_filename = self.path_to_h5_narrfile(yr)
        h5f = h5py.File(h5f_annual_filename, 'r')
        return(h5f)


    # called before and inside the loop by years
    # this returns one grid coordinate
    def read_one_year_h5(self,yr:int|str,idy: int, idx: int)->dict[str, np.ndarray]:
        """read one year hf5 file, extra 3 datasets and filter just one coordinate
        Files must be named like narr_PSD_1980_BC.h5
        
        Args:
            yr (int): year of data to read, embedded in filename
            idy (int): index of grid y coordinate (North/South)
            idx (int): index of grid x coordinate (East/West)
        Returns:
            dict[str, np.ndarray]: timeseries values for PC, WD and WS from one grid point, all hours
        """
        
        h5f_annual_filename = self.path_to_h5_narrfile(yr) 
        
        h5f = h5py.File(h5f_annual_filename, 'r')
        # extract all values for one year
        # previously filtered at read time, like
        #  pc_1year = h5f['pc'][idy,idx,ts:te]
        
        ts:dict[str, np.ndarray]= {}
        ts['pc'] = np.array(h5f['PC'][idy,idx,:])   #type:ignore
        ts['ws'] = np.array(h5f['WS'][idy,idx,:])   #type:ignore
        ts['wd'] = np.array(h5f['WD'][idy,idx,:])   #type:ignore

        h5f.close()
        return ts

    def read_narr_timeseries_h5(self, latval: float, lonval: float)->dict[str, np.ndarray]:
        """read in wind data for all available years  from HDF5 files

        Args:
            latval (float): latitude value in decimal degrees (CRS unknown)
            lonval (float): longitude value in decimal degrees (CRS unknown)
            
        Returns: 
            dict[str, np.ndarray]: dictionary of numpy arrays keyed by dataset

        """

        # get coordinate to grid index map arrays
        idx, idy  = self.grid_index.latlon_to_gridyx(latval, lonval)
        
        # move this to a parameter if data is updated
        available_years = list(range(1979,2009,1))
    
            # start the time series arrays by reading the first year, removing it from the list
        yr:int=available_years.pop(0)
    
        # read the first year            
        narr_ts = self.read_one_year_h5(yr=yr, idx=idx, idy=idy) #type:ignore
        # accumulate the rest
        for yr in available_years:
            ts_1year = self.read_one_year_h5(yr=yr, idx=idx, idy=idy)
            # note on py2 to 3 conversion: 
            # it was axis=1 in original script but that doesn't work on 1-d arrays
            # axis=0 combines row-wise for 1-d array, which following code uses
            narr_ts['pc']:np.ndarray = np.concatenate((narr_ts['pc'],ts_1year['pc']),axis=0) #type:ignore    
            narr_ts['ws']:np.ndarray = np.concatenate((narr_ts['ws'],ts_1year['ws']),axis=0) #type:ignore
            narr_ts['wd']:np.ndarray = np.concatenate((narr_ts['wd'],ts_1year['wd']),axis=0) #type:ignore
                    
        return(narr_ts) 


def filter_narr_timeseries(self, ts:dict[str, np.ndarray], tstart:int=0, tend:int=2920)->dict[str, np.ndarray]:
    """simple method filter NARR timeseries data, limit the timeseries the same
    way for each key ()

    Args:
        ts: dictionary of time series
        tstart (int): time start index default=0, start of data
        tend (int): time end index, default 2920, all data we are using right now. 

    Returns:
        tuple: Filtered data (pc, ws, wd).  If using default ts,te, return all data
    """
    
    for key in ts: 
        ts[key] = ts[key][tstart:tend]
    
    return ts

##################################
class WindDataS3(WindData):
    
    location:str = "S3"
    
    def __init__(self, grid_index: GridIndex,  bucket:str, narr_data_dir:str, s3_client:S3Client|None = None):
        """_summary_
            
        Args:
            grid_index (GridIndex): GridIndex class that can translate lat/lon 
                into grid y,x
            bucket (str): S3 bucket to retrieve files from
            narr_data_dir (str): directory that contains the
                per-gridpoint JSON files organised as
                ``<dataset>/<dataset>_<x>_<y>.json``.  

        Raises:
            ValueError: _description_
        """
        
        self.bucket = bucket
        if not s3_client:
            try:
                self.s3_client = get_s3_client()
            except Exception as e:
                raise ValueError(f"Location is S3 but failed to initialize S3 client: {e}")
        else:
            self.s3_client = s3_client
        
        super().__init__(grid_index, narr_data_dir)


    def read_dataset_json(self, grid_x:int, grid_y:int, dataset:str)->dict[int, np.ndarray]:
        """read a dataset for all years, S3 edition
        one coordinate from a JSON file

        Args:     
            grid_x (int): grid point
            grid_y (int): grid point
            dataset (str): dataset name (PC, WS, WD)

        Returns:    
            dict[int, float]: A dictionary mapping years to the dataset values at the specified coordinate

        Raises:
            ValueError: when S3 bucket does not exist or AWS credentials are invalid,
                indicating a configuration problem that the caller must resolve.
        """
        
        # ts = time series
        ts_by_year_file = self.narr_data_json_filename(dataset, grid_x, grid_y)
        
        
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=ts_by_year_file)
            ts_by_year = response['Body'].read()
            ts_by_year = json.loads(ts_by_year)
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code in ('NoSuchBucket', 'InvalidBucketName'):
                raise ValueError(
                    f"S3 bucket '{self.bucket}' not found or invalid. "
                    f"Check NARR_BUCKET configuration."
                )
            elif error_code in ('InvalidClientTokenId', 'AuthFailure',
                                'SignatureDoesNotMatch', 'AccessDenied',
                                'InvalidAccessKeyId'):
                raise ValueError(
                    f"AWS credentials are invalid for bucket '{self.bucket}'. "
                    f"Check AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY."
                )
            else:
                # Data not found (NoSuchKey, etc.) — not a config error, return empty
                print(f"Error occurred while fetching {ts_by_year_file} from S3 bucket {self.bucket}: {e}")
                return {}
        except Exception as e:
            print(f"Error occurred while fetching {ts_by_year_file} from S3 bucket {self.bucket}: {e}")
            return {}
        
        return ts_by_year
   
    def read_one_year_h5(self,yr:int|str,idy: int, idx: int)-> dict[str, np.ndarray]:
        """read one year hf5 file, S3 EDITION
        extra 3 datasets and filter just one coordinate
        Files must be named like narr_PSD_1980_BC.h5
        
        Args:
            yr (int): year of data to read, embedded in filename
            idy (int): index of grid y coordinate (North/South)
            idx (int): index of grid x coordinate (East/West)
            narr_data_dir (str): path to NARR input files
        Returns:
             dict[str, np.ndarray]: timeseries values for PC, WD and WS from one grid point, all hours
        """
        # this is the same for files or for S3
        # for S3, uses the "path" inside the bucket
        h5f_annual_filename = self.path_to_h5_narrfile(yr) 
        ts:dict[str, np.ndarray]= {}
        # using for loop here to work with generator function
        # but there is only on file, which is closed by generator
        for h5f in read_hdf5_from_s3(self.s3_client, self.bucket, h5f_annual_filename):
            ts['pc'] = np.array(h5f['PC'][idy,idx,:])   #type:ignore
            ts['ws'] = np.array(h5f['WS'][idy,idx,:])   #type:ignore
            ts['wd'] = np.array(h5f['WD'][idy,idx,:])   #type:ignore

        return ts    


##################################    

def wind_data_factory(location = "S3", 
                      narr_grid_file:str ="", narr_data_dir:str="", 
                      narr_bucket:str = "", s3_client:S3Client|None = None)->WindData:

    """Factory function to create the appropriate WindData instance based on location.

    Constructs and returns a fully initialised WindData (for local files) or
    WindDataS3 (for S3) object, each paired with the matching GridIndex.

    Args:
        location (str): Where to read data from. Must be ``"S3"`` or ``"FILE"``.
            Defaults to ``"S3"``.
        narr_grid_file (str): Path (or S3 key) to the NARR lat/lon grid HDF5 file
            used to convert lat/lon coordinates to grid indices.
        narr_data_dir (str): Local directory (or S3 prefix) containing the
            per-gridpoint JSON files organised as
            ``<dataset>/<dataset>_<x>_<y>.json``.
        narr_bucket (str): Name of the S3 bucket. Required when
            ``location="S3"``, ignored otherwise.
        s3_client (S3Client | None): An already-initialised boto3 S3 client.
            When ``None`` and ``location="S3"``, a client is created with
            default credentials.

    Returns:
        WindData: A WindData-compatible instance to retrieve wind data.

    Raises:
        RuntimeError: If ``location="S3"`` but the provided client or bucket is
            invalid / unreachable.
        RuntimeError: If ``location`` is not ``"FILE"`` or ``"S3"``.
    """

    if location == "S3":
        if not s3_client and not check_bucket(s3_client, narr_bucket):
            raise RuntimeError(f"requested S3 access but invalid client {s3_client} or bucket {narr_bucket}")

        grid_index = GridIndexS3(narr_grid_file= narr_grid_file, bucket=narr_bucket, s3_client= s3_client)
        wind_data = WindDataS3(grid_index, bucket = narr_bucket, narr_data_dir=narr_data_dir)
    elif location == "FILE":
        grid_index = GridIndex(narr_grid_file)
        wind_data = WindData(grid_index, narr_data_dir)
        
    else:
        raise RuntimeError(f"when getting wind data, location must be FILE or S3, not {location}")
    
    return(wind_data)

##################################
# TEMPORARY FUNCTIONS TO CONVERT DATA


def save_narr_timeseries_s3_to_local(latval: float, lonval: float, narr_bucket:str, narr_grid_latlon:str, local_filefolder:str)->dict[str, str]:
    """this is used primarily for saving one of these files locally for testing 
    as one-off function and not needed as part of the FOD model run
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
    
    grid_index = GridIndex("narr_latlon.h5", location="S3", bucket=narr_bucket)
    (grid_x, grid_y) = grid_index.latlon_to_gridyx(latval, lonval)
    
    files_written = {}   
     
    wind_data = WindDataS3(grid_index, bucket = narr_bucket, )    
    narr_timeseries = wind_data.read_narr_timeseries_json(latval, lonval, format="not_fod")
    
    for dataset in wind_data._datasets:
        ts_filename =  wind_data.narr_data_json_filename(dataset, grid_x, grid_y)
        local_file_path = os.path.join(local_filefolder, ts_filename)
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)
        with open(local_file_path, "w") as f:
            json.dump(narr_timeseries[dataset], f)
            files_written[dataset] = local_file_path
        
    return files_written

def save_narr_timeseries_test_data(TEST_MI_LAT = 44.0, TEST_MI_LON = -83.0, save_folder = "tests/data"):
    from dotenv import load_dotenv
    load_dotenv()
    narr_bucket = os.getenv("NARR_BUCKET", "")
    narr_grid_latlon = os.getenv("NARR_GRID_LATLON", "")
    files_saved = save_narr_timeseries_s3_to_local(TEST_MI_LAT, TEST_MI_LON, narr_bucket, narr_grid_latlon, save_folder )
    return files_saved