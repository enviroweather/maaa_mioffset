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
#   May 2026 (Pat Bills, MSU ICER)
#     + added methods create other map and image formats for API outputs
#     + split functions to 1) create object 2) save to disk OR 3) convert for api
#     + use new wind data factory method for flex file location (s3 vs file)
#     + functions to save KML and SVG for api use, and convert to Base64 for JSON compatibility
#     - move main 'runners' into mioffset.py - this is no longer an executable script
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

print("MIOFFSET DEVELOPMENT VERSION - NOT FOR PRODUCTION USE")

# #------------------------Imports-------------------------

# from python stdlib
import json

import math
import sys, os
import io
import zipfile


# old mapping files
from geopy import Point
# vincenty method is deprecated, use geodesic method instead
import simplekml
import shapefile

# environment
from dotenv import load_dotenv

# response prep
import base64

# for model
import numpy as np
import matplotlib.pyplot as plt
from geopy.distance import geodesic
from mioffset.narr_data import WindData, filter_narr_timeseries, wind_data_factory


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


# note that these don't appear to be used in this 
# but are perhaps used in the FE to calculate odor_index
#--------------------------Variable definitions--------------------------
# wc: Frequency of each wind-stability class (float)
# f:  Wind-stability class that occurs closest to but not 
#     greater than 5%, 3%, and 1.5% of the time (integer)
# D:  Setback distance, computed as a function of wind 
#     stability class using OFFSET look-up tables (float)
# E:  Total Odor Emission Factor (float)

# glossary
# FY: full year
# wind_speed: W? season
#------------------------------------------------------------------------



####### VISUALIZATIONS ##########
def footprint_plots(D: np.ndarray, E: float, topt: int):
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
    '','','','','SSW','','','','','SW','','','','','wind_speedW',
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
    ax.set_position((box.x0, box.y0, box.width * 0.8, box.height * 0.8))

    # Put a legend to the right of the current axis
    lg=ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.25))
    lg.draw_frame(False)
    return(plt)


def matplotlib_to_svg(plt)->str:
    """get an SVG string from a matplotlib plot. This has probably been 
    written 1,000s of times in code bases
    
    Args:
        plt: Matplotli
        
    Returns:
        str: SVG code for the plot
    
    """
    
    plot_image = io.StringIO()
    
    plt.savefig(plot_image, format='svg')
    plot_image.seek(0)  # rewind the data
    plot_svg = plot_image.getvalue() # svg string

    return(plot_svg)

       

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

    plt = footprint_plots(D, E, topt)
    ## the only difference for "topt" is the filename here, move this to a parameter?
    if(topt == 1):
        plot_file_name = "image_footprint_3inone_FY.png"         
    elif(topt == 2):
        plot_file_name=  "image_footprint_3inone_Warm_Season.png" 
    else:
        raise RuntimeError("invalid time option")
        
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
    '','','','','SSW','','','','','SW','','','','','wind_speedW',
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
        plot_file_name = "image_footprint_wind_speed.png"

    five_percent_plot_file_path = add_prefix_to_filename(os.path.join(output_offset_dir, plot_file_name), file_prefix)
    plt.savefig(five_percent_plot_file_path, format='png', dpi=300, transparent=True)
    plt.close()

    debug_print(f"saved {five_percent_plot_file_path}")

    return(footprints_plot_file_path, five_percent_plot_file_path)


