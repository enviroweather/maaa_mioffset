
# FOD config for running on current HPCC arrangement
#######
# HDF5 input data files
# relative to this py 
BASE_DIR = "/mnt/research/ICER-RSE/clients/enviroweather/mioffset"
NARR_INPUT = BASE_DIR + "/h5/narr_latlon.h5" 
NARR_INPUT_DIR = BASE_DIR + "/h5/" 

NARR_INPUT_LOC = BASE_DIR + "/h5/narr_PSD_" 


####
# base location to store output files
OUTPUT_OFFSET_DIR = '../tmp/'   # This is needed for creating the zip file; It is relative to the executable 
# used to save shapefile zip only.  for now set it to be the same.  simplify this later 
#
OUTPUT_LOCATION = OUTPUT_OFFSET_DIR


#####
# # files and folders used to save output from script 
# OUT_IMG_3_1_FY = OUTPUT_OFFSET_DIR + "image_footprint_3inone_FY.png" 

# OUT_IMG_3_1_WS = OUTPUT_OFFSET_DIR + "image_footprint_3inone_WS.png" 

# OUT_IMG_FY = OUTPUT_OFFSET_DIR + "image_footprint_FY.png" 

# OUT_IMG_WS = OUTPUT_OFFSET_DIR + "image_footprint_WS.png" 

# SETBACK_FY = OUTPUT_OFFSET_DIR + 'table_setbackdistance_FY.txt' 

# SETBACK_WS = OUTPUT_OFFSET_DIR + 'table_setbackdistance_WS.txt' 

# SAVE_FOOTPRINT_FY = OUTPUT_OFFSET_DIR + "kml_footprint_FY.kml" 

# SAVE_FOOTPRINT_WS = OUTPUT_OFFSET_DIR + "kml_footprint_WS.kml" 

# SHAPE_SOURCE_FY = OUTPUT_OFFSET_DIR + 'shp_source_FY' 

# SHAPE_SOURCE_WS = OUTPUT_OFFSET_DIR + 'shp_source_WS' 

# SHAPE_FOOTPRINT_FY = OUTPUT_OFFSET_DIR + 'shp_footprint_FY' 

# SHAPE_FOOTPRINT_WS = OUTPUT_OFFSET_DIR + 'shp_footprint_WS' 



#### 
# url for map making
PLACE_MARK = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png' 


########
# unused
# ?
INPUT_FILE = "/home/web-ewx/webdir/legacy/mioffset/footprint_input.txt" 
# the NARR files are explicitly named in the fod3.py code, so this is not used
# however, setting it for this config
# NARR_DATA_FOLDER = BASE_DIR + "/h5/" 

# this _was_ used to identify the folder where old files were to be deleted
# but the code to delete the existing files is commented out
# RM_OUTPUT_FILES = "/home/web-ewx/webdir/legacy/mioffset/tmp" 

########
# program paramaters defaults/testing?  unknown
# Eventually, the values below will all be passed by the web page, thus we will be able to comment them out 

LOC_FLAG = 'L' 
NUM_OF_SOURCES = '3'
SOURCE_1 = "1,100000,6,0.1"
SOURCE_2 = "2,100000,42,0.5"
SOURCE_3 = "3,5000,28,0.5"
TIME_FLAG = 'F' 

