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
#   
#   March 2026: Python 3 untested by working version (Patrick Bills, MSU ICER)
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

print("MIOFFSET DEVELOPMENT VERSION ONLY - NOT FOR PRODUCTION USE")

# #------------------------Imports-------------------------

import numpy as np
import math
import h5py
import sys, os
import matplotlib
# matplotlib.use('Agg') is necessary when the script is called from a PHP application
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import time
import zipfile
import matplotlib.cm as cm
from geopy import Point
# vincenty method is deprecated, use geodesic method instead
from geopy.distance import geodesic
import scipy.io as sio
import simplekml
import shapefile


DEBUG=os.getenv('DEBUG', True)

def debug_print(x):
    if DEBUG:
        print(x)

def add_prefix_to_filename(full_path: str, prefix: str = "", prefix_sep: str = "_") -> str:
    """Return full_path with prefix applied only to the filename part."""
    
    if prefix[-1] != prefix_sep:
        prefix += prefix_sep 

    dir_name, file_name = os.path.split(full_path)
    prefixed_name = prefix + file_name
    if dir_name:
        return os.path.join(dir_name, prefixed_name)
    return prefixed_name

#------------------------ Config -------------------------

# just read in all config, it's our file
# TODO, after script is working, convert explicit import 
from fod_config import *

# note that these don't appear to be used in this 
# but are perhaps used in the FE to calculate odor_index
#--------------------------Variable definitions--------------------------
# wc: Frequency of each wind-stability class (float)
# f:  Wind-stability class that occurs closest to but not 
#     greater than 5%, 3%, and 1.5% of the time (integer)
# D:  Setback distance, computed as a function of wind 
#     stability class using OFFSET look-up tables (float)
# E:  Total Odor Emission Factor (float)
#------------------------------------------------------------------------


def read_narr_lat_lon( narr_file:str = NARR_INPUT):
    """read in lat,lon for converting lat lon to climatology grid indices

    Args:
        narr_file (str, optional): string full path to the NARR input file. 
            Defaults to NARR_INPUT.
    """
    with h5py.File(narr_file,'r') as hf:
        data = hf.get('LAT')
        LAT = np.array(data)
        data = hf.get('LON')
        LON = np.array(data)

    return(LAT, LON)
        

def validate_latlon(latval: float, lonval: float, LAT: np.ndarray, LON: np.ndarray) -> bool:
    """determine latitude, longitude params are withing boundary

    Args:
        latval (float): latitude value
        lonval (float): longitude value 
        LAT (np.ndarray): latitude grid
        LON (np.ndarray): longitude grid
    """
    
    if((latval <np.min(np.min(LAT))) or ( latval > np.max(np.max(LAT))) \
    or (lonval < np.min(np.min(LON))) or (lonval > np.max(np.max(LON)))):
        return(False)
    
    return(True)


def read_narr(latval: float, lonval: float, LAT: np.ndarray, LON: np.ndarray, ts: int, te: int):
    """get wind climatology for all years for point

    Args:
        latval (float): latitude value
        lonval (float): longitude value
        LAT (np.ndarray): latitude grid
        LON (np.ndarray): longitude grid
        ts (int): start time index
        te (int): end time index
    """
    
    distance:float = (LAT-latval)**2 + (LON-lonval)**2
    idy, idx = np.where(distance==distance.min())
    idy=int(idy[0]);idx=int(idx[0]);


    for yr in range(1979,2009,1):
        h5f = h5py.File(NARR_INPUT_LOC + str(yr) + '_BC.h5','r')
        PC1 = h5f['PC'][idy,idx,ts:te]
        WS1 = h5f['WS'][idy,idx,ts:te]
        WD1 = h5f['WD'][idy,idx,ts:te]
        if (yr == 1979):
            PC=PC1
            WS=WS1
            WD=WD1
        else:
            # py2 to 3 conversion: 
            # it was axis=1 in original script but that doesn't work on 1-d arrays
            # axis=0 combines row-wise for 1-d array, which following code uses
            PC=np.concatenate((PC,PC1),axis=0)
            WS=np.concatenate((WS,WS1),axis=0)
            WD=np.concatenate((WD,WD1),axis=0)
                
    return(PC, WS, WD)


