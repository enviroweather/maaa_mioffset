#!/usr/bin/env python3

# fod3.py python3 version of new_fod.py
#########################################################################	
#
#	Originally Developed by:
#
#	Dr. Michael T. Kiefer, 
#   Department of Geography, Environment, and Spatial Sciences
#	Michigan State University 
#   Modified by 
#
#	alterations for using in PHP application by Tracy Aichle
#   June 2026 (Pat Bills, MSU ICER)
#     +/- organized into distinct modules to minimize inputs needs for cloud functions
#     + distinction between mioffset for web (dictionary and GeoJSON only) and for "report"
#       which has plots and GIS Files if and when needed to make web site very responsive
#   May 2026 (Pat Bills, MSU ICER)
#     + added methods create other map and image formats for API outputs
#     + split functions to 1) create object 2) save to disk OR 3) convert for api
#     + use new wind data factory method for flex file location (s3 vs file)
#     + functions to save KML and SVG for api use, and convert to Base64 for JSON compatibility
#     - move main 'runners' into mioffset.py - this is no longer an executable script
#     - move Matplotlib plotting functions into setback_plots.py to keep this file lean
#   April 2026 refactoring 
#     + refactored into distinct functions for optimization and testing 
#     + functions are split into modules (narr_data.py, etc)
#     + configured to use .env for configuration instead of fod_config.py
#     + transformed data from whole-grid by year files into whole-timme series
#       by grid-point for very fast data reading (suitable for cloud)
#     + works with AWS S3 object storage for time series files above
#     
#   March 2026: Python 3 untested by working version (Pat Bills, MSU     ICER)
#     + various python 2 to 3 conversions
#     + removed imports and code that is no longer used
#     + np types (np.float) are deprecated
#     + replacement for deprecated distance method
#     + fixed several issues with numpy,pyshp, and file paths
#     + removed unused comments and code 
#   10 July 2017
#	+ Two changes to static polar plots:
#		- Changed axes scaling to 80%
#		- Replaced white background with transparent background
#
#
########################################################################



# #------------------------Imports-------------------------

# from python stdlib
from os import path, getenv    
import logging

# environment
from dotenv import load_dotenv
load_dotenv()

# for model
from math import pow
from numpy import ndarray, array, copy, round, arange, empty, random, zeros, histogram, median, sum, where
from numpy import min as np_min  # to not mask python min
from numpy import max as np_max  
from geopy.distance import geodesic

# for mapping
from geopy import Point

#----------------Variable definitions/Glossary-------------------------
# wc: Frequency of each wind-stability class (float)
# f:  Wind-stability class that occurs closest to but not 
#     greater than 5%, 3%, and 1.5% of the time (integer)
# D:  Setback distance, computed as a function of wind 
#     stability class using OFFSET look-up tables (float)
# E:  Total Odor Emission Factor (float)
# FY: full year
# ws: wind_speed: W? season
# wd: wind_direction
# 
#----------------------------------------------------------------------

### indication that this is not for final use
logging.log(logging.INFO, "MIOFFSET DEVELOPMENT VERSION - NOT FOR PRODUCTION USE")



def setback_text_table(D: ndarray)->str:
    """ create Special special version of D array, with three "N" rows at top of table and other 
    two "N" rows at bottom of table.  This is done in order to match how it 
    is presented in existing MI Odor Print excel spreadsheet.
    
    Args:
        D (ndarray): offset values, must have shape 80,3
    
    Returns:
        str: lines of table suitable for printing in fixed width font
    """
    
    wlab=array(
       ['N','-','-','-','-','NNE','-','-','-','-','NE','-','-','-','-', \
	    'ENE','-','-','-','-','E','-','-','-','-','ESE','-','-','-','-', \
	    'SE','-','-','-','-','SSE','-','-','-','-','S','-','-','-','-', \
	    'SSW','-','-','-','-','SW','-','-','-','-','WSW','-','-','-','-', \
	    'W','-','-','-','-','WNW','-','-','-','-','NW','-','-','-','-', \
	    'NNW','-','-','-','-']
                  )
    
    # Special special version of D array, with three "N" rows at top of table and other 
    # two "N" rows at bottom of table.  This is done in order to match how it 
    # is presented in existing MI Odor Print excel spreadsheet.
    Dtbl=copy(D)
    Dtbl[1:79,:]=D[0:78,:]
    Dtbl[0]=D[79,:]
    
    # round to 2 places
    d5 = round(Dtbl[:,0],2)   # 5%
    d3 = round(Dtbl[:,1],2)   # 3%
    d15 = round(Dtbl[:,2],2)  # 1.5%
    
    header_lines = [
        f"{'Toward Distance_in_Miles':>6}",
        f"{'       5%   3%   1.5%':>21}",
    ]
    
    table_lines = [
        f"{label:>6s} {v5:4.2f} {v3:4.2f} {v15:4.2f}"
        for label, v5, v3, v15 in zip(wlab, d5, d3, d15)
    ]
    
    table_text = "\n".join(header_lines + table_lines) + "\n"
    
    return(table_text)
    