def setback_text_table(D: np.ndarray)->str:
    """ create Special special version of D array, with three "N" rows at top of table and other 
    two "N" rows at bottom of table.  This is done in order to match how it 
    is presented in existing MI Odor Print excel spreadsheet.
    
    Args:
        D (np.ndarray): offset values, must have shape 80,3
    
    Returns:
        str: lines of table suitable for printing in fixed width font
    """
    
    wlab=np.array(
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
    Dtbl=np.copy(D)
    Dtbl[1:79,:]=D[0:78,:]
    Dtbl[0]=D[79,:]
    
    # round to 2 places
    d5 = np.round(Dtbl[:,0],2)   # 5%
    d3 = np.round(Dtbl[:,1],2)   # 3%
    d15 = np.round(Dtbl[:,2],2)  # 1.5%
    
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


def write_setback_text_table(text_file_name: str, table_text: str):# D: np.ndarray):
    """write text file of set-back distances in tabular form by direction

    Args:
        text_file_name (str): file name to save the table as
        D (np.ndarray): array of setback distances
        
    Returns:
        str: file name that was saved
    """ 

    with open(text_file_name, 'wt') as f_handle:
        f_handle.write(table_text)

    return(text_file_name)
    

########## MAPPING ###########

def fod_plot_to_ll(D, lat:float, lon:float)->np.ndarray:
    """convert setback distance output from FOD model into a the 
    lat, lon coordinates of set-back radius from the 
    center point for placing on a map 

    Args:
        D (_type_): output from 
        lat (float): latitude of center point
        lon (float): longitude of center point
    """
    
    dbin = np.arange(4.5, 364.5, 4.5) #redefined with 4.5 degree bins.        
    
    LL:np.ndarray = np.empty((81,3,2), dtype=float, order='F')        
    
    for d in range(0,dbin.size):
        for p in range(0,3):
            LL[d,p,1]=geodesic(miles=D[d,p]).destination(Point(lat, lon), dbin[d]).latitude
            LL[d,p,0]=geodesic(miles=D[d,p]).destination(Point(lat, lon), dbin[d]).longitude
    
    # does this rotate or flip it?
    LL[80,:,:]=LL[0,:,:]
    
    return(LL)
    
    
def fod_kml(LL, E, lat, lon):
    """create KML formatted setback polygons for placing on a map

    Args:
        LL (np.ndarray): shape (81, 3, 2) array from fod_plot_to_ll where
            axis 0 = direction bins (80 + closing point),
            axis 1 = footprint level (0=5%, 1=3%, 2=1.5%),
            axis 2 = [longitude, latitude]
        E (float): Total Odor Emission Factor
        lat (float): latitude of the point source
        lon (float): longitude of the point source
        
    Returns:
        str: XML-formatted KML 
    """
    PLACE_MARK = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png' 

    kml = simplekml.Kml()
    pnt=kml.newpoint(name="", coords=[(lon,lat)])  # Source
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
    return(kml)

    # string is kml.kml()
    
def write_kml(LL, E, lat, lon, kml_file_name):
    """create kml and save file from LL array 

    Args:
        LL (np array): set backs in lat/lon
        latval (float): point source latitude
        lonval (float): point source longitude
        kml_file_name (str): full path to kml file to save
    """
    
    kml = fod_kml(LL, E, lat, lon)     
    kml.save(kml_file_name)  


def kml_encode_base64(kml:str|simplekml.Kml, kml_file_name="kml"):
    """
    Convert KML content to a URL-safe Base64-encoded dictionary payload 
    (suitable for incorporation into JSON response)
    Accepts either a `simplekml.Kml` object or a raw KML XML string, encodes the
    KML content as UTF-8, then returns a dictionary where the key is the provided
    file name and the value is the Base64-encoded bytes.
    Args:
        kml (str | simplekml.Kml):
            KML content to encode. Must be either:
            - a `simplekml.Kml` instance (uses its `.kml()` output), or
            - a raw KML XML string.
        kml_file_name (str, optional):
            Key name to use in the returned dictionary. Defaults to `"kml"`.
    Returns:
        dict[str, bytes]:
            A dictionary containing one entry:
            `{kml_file_name: <urlsafe_base64_encoded_kml_bytes>}`.
    Raises:
        RuntimeError:
            If `kml` is neither a `simplekml.Kml`-like object (with `.kml()`) nor a string.
    """
    if hasattr(kml, 'kml'):
        kml_xml:str = kml.kml()
    elif isinstance(kml, str):
        kml_xml:str = kml        
    else:
        # don't know what this is
        raise RuntimeError("kml sent to kml2base64 is not a recognized type (kml or xml str)")
    kmlb64 = base64.urlsafe_b64encode(kml_xml.encode('utf-8'))
    kml_dict = {kml_file_name:kmlb64}
    return kml_dict


def kml_decode_base64(kml_dict: dict[str, bytes | str], kml_file_name: str = "kml") -> str:
    """Decode URL-safe Base64 KML payload back into XML text.

    Args:
        kml_dict (dict[str, bytes | str]):
            Dictionary payload containing one encoded KML value.
        kml_file_name (str, optional):
            Key name expected in kml_dict. Defaults to "kml".

    Returns:
        str: Decoded KML XML string.

    Raises:
        RuntimeError:
            If the payload is invalid or cannot be decoded as UTF-8 XML.
    """
    if not isinstance(kml_dict, dict):
        raise RuntimeError("kml_decode_base64 expects a dictionary payload")

    if kml_file_name not in kml_dict:
        raise RuntimeError(f"kml_decode_base64 missing key '{kml_file_name}' in payload")

    kmlb64 = kml_dict[kml_file_name]
    if isinstance(kmlb64, str):
        kmlb64_bytes = kmlb64.encode("ascii")
    elif isinstance(kmlb64, (bytes, bytearray)):
        kmlb64_bytes = bytes(kmlb64)
    else:
        raise RuntimeError("encoded KML value must be bytes or string")

    try:
        kml_xml_bytes = base64.urlsafe_b64decode(kmlb64_bytes)
        kml_xml = kml_xml_bytes.decode("utf-8")
    except Exception as exc:
        raise RuntimeError("failed to decode Base64 KML payload") from exc

    return kml_xml


def fod_geojson(LL: np.ndarray, E: float, lat: float, lon: float) -> dict:
    """Create a GeoJSON FeatureCollection equivalent to fod_kml.

    Produces a point feature for the odor source and three polygon features
    for the 5%, 3%, and 1.5% setback footprints.

    Args:
        LL (np.ndarray): shape (81, 3, 2) array from fod_plot_to_ll where
            axis 0 = direction bins (80 + closing point),
            axis 1 = footprint level (0=5%, 1=3%, 2=1.5%),
            axis 2 = [longitude, latitude]
        E (float): Total Odor Emission Factor
        lat (float): latitude of the point source
        lon (float): longitude of the point source

    Returns:
        dict: GeoJSON FeatureCollection with four features (but not JSON str):
              one Point (source) and three Polygons (1.5%, 3%, 5% footprints)
    """
    def _ring(level_idx: int) -> list:
        # LL[d, p, 0] = lon, LL[d, p, 1] = lat — GeoJSON uses [lon, lat]
        return LL[:, level_idx, :].tolist()

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"name": "Odor source", "odor_emission_factor": E},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(2)]},
            "properties": {"name": "1.5% footprint", "level": "1.5%"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(1)]},
            "properties": {"name": "3% footprint", "level": "3%"},
        },
        {
            "type": "Feature",
            "geometry": {"type": "Polygon", "coordinates": [_ring(0)]},
            "properties": {"name": "5% footprint", "level": "5%"},
        },
    ]

    return {"type": "FeatureCollection", "features": features}

        