def write_footprint_plots(D: np.ndarray, E: float, topt: int, output_offset_dir: str, file_prefix: str=""):
    """create wind plots from model and save as PNGs

    Args:
        D (np.ndarray): Setback distance, computed as a function of wind stability class using OFFSET look-up tables (float)
        E (float): Total Odor Emission Factor (float)
        topt (int): time option
        output_offset_dir (str): folder to save these in
        file_prefix (str): optional prefix to add to file names to make them unique
    """
    #------Plot footprint on polar axes with standard white background-------

    dbin = np.arange(4.5, 364.5, 4.5) #redefined with 4.5 degree bins.
    #   1.  First image: all three footprints (1.5%,3%,5%)
    
    ax = plt.subplot(111, projection='polar')
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    theta=np.radians(dbin)
    ax.grid(True);ax.yaxis.grid(lw=1, ls='--');
    ax.plot(theta, D[:,0],'r-',theta, D[:,1],'b-',theta, D[:,2],'g-',lw=2.5)
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,0],D[0,0]],'r',lw=2.5,label='5%')
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,1],D[0,1]],'b',lw=2.5,label='3%')
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,2],D[0,2]],'g',lw=2.5,label='1.5%')
    ax.set_xticks(np.arange(0,2*math.pi,2*math.pi/80))
    ax.set_xticklabels(['N','','','','','NNE','','','','','NE',
    '','','','','ENE','','','','','E','','','','','ESE',
    '','','','','SE','','','','','SSE','','','','','S',
    '','','','','SSW','','','','','SW','','','','','WSW',
    '','','','','W','','','','','WNW','','','','','NW',
    '','','','','NNW','','','',''])

    if(1.1*np.max(D[:,2]) >= 0.5):
        yl=np.ceil(1.1*np.max(D[:,2]))
        ax.set_ylim(0,yl)
        ax.set_yticks(np.linspace(0,yl,num=11))
        ax.set_yticklabels(np.round(np.linspace(0,yl,num=11),1))
    else:
        yl=0.5 # Small setback distance
        ax.set_ylim(0,yl)
        ax.set_yticks(np.linspace(0,yl,num=6))
        ax.set_yticklabels(np.round(np.linspace(0,yl,num=6),1))
    position=335
    ax._r_label_position._t = (position, 0)
    ax._r_label_position.invalidate()
    ax.xaxis.set_tick_params(labelsize=14)
    ax.yaxis.set_tick_params(labelsize=14,labelcolor='black')
    if(topt == 1):
        ax.set_title('MI Odor Print - Distance in Miles' + '\n' \
        + '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n', va='bottom')
    elif(topt == 2):
        ax.set_title('MI Odor Print - Distance in Miles' + '\n' \
        + '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n', va='bottom')
    # Shrink current axis by 20%
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height * 0.8])

    # Put a legend to the right of the current axis
    lg=ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.25))
    lg.draw_frame(False)
    
    if(topt == 1):
        plot_file_name = "image_footprint_3inone_FY.png"         
    elif(topt == 2):
        plot_file_name=  "image_footprint_3inone_WS.png" 
        
    footprints_plot_file_path = add_prefix_to_filename(os.path.join(output_offset_dir, plot_file_name), file_prefix)
    plt.savefig(footprints_plot_file_path, format='png', dpi=300, transparent=True)
    debug_print(f"saved {footprints_plot_file_path}")
    plt.close()
    
    
    # ---------  2.   Second image: 5% footprint only.
    ax = plt.subplot(111, projection='polar')
    ax.set_theta_zero_location('N')
    ax.set_theta_direction(-1)
    theta=np.radians(dbin)
    ax.grid(True);ax.yaxis.grid(lw=1, ls='--');
    ax.plot(theta, D[:,0],'r-',lw=2.5)
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,0],D[0,0]],'r',lw=2.5,label='5%')
    ax.set_xticks(np.arange(0,2*math.pi,2*math.pi/80))
    ax.set_xticklabels(['N','','','','','NNE','','','','','NE',
    '','','','','ENE','','','','','E','','','','','ESE',
    '','','','','SE','','','','','SSE','','','','','S',
    '','','','','SSW','','','','','SW','','','','','WSW',
    '','','','','W','','','','','WNW','','','','','NW',
    '','','','','NNW','','','',''])

    if(1.1*np.max(D[:,0]) >= 0.5):
        yl=np.ceil(1.1*np.max(D[:,0]))
        ax.set_ylim(0,yl)
        ax.set_yticks(np.linspace(0,yl,num=11))
        ax.set_yticklabels(np.round(np.linspace(0,yl,num=11),1))
    else:
        yl=0.5 # Small setback distance
        ax.set_ylim(0,yl)
        ax.set_yticks(np.linspace(0,yl,num=6))
        ax.set_yticklabels(np.round(np.linspace(0,yl,num=6),1))
    position=335
    ax._r_label_position._t = (position, 0)
    ax._r_label_position.invalidate()
    ax.xaxis.set_tick_params(labelsize=14)
    ax.yaxis.set_tick_params(labelsize=14,labelcolor='black')
    if(topt == 1):
        ax.set_title('MI Odor Print - Distance in Miles' + '\n' \
        + '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n', va='bottom')
    elif(topt == 2):
        ax.set_title('MI Odor Print - Distance in Miles' + '\n' \
        + '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n', va='bottom')
    # Shrink current axis by 20%
    box = ax.get_position()
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height * 0.8])

    # Put a legend to the right of the current axis
    lg=ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.25))
    lg.draw_frame(False)

    if(topt == 1):
        plot_file_name = "image_footprint_FY.png"
    elif(topt == 2):
        plot_file_name = "image_footprint_WS.png"

    five_percent_plot_file_path = add_prefix_to_filename(os.path.join(output_offset_dir, plot_file_name), file_prefix)
    plt.savefig(five_percent_plot_file_path, format='png', dpi=300, transparent=True)
    plt.close()

    debug_print(f"saved {five_percent_plot_file_path}")

    return(footprints_plot_file_path, five_percent_plot_file_path)



