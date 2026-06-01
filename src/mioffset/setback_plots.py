"""setback_plots

code to create footprint polar plots, not for maps
"""
# these functions are moved here to reduce dependencies and time
# for the main model to run.  

import io
from os import path
import matplotlib.pyplot as plt
from numpy import ndarray, radians, arange, max, ceil, linspace, round
from math import pi
from mioffset.mioffset_utils import add_prefix_to_filename, debug_print


####### VISUALIZATIONS ##########
def footprint_plots(D: ndarray, E: float, topt: int):
    dbin = arange(4.5, 364.5, 4.5) #redefined with 4.5 degree bins.
    #   1.  First image: all three footprints (1.5%,3%,5%)
    
    ax = plt.subplot(111, projection='polar')
    ax.set_theta_zero_location('N')    #type:ignore # this works, but raise typing error
    ax.set_theta_direction(-1)         #type:ignore # this works, but raise typing error
    theta=radians(dbin)
    ax.grid(True);ax.yaxis.grid(lw=1, ls='--');
    ax.plot(theta, D[:,0],'r-',theta, D[:,1],'b-',theta, D[:,2],'g-',lw=2.5)
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,0],D[0,0]],'r',lw=2.5,label='5%')
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,1],D[0,1]],'b',lw=2.5,label='3%')
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,2],D[0,2]],'g',lw=2.5,label='1.5%')
    ax.set_xticks(arange(0,2*pi,2*pi/80))
    ax.set_xticklabels(['N','','','','','NNE','','','','','NE',
    '','','','','ENE','','','','','E','','','','','ESE',
    '','','','','SE','','','','','SSE','','','','','S',
    '','','','','SSW','','','','','SW','','','','','wind_speedW',
    '','','','','W','','','','','WNW','','','','','NW',
    '','','','','NNW','','','',''])

    if(1.1*max(D[:,2]) >= 0.5):
        yl=ceil(1.1*max(D[:,2]))
        ax.set_ylim(0,yl)
        ax.set_yticks(linspace(0,yl,num=11))
        ax.set_yticklabels(round(linspace(0,yl,num=11),1))
    else:
        yl=0.5 # Small setback distance
        ax.set_ylim(0,yl)
        ax.set_yticks(linspace(0,yl,num=6))
        ax.set_yticklabels(round(linspace(0,yl,num=6),1))
    position=335
    ax._r_label_position._t = (position, 0)  # type:ignore
    ax._r_label_position.invalidate()        # type:ignore
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

       

def write_footprint_plots(D: ndarray, E: float, topt: int, output_offset_dir: str, file_prefix: str=""):
    """create wind plots from model and save as PNGs

    Args:
        D (ndarray): Setback distance, computed as a function of wind stability class using OFFSET look-up tables (float)
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
        
    footprints_plot_file_path = add_prefix_to_filename(path.join(output_offset_dir, plot_file_name), file_prefix)
    plt.savefig(footprints_plot_file_path, format='png', dpi=300, transparent=True)
    debug_print(f"saved {footprints_plot_file_path}")
    plt.close()
    
    
    #TODO this code should be moved to footprint_plots, and if necessary could we add a parameter to footprint plots
    # this seems to add a new subplot to the original 
    # that accommodates this (since it is nearly the same code)
    dbin = arange(4.5, 364.5, 4.5) #redefined with 4.5 degree bins.

    # ---------  2.   Second image: 5% footprint only.
    ax = plt.subplot(111, projection='polar')
    ax.set_theta_zero_location('N')              # type:ignore  # these methods do work
    ax.set_theta_direction(-1)                   # type:ignore  # these methods do work
    theta=radians(dbin)
    ax.grid(True);ax.yaxis.grid(lw=1, ls='--');
    ax.plot(theta, D[:,0],'r-',lw=2.5)
    ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,0],D[0,0]],'r',lw=2.5,label='5%')
    ax.set_xticks(arange(0,2*pi,2*pi/80))
    ax.set_xticklabels(['N','','','','','NNE','','','','','NE',
    '','','','','ENE','','','','','E','','','','','ESE',
    '','','','','SE','','','','','SSE','','','','','S',
    '','','','','SSW','','','','','SW','','','','','wind_speedW',
    '','','','','W','','','','','WNW','','','','','NW',
    '','','','','NNW','','','',''])

    if(1.1*max(D[:,0]) >= 0.5):
        yl=ceil(1.1*max(D[:,0]))
        ax.set_ylim(0,yl)
        ax.set_yticks(linspace(0,yl,num=11))
        ax.set_yticklabels(round(linspace(0,yl,num=11),1))
    else:
        yl=0.5 # Small setback distance
        ax.set_ylim(0,yl)
        ax.set_yticks(linspace(0,yl,num=6))
        ax.set_yticklabels(round(linspace(0,yl,num=6),1))
    position=335
    ax._r_label_position._t = (position, 0)   # type:ignore  # these methods do work
    ax._r_label_position.invalidate()         # type:ignore  # these methods do work
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
    ax.set_position([box.x0, box.y0, box.width * 0.8, box.height * 0.8]) # type:ignore  # these methods do work

    # Put a legend to the right of the current axis
    lg=ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.25))
    lg.draw_frame(False)

    if(topt == 1):
        plot_file_name = "image_footprint_FY.png"
    elif(topt == 2):
        plot_file_name = "image_footprint_wind_speed.png"

    five_percent_plot_file_path = add_prefix_to_filename(path.join(output_offset_dir, plot_file_name), file_prefix)
    plt.savefig(five_percent_plot_file_path, format='png', dpi=300, transparent=True)
    plt.close()

    debug_print(f"saved {five_percent_plot_file_path}")

    return(footprints_plot_file_path, five_percent_plot_file_path)