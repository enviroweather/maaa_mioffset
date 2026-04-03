#!/bin/bash

echo "using python $(which python)"
FILE_PREFIX="MIOFFSET_PY3"
echo $FILE_PREFIX

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

# put output from tmp into a testing directory
mkdir -p ../../testing/py3
mv  ../tmp/${FILE_PREFIX}* ../../testing/py3/
LEGACY_TABLE="../../testing/legacy/MIOFFSET_LEGACY_table_setbackdistance_FY.txt"
PY3_TABLE="../../testing/py3/MIOFFSET_PY3_table_setbackdistance_FY.txt"
echo "Differences between LEGACY and PY3 table"
git diff --no-index $LEGACY_TABLE $PY3_TABLE
