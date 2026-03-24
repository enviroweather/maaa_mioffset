#!/bin/bash

echo "using python $(which python)"
latval=43.14319
lonval=-84.23689
odor_index=10
# python version of getting time stamp
# from datetime import datetime
# time_stamp = datetime.now().strftime("%H:%M:%S.%f")
# linux 
time_stamp=$(date '+%H:%M:%S.%N')
echo "latval : $latval"
echo "lonval : $lonval"
echo "odor_index : $odor_index"
echo "time_stamp : $time_stamp"
python fod3.py  $latval  $lonval  $odor_index "$time_stamp"

