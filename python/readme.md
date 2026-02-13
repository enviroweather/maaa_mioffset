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

**Config inputs**

```
LOC_FLAG = 'L' 
NUM_OF_SOURCES = '3'
SOURCE_1 = "1,100000,6,0.1"
SOURCE_2 = "2,100000,42,0.5"
SOURCE_3 = "3,5000,28,0.5"
TIME_FLAG = 'F' 
```