def fod_plot_to_ll(D, lat:float, lon:float)->ndarray:
    """convert setback distance output from FOD model into a the 
    lat, lon coordinates of set-back radius from the 
    center point for placing on a map 

    Args:
        D (_type_): output from 
        lat (float): latitude of center point
        lon (float): longitude of center point
    """
    
    dbin = arange(4.5, 364.5, 4.5) #redefined with 4.5 degree bins.        
    
    LL:ndarray = empty((81,3,2), dtype=float, order='F')        
    
    for d in range(0,dbin.size):
        for p in range(0,3):
            LL[d,p,1]=geodesic(miles=D[d,p]).destination(Point(lat, lon), dbin[d]).latitude
            LL[d,p,0]=geodesic(miles=D[d,p]).destination(Point(lat, lon), dbin[d]).longitude
    
    # does this rotate or flip it?
    LL[80,:,:]=LL[0,:,:]
    
    return(LL)





###### MAIN MODEL 
        
def fod_model(pc: ndarray, wind_speed:ndarray, wind_direction:ndarray, odor_index:int):
    """calculates an aray of setback distances in miles given wind
    characteristics for a coordinate in the state of Michigan 

    Args:
        pc (ndarray): time series of ?
        wind_speed (ndarray): time series of wind speeds
        wind_direction (ndarray): time series of wind directions
        odor_index (int): odor index calculated from building size and type
    Returns:
        array 3 sets of 80 values (shape = (80,3)), 5% 3%, 1.5% setback distance
    """

    # renamed for comparability with original code
    E = odor_index
    #-----------------------Wind direction processing------------------------
    
    indx=random.RandomState(seed=8675309).permutation(wind_direction.size)
    wd4=[90,180,270,360]
    i4=zeros((wind_direction.size,4), dtype=int, order='F')
    h,x = histogram(wind_direction,bins=arange(0,361,1))
    for m in range(0,4):
        if(m<3):
            a1=median(h[wd4[m]-1-6:wd4[m]-1-2])
            a2=median(h[wd4[m]-1+2:wd4[m]-1+6])
        else:
            a1=median(h[wd4[m]-1-6:wd4[m]-1-2])
            a2=median(h[1:5])
        cap=round((a1+a2)/2)
        I=wind_direction==wd4[m];c=1;i4[:,m]=I.astype(int)
        for t in range(0,i4[:,0].size):
            tr=indx[t]
            if((I[tr].astype(int)==1) & (c<=cap)):
                i4[tr,m]=0
                c=c+1	
    Isum=sum(i4,1)
    I1=Isum>0
    I2=I1.astype(int)
    wind_directionds=copy(wind_direction)
    wind_directionds[I2==1]=-999

    #--------Footprint preliminary step 1: compute "windstar chart"----------
    dbin=arange(11.25,360,22.5)
    wc = zeros((16,6), dtype=float, order='F')
    for d in range(0,dbin.size):
        if (d == 0):									
            pcs = pc[(wind_directionds >= dbin[15]) | ((wind_directionds < dbin[0]) & (wind_directionds >= 0))]
            wind_speeds = wind_speed[(wind_directionds >= dbin[15]) | ((wind_directionds < dbin[0]) & (wind_directionds >= 0))]		
        else:
            pcs = pc[(wind_directionds >= dbin[d-1]) & (wind_directionds < dbin[d])]
            wind_speeds = wind_speed[(wind_directionds >= dbin[d-1]) & (wind_directionds < dbin[d])]				
        wc[d,0] = float((((pcs == 6) & (wind_speeds <= 1.3)).sum()))/ float((wind_directionds>=0).sum())*100
        wc[d,1] = wc[d,0] + float((((pcs == 6) & (wind_speeds > 1.3) & (wind_speeds <= 3.1)).sum()))/ float((wind_directionds>=0).sum())*100
        wc[d,2] = wc[d,1] + float((((pcs == 5) & (wind_speeds <= 3.1)).sum()))/ float((wind_directionds>=0).sum())*100
        wc[d,3] = wc[d,2] + float((((pcs == 5) & (wind_speeds > 3.1) & (wind_speeds <= 5.4)).sum()))/ float((wind_directionds>=0).sum())*100
        wc[d,4] = wc[d,3] + float((((pcs == 4) & (wind_speeds <= 5.4)).sum()))/ float((wind_directionds>=0).sum())*100
        wc[d,5] = wc[d,4] + float((((pcs == 4) & (wind_speeds > 5.4) & (wind_speeds <= 8.0)).sum()))/ float((wind_directionds>=0).sum())*100


    #------Footprint preliminary step 2: identify 1.5%,3%,5% classess--------
    f = zeros((5*dbin.size,3), dtype=int, order='F')
    for d in range (0,dbin.size):
        tem=round(wc[d,:],2)
        if(d==0):
            f[37:42,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[37:42,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[37:42,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==1):
            f[42:47,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[42:47,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[42:47,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==2):
            f[47:52,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[47:52,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[47:52,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==3):
            f[52:57,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[52:57,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[52:57,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==4):
            f[57:62,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[57:62,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[57:62,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==5):
            f[62:67,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[62:67,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[62:67,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
            f[67:72,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
        elif(d==6):
            f[67:72,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[67:72,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==7):
            f[72:77,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[72:77,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[72:77,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==8):
            f[77:80,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[77:80,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[77:80,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
            f[0:2,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[0:2,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[0:2,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==9):
            f[2:7,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[2:7,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[2:7,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==10):
            f[7:12,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[7:12,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[7:12,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==11):
            f[12:17,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[12:17,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[12:17,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==12):
            f[17:22,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[17:22,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[17:22,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==13):
            f[22:27,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[22:27,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[22:27,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==14):
            f[27:32,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[27:32,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[27:32,0]=np_min(where(tem==np_max(tem[tem<=5])))+1
        elif(d==15):
            f[32:37,2]=np_min(where(tem==np_max(tem[tem<=1.5])))+1
            f[32:37,1]=np_min(where(tem==np_max(tem[tem<=3])))+1
            f[32:37,0]=np_min(where(tem==np_max(tem[tem<=5])))+1


    #-------Footprint preliminary step 3: compute setback distance (D)-------
    D = zeros((5*dbin.size,3), dtype=float, order='F')
    for d in range (0,5*dbin.size):
        for p in range (0,3):
            if (f[d,p] == 1):
                D[d,p]=0.1181*pow(E,0.5132) # Class 1
            elif (f[d,p] == 2):
                D[d,p]=0.0634*pow(E,0.5366) # Class 2
            elif (f[d,p] == 3):
                D[d,p]=0.0399*pow(E,0.5397) # Class 3   
            elif (f[d,p] == 4):
                D[d,p]=0.0242*pow(E,0.5844) # Class 4   
            elif (f[d,p] == 5):  
                D[d,p]=0.0175*pow(E,0.5827) # Class 5
            elif (f[d,p] == 6):
                D[d,p]=0.0101*pow(E,0.6264) # Class 6  
                
    return(D) 

def fod2dict(D:ndarray)->dict[str, list[float]]:
    """convert output of FOD model from Numpy array to python dict, one
    for each column.  This is to help convert to JSON to return via an API

    Args:
        D (ndarray): output from fod_model, 80 rows, 2 columns

    Returns:
        dict[str, list[float]]: same date, but one key for each column, keys named by what they are
    """
    return {'5percent':D[:,0].tolist(), '3percent':D[:,1].tolist(), '1.5percent':D[:,2].tolist()}