def write_pointsource_shapefile(shapefile_name_stem:str, lonval:float, latval:float)->list[str]:
    """save single point shape file for mapping point source using pyshp
    https://github.com/GeospatialPython/pyshp?tab=readme-ov-file#writing-shapefiles
    
    SIDE EFFECT: files written to disk

    
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


def write_footprint_shapefile(shape_file_name_stem: str, LL: np.ndarray)->list[str]:
    """Write the footprint polygon shapefile and return list of 
    filenames created

    SIDE EFFECT: files written to disk
    
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


def write_zipfile(zipfile_path: str, zip_files: list[str])->str:
    """given list of files and zip file path, create and save
    a zip file.  The items in the zip file have their directory 
    stripped so unzipping will go directly into the target folder
    
    SIDE EFFECT: files written to disk


    Args:
        zipfile_path (str): where to store the zip file
        zip_files (list[str]): list of full paths to files to include
    Returns:
        str: path to zip file saved
    """
    shape_zip = zipfile.ZipFile(zipfile_path, 'w')

    tmp_str = []
    for zfile in zip_files:
        tmp_str = zfile.rsplit('/',1)
        tmp_loc_file = tmp_str[1]
        shape_zip.write(zfile, arcname=tmp_loc_file, compress_type=zipfile.ZIP_DEFLATED)

    shape_zip.close()
    return(zipfile_path)