def write_setback_text_table(text_file_name: str, D: np.ndarray):
    """write text file of set-back distances in tabular form by direction

    Args:
        text_file_name (str): file name to save the table as
        D (np.ndarray): array of setback distances
        
    Returns:
        str: file name that was saved
    """ 
    
    wlab=np.array(['N','-','-','-','-','NNE','-','-','-','-','NE','-','-','-','-', \
    'ENE','-','-','-','-','E','-','-','-','-','ESE','-','-','-','-', \
    'SE','-','-','-','-','SSE','-','-','-','-','S','-','-','-','-', \
    'SSW','-','-','-','-','SW','-','-','-','-','WSW','-','-','-','-', \
    'W','-','-','-','-','WNW','-','-','-','-','NW','-','-','-','-', \
    'NNW','-','-','-','-'])

    # Special special version of D array, with three "N" rows at top of table and other 
    # two "N" rows at bottom of table.  This is done in order to match how it 
    # is presented in existing MI Odor Print excel spreadsheet.
    Dtbl=np.copy(D)
    Dtbl[1:79,:]=D[0:78,:]
    Dtbl[0]=D[79,:]
    d5 = np.round(Dtbl[:,0],2)
    d3 = np.round(Dtbl[:,1],2)
    d15 = np.round(Dtbl[:,2],2)

    header_lines = [
        f"{'Toward Distance_in_Miles':>6}",
        f"{'       5%   3%   1.5%':>21}",
    ]
    table_lines = [
        f"{label:>6s} {v5:4.2f} {v3:4.2f} {v15:4.2f}"
        for label, v5, v3, v15 in zip(wlab, d5, d3, d15)
    ]
    table_text = "\n".join(header_lines + table_lines) + "\n"

    with open(text_file_name, 'wt') as f_handle:
        f_handle.write(table_text)

    return(text_file_name)
    


