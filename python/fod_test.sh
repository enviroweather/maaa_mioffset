#!/bin/bash

echo "using python $(which python)"
FILE_PREFIX="MIOFFSET_PY3"
echo $FILE_PREFIX

# values from original config file
latval=43
lonval=-84

odor_index=10

# this is just used for the file prefix of the output
time_stamp=$FILE_PREFIX # "$(date '+%H_%M_%S_%N')"
echo "latval : $latval"
echo "lonval : $lonval"
echo "odor_index : $odor_index"
echo "time_stamp : $time_stamp"
python fod3.py  $latval  $lonval  $odor_index "$time_stamp"

## test 

# let's compare file
LEGACY_FOLDER=../../testing/legacy
PY3_FOLDER=../../testing/py3

# put output from tmp into a testing directory
# mkdir -p $PY3_FOLDER
cp  ../tmp/${FILE_PREFIX}* $PY3_FOLDER


echo "Differences between LEGACY and PY3 table"
LEGACY_TABLE="${LEGACY_FOLDER}/MIOFFSET_LEGACY_table_setbackdistance_FY.txt"
PY3_TABLE="${PY3_FOLDER}/MIOFFSET_PY3_table_setbackdistance_FY.txt"
git diff --no-index $LEGACY_TABLE $PY3_TABLE

#echo "Differences between KML files"
#LEGACY_KML="${LEGACY_FOLDER}/MIOFFSET_LEGACY_kml_footprint_FY.kml"
#PY3_KML="${PY3_FOLDER}/MIOFFSET_PY3_kml_footprint_FY.kml"
#git diff --no-index $LEGACY_KML $PY3_KML 
