## Michigan Offset

Quickstart for Using the Python program: fod3.py 

### background

new_fod.py is M. Kiefer's original code written in Python 2. 

For details about how this works, see full PDF documentation. 
This readme is the basic quick start to enable testing of 
the python code and not if it's correct.  


### Running 

fod_config.py is a list of variables used by the fod program 
which are imported as constants. 


**Command line params**

`fod3.py  latval lonval odor_index time_stamp `

where

- latval = decimal latitude within state of Michigan (LP?)
- lonval = decimal longitude within state of Michigan (LP?)
- odor_index = ?
- time_stamp = ?

### Params in Config File 

TIME_FLAG 

 - 'F' = (default) Full year dataset: 1 Jan - 31 Dec; run program once.
 - 'W' = Warm season dataset: 1 Apr - 31 Oct ; run program once.
 - 'B' = Run program twice, once for 1 Jan - 31 Dec (tfs=1), and a second time, for 1 Apr - 31 Oct.

NARR_INPUT = single file named 

NARR_INPUT_LOC = folder with partial file name like "/path/to/narr_PSD_"
The folder has a collection of HDF5 file (extension h5) that are created
in the code to read them all in, from 1979 to 2009, for example  `narr_PSD_1980_BC.h5`

note, there is another copy that appears identical
```
MTK 11/22/21:

OFFSET-related NARR data are also stored in /data/ncep/narr/offset
```



#### Config file params that are not used in the program

- NARR_DATA_FOLDER (the full path to the data files in this folder are used instead)


```
LOC_FLAG = 'L' 
NUM_OF_SOURCES = '3'
SOURCE_1 = "1,100000,6,0.1"
SOURCE_2 = "2,100000,42,0.5"
SOURCE_3 = "3,5000,28,0.5"
TIME_FLAG = 'F' 
```