def write_kml(LL, E, latval, lonval, kml_file_name):
    """create kml and save file from LL array 

    Args:
        LL (np array): set backs in lat/lon
        latval (float): point source latitude
        lonval (float): point source longitude
        kml_file_name (str): full path to kml file to save
    """
    
    kml = simplekml.Kml()
    pnt=kml.newpoint(name="", coords=[(lonval,latval)])  # Source
    pnt.name = 'E=' +str(E)
    pnt.style.iconstyle.color = simplekml.Color.black
    pnt.style.iconstyle.scale = 1 
    pnt.style.iconstyle.icon.href = PLACE_MARK
    pol=kml.newpolygon(name="1.5% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,2,:]))))
    pol.style.linestyle.color = simplekml.Color.green
    pol.style.linestyle.width = 10
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 0
    pol.visibility=0
    pol=kml.newpolygon(name="3% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,1,:]))))
    pol.style.linestyle.color = simplekml.Color.blue
    pol.style.linestyle.width = 10
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 0
    pol.visibility=0
    pol=kml.newpolygon(name="5% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,0,:]))))
    pol.style.linestyle.color = simplekml.Color.red
    pol.style.linestyle.width = 10
    pol.style.polystyle.outline = 1
    pol.style.polystyle.fill = 0
            
    kml.save(kml_file_name)  


        
def write_pointsource_shapefile(shapefile_name_stem:str, lonval:float, latval:float):
    """save single point shape file for mapping point source using pyshp
    https://github.com/GeospatialPython/pyshp?tab=readme-ov-file#writing-shapefiles
    
    Args:
        shapefile_name_stem (str): base file name to use for components of shapefile
        lonval (float): longitude of point
        latval (float): latitude of point
    
    Returns:
        list[str]: list of all the actual files that were saved
    """
    w = shapefile.Writer(shapefile_name_stem, shapeType=shapefile.POINT)
    w.point(lonval,latval)
    w.field('Point')
    w.record('Odor_source')
    w.close()
    return([        
        f"{shapefile_name_stem}.dbf",
        f"{shapefile_name_stem}.shp",
        f"{shapefile_name_stem}.shx",                
    ])

            

def write_footprint_shapefile(shape_file_name_stem: str, LL: np.ndarray):
    """Write the footprint polygon shapefile and return list of 
    filenames created

    Args:
        shape_file_name_stem (str): the 'stem' of the file, a full path with 
        a file name and no extension
        LL (np.ndarray): Lat Lon of footprint ring (usually the 5% one)

    Returns:
        list[str]: list of all the actual files that were saved
    """

    # uses pyshp
    # https://github.com/GeospatialPython/pyshp?tab=readme-ov-file#writing-shapefiles
        
    w = shapefile.Writer(shape_file_name_stem, shapeType=shapefile.POLYGON)
    w.poly([LL[:,0,:].tolist()])
    w.field('Polygon')
    w.record('5%_footprint')
    w.close()

    return [
        f"{shape_file_name_stem}.dbf",
        f"{shape_file_name_stem}.shp",
        f"{shape_file_name_stem}.shx",
    ]


def write_zipfile(zipfile_path: str, zip_files: list[str]):
    """given list of files and zip file path, create and save
    a zip file.  The items in the zip file have their directory 
    stripped so unzipping will go directly into the target folder

    Args:
        zipfile_path (str): where to store the zip file
        zip_files (list[str]): list of full paths to files to include
    """
    shape_zip = zipfile.ZipFile(zipfile_path, 'w')

    tmp_str = []
    for zfile in zip_files:
        tmp_str = zfile.rsplit('/',1)
        tmp_loc_file = tmp_str[1]
        shape_zip.write(zfile, arcname=tmp_loc_file, compress_type=zipfile.ZIP_DEFLATED)

    shape_zip.close()
    return(zipfile_path)
        
def fod_model(latval, lonval, LAT, LON, E, topt=1):
    """calculates an aray of setback distances in miles given wind
    characterists for a coordinate in the state of Michigan 

    Args:
        latval (float): latitude of the point
        lonval (float): longitude of the point
        LAT (np.ndarray): array of wind characterists at Lat
        LON (np.ndarray): array of longitudes
        E (np.ndarray): array of elevations
        topt (int, optional): _description_. Defaults to 1.
    """
    if(topt == 1):
        # Use full dataset: 00 UCT 1 Jan to 21 UCT 31 Dec
        ts=0
        te=2920
    elif(topt == 2):
        # Restrict to 00 UTC 1 Apr (point #721, i.e., #720 in pythonese)
        # to 21 UTC 31 Oct (point #2432, i.e., #2431 in pythonese).
        # Recall that Xindi's data omits leap days.  So each year
        # contains the same number of hours.
        ts=720
        te=2432
    
    
    PC, WS, WD = read_narr(latval, lonval, LAT, LON, ts, te)
    #-----------------------Wind direction processing------------------------

    indx=np.random.RandomState(seed=8675309).permutation(WD.size)
    wd4=[90,180,270,360]
    i4=np.zeros((WD.size,4), dtype=int, order='F')
    h,x = np.histogram(WD,bins=np.arange(0,361,1))
    for m in range(0,4):
        if(m<3):
            a1=np.median(h[wd4[m]-1-6:wd4[m]-1-2])
            a2=np.median(h[wd4[m]-1+2:wd4[m]-1+6])
        else:
            a1=np.median(h[wd4[m]-1-6:wd4[m]-1-2])
            a2=np.median(h[1:5])
        cap=round((a1+a2)/2)
        I=WD==wd4[m];c=1;i4[:,m]=I.astype(int)
        for t in range(0,i4[:,0].size):
            tr=indx[t]
            if((I[tr].astype(int)==1) & (c<=cap)):
                i4[tr,m]=0
                c=c+1	
    Isum=np.sum(i4,1)
    I1=Isum>0
    I2=I1.astype(int)
    WDds=np.copy(WD)
    WDds[I2==1]=-999

    #--------Footprint preliminary step 1: compute "windstar chart"----------
    dbin=np.arange(11.25,360,22.5)
    wc = np.zeros((16,6), dtype=float, order='F')
    for d in range(0,dbin.size):
        if (d == 0):									
            PCs = PC[(WDds >= dbin[15]) | ((WDds < dbin[0]) & (WDds >= 0))]
            WSs = WS[(WDds >= dbin[15]) | ((WDds < dbin[0]) & (WDds >= 0))]		
        else:
            PCs = PC[(WDds >= dbin[d-1]) & (WDds < dbin[d])]
            WSs = WS[(WDds >= dbin[d-1]) & (WDds < dbin[d])]				
        wc[d,0] = float((((PCs == 6) & (WSs <= 1.3)).sum()))/ float((WDds>=0).sum())*100
        wc[d,1] = wc[d,0] + float((((PCs == 6) & (WSs > 1.3) & (WSs <= 3.1)).sum()))/ float((WDds>=0).sum())*100
        wc[d,2] = wc[d,1] + float((((PCs == 5) & (WSs <= 3.1)).sum()))/ float((WDds>=0).sum())*100
        wc[d,3] = wc[d,2] + float((((PCs == 5) & (WSs > 3.1) & (WSs <= 5.4)).sum()))/ float((WDds>=0).sum())*100
        wc[d,4] = wc[d,3] + float((((PCs == 4) & (WSs <= 5.4)).sum()))/ float((WDds>=0).sum())*100
        wc[d,5] = wc[d,4] + float((((PCs == 4) & (WSs > 5.4) & (WSs <= 8.0)).sum()))/ float((WDds>=0).sum())*100


    #------Footprint preliminary step 2: identify 1.5%,3%,5% classess--------
    f = np.zeros((5*dbin.size,3), dtype=int, order='F')
    for d in range (0,dbin.size):
        tem=np.round(wc[d,:],2)
        if(d==0):
            f[37:42,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[37:42,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[37:42,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==1):
            f[42:47,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[42:47,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[42:47,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==2):
            f[47:52,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[47:52,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[47:52,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==3):
            f[52:57,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[52:57,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[52:57,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==4):
            f[57:62,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[57:62,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[57:62,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==5):
            f[62:67,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[62:67,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[62:67,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==6):
            f[67:72,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[67:72,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[67:72,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==7):
            f[72:77,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[72:77,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[72:77,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==8):
            f[77:80,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[77:80,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[77:80,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
            f[0:2,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[0:2,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[0:2,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==9):
            f[2:7,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[2:7,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[2:7,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==10):
            f[7:12,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[7:12,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[7:12,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==11):
            f[12:17,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[12:17,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[12:17,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==12):
            f[17:22,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[17:22,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[17:22,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==13):
            f[22:27,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[22:27,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[22:27,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==14):
            f[27:32,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[27:32,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[27:32,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
        elif(d==15):
            f[32:37,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
            f[32:37,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
            f[32:37,0]=np.min(np.where(tem==max(tem[tem<=5])))+1


    #-------Footprint preliminary step 3: compute setback distance (D)-------
    D = np.zeros((5*dbin.size,3), dtype=float, order='F')
    for d in range (0,5*dbin.size):
        for p in range (0,3):
            if (f[d,p] == 1):
                D[d,p]=0.1181*math.pow(E,0.5132) # Class 1
            elif (f[d,p] == 2):
                D[d,p]=0.0634*math.pow(E,0.5366) # Class 2
            elif (f[d,p] == 3):
                D[d,p]=0.0399*math.pow(E,0.5397) # Class 3   
            elif (f[d,p] == 4):
                D[d,p]=0.0242*math.pow(E,0.5844) # Class 4   
            elif (f[d,p] == 5):  
                D[d,p]=0.0175*math.pow(E,0.5827) # Class 5
            elif (f[d,p] == 6):
                D[d,p]=0.0101*math.pow(E,0.6264) # Class 6  
                
    return(D) 
      
              
def fod(latval:float, lonval:float, odor_index:int, file_prefix:str, LAT:np.ndarray, LON:np.ndarray, time_flag:str, output_offset_dir:str):
    """coordinate the run of the FOD model and call functions to save various outputs

    Args:
        latval (float): latitude of point source   
        lonval (float): longitude of point source
        odor_index (int): odor index value
        file_prefix (str): prefix for output files
        LAT (np.ndarray): array of latitudes
        LON (np.ndarray): array of longitudes
        time_flag (str, optional): time flag for dataset selection. Defaults to TIME_FLAG on config file
        output_offset_dir (str, optional): directory for output files  Defaults to OUTPUT_OFFSET_DIR.
    """
    
    E = odor_index # doing this here to match legacy code and downstream fn's
    
    if(time_flag == 'F'):
        tfs=1;tfe=1 #Full year dataset: 1 Jan - 31 Dec; run program once.
    elif(time_flag == 'W'):
        tfs=2;tfe=2;#Warm season dataset: 1 Apr - 31 Oct ; run program once.
    elif(time_flag == 'B'):
        tfs=1;tfe=2 #Run program twice, once for 1 Jan - 31 Dec (tfs=1), and a second time, for 1 Apr - 31 Oct. (tfe=2)
    else:
        print('Incorrect time flag option, defaulting to full year')
        tfs=1;tfe=1				

    # this runs once for flags F and W and twice for B
    for topt in range(tfs,tfe+1):        
        D = fod_model(latval=latval, lonval=lonval, LAT=LAT, LON=LON, E=E, topt=topt)

        footprints_plot_file_path, five_percent_plot_file_path = write_footprint_plots(D=D, E=E, topt=topt, output_offset_dir=output_offset_dir, file_prefix=file_prefix)

        #---------Print formatted table to text file--------        
        if(topt == 1):            
            text_file_name = 'table_setbackdistance_FY.txt'            
        elif(topt == 2):
            text_file_name = 'table_setbackdistance_WS.txt'         
            
        text_file_name = add_prefix_to_filename(
            os.path.join(output_offset_dir, text_file_name), file_prefix)
        
        write_setback_text_table(text_file_name=text_file_name, D=D)

        
        # make a Lat/Lon array, used by both KML and shape file writers
        # this is not the same as 2018 version:
        #   b/c uses geodesic fn since vincenty was deprecated
        LL=np.empty((81,3,2), dtype=float, order='F')        
        for d in range(0,dbin.size):
            for p in range(0,3):
                LL[d,p,1]=geodesic(miles=D[d,p]).destination(Point(latval, lonval), dbin[d]).latitude
                LL[d,p,0]=geodesic(miles=D[d,p]).destination(Point(latval, lonval), dbin[d]).longitude
        LL[80,:,:]=LL[0,:,:]
        
        
        #-----------Generate KML file with footprints drawn as polygons----------
        if(topt == 1):
            file_name = "kml_footprint_FY.kml"
        elif(topt == 2):
            file_name = "kml_footprint_WS.kml" 
            
        kml_file_name = add_prefix_to_filename(os.path.join(output_offset_dir, file_name), file_prefix)
        write_kml(LL, E, latval, lonval, kml_file_name)


        #----------Create ESRI shapefile (only output 5% footprint)--------------

        # point source
        if(topt == 1):
            shapefile_name_stem = SHAPE_SOURCE_FY = 'shp_source_FY' 
        elif(topt == 2):
            shapefile_name_stem = SHAPE_SOURCE_WS = 'shp_source_WS' 

        shapefile_name_stem = add_prefix_to_filename(os.join(output_offset_dir, shapefile_name_stem), file_prefix)

        pointsource_shape_files = write_pointsource_shapefile(shapefile_name_stem, lonval, latval):
        
        # polygon
        if(topt == 1):
            shapefile_name_stem = SHAPE_FOOTPRINT_FY = 'shp_footprint_FY' 
        elif(topt == 2):                   
            shapefile_name_stem = SHAPE_FOOTPRINT_WS = 'shp_footprint_WS'      

        shapefile_name_stem = add_prefix_to_filename(os.join(output_offset_dir, shapefile_name_stem), file_prefix)
        footprint_shape_files = write_footprint_shapefile(shape_file_name=shapefile_name_stem, LL=LL)

        #---- create zip of shape file ---#
        
        zip_files = pointsource_shape_files + footprint_shape_files
        if(topt == 1):
            zipfile_name = 'fy_shapefile.zip' 
        elif(topt == 2):                   
            zipfile_name = 'ws_shapefile.zip' 
        
        zipfile_path =  add_prefix_to_filename(os.path.join(output_offset_dir,  zipfile_name), file_prefix)
    
        zipfile_path = write_zipfile(zipfile_path, zip_files)
        
    # end for loop 
    # 


if __name__ == "__main__":
    latval = float(sys.argv[1])
    lonval = float(sys.argv[2])
    odor_index = float(sys.argv[3])
    file_prefix = sys.argv[4]
    
    # validate here     
    LAT, LON = read_narr_lat_lon(narr_file = NARR_INPUT)
    
    if not validate_latlon(latval, lonval, LAT, LON):
        print("Location outside the NARR domain.")
        sys.exit()

    fod(latval, lonval, odor_index, file_prefix, LAT, LON, time_flag = TIME_FLAG, output_offset_dir=OUTPUT_OFFSET_DIR)