###### MAIN MODEL 
        
def fod_model(pc: np.ndarray, wind_speed:np.ndarray, wind_direction:np.ndarray, odor_index:int):
    """calculates an aray of setback distances in miles given wind
    characteristics for a coordinate in the state of Michigan 

    Args:
        pc (np.ndarray): time series of ?
        wind_speed (np.ndarray): time series of wind speeds
        wind_direction (np.ndarray): time series of wind directions
        odor_index (int): odor index calculated from building size and type
    Returns:
        np.array 3 sets of 80 values (shape = (80,3)), 5% 3%, 1.5% setback distance
    """

    # renamed for comparability with original code
    E = odor_index
    #-----------------------Wind direction processing------------------------
    
    indx=np.random.RandomState(seed=8675309).permutation(wind_direction.size)
    wd4=[90,180,270,360]
    i4=np.zeros((wind_direction.size,4), dtype=int, order='F')
    h,x = np.histogram(wind_direction,bins=np.arange(0,361,1))
    for m in range(0,4):
        if(m<3):
            a1=np.median(h[wd4[m]-1-6:wd4[m]-1-2])
            a2=np.median(h[wd4[m]-1+2:wd4[m]-1+6])
        else:
            a1=np.median(h[wd4[m]-1-6:wd4[m]-1-2])
            a2=np.median(h[1:5])
        cap=round((a1+a2)/2)
        I=wind_direction==wd4[m];c=1;i4[:,m]=I.astype(int)
        for t in range(0,i4[:,0].size):
            tr=indx[t]
            if((I[tr].astype(int)==1) & (c<=cap)):
                i4[tr,m]=0
                c=c+1	
    Isum=np.sum(i4,1)
    I1=Isum>0
    I2=I1.astype(int)
    wind_directionds=np.copy(wind_direction)
    wind_directionds[I2==1]=-999

    #--------Footprint preliminary step 1: compute "windstar chart"----------
    dbin=np.arange(11.25,360,22.5)
    wc = np.zeros((16,6), dtype=float, order='F')
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
            f[67:72,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
        elif(d==6):
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

def fod2dict(D:np.ndarray)->dict[str, list[float]]:
    """convert output of FOD model from Numpy array to python dict, one
    for each column.  This is to help convert to JSON to return via an API

    Args:
        D (np.ndarray): output from fod_model, 80 rows, 2 columns

    Returns:
        dict[str, list[float]]: same date, but one key for each column, keys named by what they are
    """
    return {'5percent':D[:,0].tolist(), '3percent':D[:,1].tolist(), '1.5percent':D[:,2].tolist()}


def fod2json(D:np.ndarray)->str:
    """convert output of FOD model from Numpy array to JSON string

    Args:
        D (np.ndarray): output from fod_model, 80 rows, 2 columns

    Returns:
        str: JSON string containing the data
    """

    D_dict = fod2dict(D)
    D_json = json.dumps(D_dict)
    
    return D_json

