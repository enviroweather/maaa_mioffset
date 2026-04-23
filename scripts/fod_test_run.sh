#!/bin/bash

echo "using python $(which python)"

# values from original config file
latval=43
lonval=-84
odor_index=10
FILE_PREFIX="MIOFFSET_PY3"

# previously timestamp just used for the file prefix of the output
# time_stamp="$(date '+%H_%M_%S_%N')"
echo $FILE_PREFIX
echo "latval : $latval"
echo "lonval : $lonval"
echo "odor_index : $odor_index"
echo "time_stamp : $time_stamp"
python src/mioffset/fod3.py  $latval  $lonval  $odor_index "$FILE_PREFIX"


