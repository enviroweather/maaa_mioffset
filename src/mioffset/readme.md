## Michigan Offset - DEVELOPMENT AND TESTING VERSION

This program was created by MSU Enviroweather staff, 

Quickstart for Using the Python program to model odor plumes. 

### background

new_fod.py is M. Kiefer's original code written in Python 2. 

For details about how this works, see full [PDF documentation](../doc/MIOFFSET2018_technicaldocument.pdf). 

The outputs of the program are odor footprint plots and a table of setback distance, 
and the odor footprint as a KML file or a Shapefile for export to GIS applications.


### Setup

**Support Data files**

You must have a copies of NARR wind climatology profiles 
available on the MSU Enviroweather servers. At this time these
are not publicly available.   For Enviroweather staff:

```
MTK 11/22/21:

OFFSET-related NARR data are also stored in /data/ncep/narr/offset
```

NARR data is wind speed, direction and PC for every 3 hours of a 365-d year
1979 - 2008  ( in python that's `range(1979,2009)` )

These are in two formats: 

- HDF5 formatted grid, time series for one year  per file, each file the entire state of MI grid including PC, WS, WD
  The progra must load each file, extract the grid point and combine these
  This format takes less disk space (32gb) but longer time and more RAM to read and process
- (new in 2026) JSON formatted file time series for each grid point for the entire period, as a dictionary
  keyed by year, one file for each PC, WS, WD, stored in folders 'pc/', 'ws/', 'wd/'
  The program needs to load just one of each of these types of files for grid 
  These files take more disk space (50+gb) but load very fast

These file use a grid index system, 
with Lat/Lon coordinates available via `narr_latlon.h5` file

The program can read these file in either a cloud "S3" object store bucket
or in the file system.  

**Configuration**

fod_config.py is a list of variables used by the fod program 
which are imported as constants and must be configured for your 
environment.    Specifically the config has the full path to 
the NARR HDF5 climatology files and the output folder. 

**Installation**

Install Python 3.11 or higher. This is tested with Python 3.13. 

It's highly recommended you create a virtual environment. There are many ways 
to do this, see https://realpython.com/python-virtual-environments-a-primer/

Install the required libraries using PIP for example

`pip install -r requirements.txt`   

This does not have a `conda` environment file currently. 


### Params in Config File 

Configuration now uses the "dot-env" system where configuration settings are in a shell file 
rather than a python file named `.env` and kept out of git.  Open the example config file 
`dot-env-example.txt` fill in the variables and save as `.env`  You don't need to enter the AWS 
credentials to run the system unless you will be using the portion that reads from Cloud 
storage (to be written)


**TIME_FLAG** 

 - 'F' = (default) Full year dataset: 1 Jan - 31 Dec; run program once.
 - 'W' = Warm season dataset: 1 Apr - 31 Oct ; run program once.
 - 'B' = Run program twice, once for 1 Jan - 31 Dec (tfs=1), and a second time, for 1 Apr - 31 Oct.

**NARR_INPUT** full path to single hdf5 file with 2 datasets, LAT and LON, forming a  grid 
for the state of Michigan.  The model was developed for use inside this grid

**NARR_INPUT_LOC** folder with partial file name like "/path/to/narr_PSD_"
The folder has a collection of HDF5 file (extension h5) that are created
in the code to read them all in, from 1979 to 2009, for example  `narr_PSD_1980_BC.h5`

These files have 3 datasets: PC, WD, WS

**OUTPUT_OFFSET_DIR** Folder where output files are written

### Running 

The latest program is fod3.py, tested with Python 3.13 

#### Old-school, just run from the command line

Ensure the python environment is activated

```
cd src/mioffset  # this folder
python fod3.py  latval lonval odor_index time_stamp 
```

where

- latval = decimal latitude within state of Michigan
- lonval = decimal longitude within state of Michigan
- odor_index = value calculated using area of buildings etc. 
- time_stamp = string to add unique value to file name

#### using test run script

From top level of this repository
```
. scripts/fod_test.sh
```

This will write files to folder for output set in the .env file

### Testing with pytest

Install development requirements with `pip install -r dev-requirements.txt` in 
your python environment. 

The package requires access to NARR data so most tests do also. 
The tests currently require both 
accessing NARR wind time series from a file folder and via AWS S3.  
this will be corrected in a future version.  

After activating the environment, from the top level of this repository run 

`pytest tests`

<!-- this is a future feature TBD
Select which method to access data files: 
`pytest --s3 tests` for only S3, 
`pytest --file tests` for only files.  The default 

-->


### Output

Files are written to the folder named in the variable `OUTPUT_OFFSET_DIR` 
in `fod_config.py` 


 - PNG format plot
 - KML file for import into a GIS
 - ESRI Shapefile for import into a GIS, which includes several files
 - zip file with all the files needed for copying the shapefile

These files are named with the timestamp to differentiate the runs, which must
be sent as a command line parameter (see above)




