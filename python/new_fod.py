#!/usr/bin/python

# python 2 
# new_fod.py
#########################################################################	
#
#	Developed by:
#
#	Michael Kiefer
#	Department of Geography, Environment, and Spatial Sciences
#	Michigan State University
#	Email: mtkiefer@msu.edu
#	Phone: (USFS): (517) 884-8051
#	      (Geography): (517) 432-4751
#
#	Last updated 10 July 2017
#	+ Two changes to static polar plots:
#		- Changed axes scaling to 80%
#		- Replaced white background with transparent background
#
########################################################################


import numpy as np
import math
import glob 
import h5py
import sys, os
import shutil
import matplotlib
# matplotlib.use('Agg') is necessary when the script is called from a PHP application
matplotlib.use('Agg')

import matplotlib.pyplot as plt

import time
import zipfile
from windrose import WindroseAxes
import matplotlib.cm as cm
from geopy import Point
from geopy.distance import vincenty
from geopy.geocoders import googlev3
import scipy.io as sio
import simplekml
import shapefile
import fod_config
from fod_config import TIME_FLAG, INPUT_FILE, NARR_INPUT, NARR_INPUT_LOC, OUT_IMG_WS, OUT_IMG_FY, OUT_IMG_3_1_WS, OUT_IMG_3_1_FY, SETBACK_FY, SETBACK_WS, PLACE_MARK
from fod_config import SAVE_FOOTPRINT_FY, SAVE_FOOTPRINT_WS, SHAPE_SOURCE_FY, SHAPE_SOURCE_WS, SHAPE_FOOTPRINT_FY, SHAPE_FOOTPRINT_WS, NARR_DATA_FOLDER, RM_OUTPUT_FILES
from fod_config import OUTPUT_LOCATION
from fod_config import *

# pylab does not appear to be used, maybe required for matplotlib output
# import pylab

latval = float(sys.argv[1])
lonval = float(sys.argv[2])
odor_index = float(sys.argv[3])
time_stamp = sys.argv[4]

#print "session_count ==",session_count
#lat = '42.7287719'
#lon = '-84.473659'

#Begin timer.
start = time.time()

#------------------------Remove old output files-------------------------
#print "RM_OUTPUT_FILES: ", glob.glob(RM_OUTPUT_FILES)
#os.system('rm ' + RM_OUTPUT_FILES)
#os.remove(RM_OUTPUT_FILES)
now = time.time()
#cutoff = now - 86400
cutoff = now - 60

folder = RM_OUTPUT_FILES
#for the_file in os.listdir(folder):
	#file_path = os.path.join(folder, the_file)
	#t = os.stat(str(file_path)
	#c = t.st_ctime
	#if c < cutoff:
		#try:
			#os.remove(str(file_path)
	##try:
		##if os.path.isfile(file_path):
			##os.unlink(file_path)
		#except Exception as e:
			#print e
#------------------------------------------------------------------------

#sys.exit()
#--------------------------Variable definitions--------------------------

# wc: Frequency of each wind-stability class (float)
# f:  Wind-stability class that occurs closest to but not 
#     greater than 5%, 3%, and 1.5% of the time (integer)
# D:  Setback distance, computed as a function of wind 
#     stability class using OFFSET look-up tables (float)
# E:  Total Odor Emission Factor (float)

#------------------------------------------------------------------------

#>>>>>>>>>>>>>>>>>>>>>>>>>I/O (SUBJECT TO CHANGE)>>>>>>>>>>>>>>>>>>>>>>>>

#------------------Read in information from input file.------------------



#INFILE = open(INPUT_FILE, "r") 
#INFILE.readline() #first header line
#INFILE.readline()
#loc_flag = str(INFILE.readline()).rstrip('\n')#remove newline character
#loc_flag = LOC_FLAG
#INFILE.readline() #second header line
#if(loc_flag == 'L'):
	#location specified in lat/long, in decimal degrees
	#getll=0
	#loc_info = INFILE.readline().split(",")
	#loc_info = lat + ", " + lon
#elif(loc_flag == 'A'):
	#location specified as address
	#getll=1
	#loc_info=str(INFILE.readline()).rstrip('\n')#remove newline character
	#loc_info = lat + ", " + lon
#INFILE.readline() #third header line
#numsource=int(INFILE.readline())
#source_list = list()
#source_list.append(SOURCE_1.split(','))
#source_list.append(SOURCE_2.split(','))
#source_list.append(SOURCE_3.split(','))
#print ""
#numsource = len(source_list)
#print "numsource: ",numsource
#source=np.zeros((numsource,3), dtype=np.float, order='F')
#print "source: ",source
#INFILE.readline() #fourth header line
#for s in range(numsource):
#n = 0
#while n < numsource:
	#for s in source_list:
		#print "s[?]: ",s[0],s[1],s[2],s[3]
		##print "source_list[1]:",source_list[1]
		##tem=INFILE.readline().split(",")
		##source[s,0]=tem1=float(tem[1].strip())#Area (sq. ft.)
		##source[s,1]=tem1=float(tem[2].strip())#Odor Emission No.
		##source[s,2]=tem1=float(tem[3].strip())#Odor Control Factor
		#source[n,0]=s[1]
		#source[n,1]=s[2]
		#source[n,2]=s[3]
	#n+=1
	
#print "source: ",source
	
	
#INFILE.readline() #fifth header line
#Option to restrict time series (full year plots vs. 1 Apr - 31 Oct plots vs. both sets of plots)
#time_flag = str(INFILE.readline()).rstrip('\n')#remove newline character
time_flag = TIME_FLAG
if(time_flag == 'F'):
	tfs=1;tfe=1 #Full year dataset: 1 Jan - 31 Dec; run program once.
elif(time_flag == 'W'):
	tfs=2;tfe=2;#Warm season dataset: 1 Apr - 31 Oct ; run program once.
elif(time_flag == 'B'):
	tfs=1;tfe=2#Run program twice, once for 1 Jan - 31 Dec (tfs=1), and a second time, for 1 Apr - 31 Oct. (tfe=2)
else:
	print('Incorrect time flag option, defaulting to full year')
	tfs=1;tfe=1				
#	
#INFILE.close()
#------------------------------------------------------------------------

#--------------Obtain latitude and longitude of the source--------------
# If user provided latitude and longitude separated by a comma:
#if(getll==0):
	#latval=float(loc_info[0])#Latitude (deg N)
	#lonval=float(loc_info[1])#Longitude (deg W)
#elif(getll==1):
	#geolocator = googlev3.GoogleV3()
	#gaddr = geolocator.geocode(loc_info)
	#latval = gaddr.latitude
	#lonval = gaddr.longitude		
#------------------------------------------------------------------------

#<<<<<<<<<<<<<<<<<<<<<<<I/O (SUBJECT TO CHANGE)<<<<<<<<<<<<<<<<<<<<<<<<<<

#>>>>>>>>>>>>>>>>>>>>>>>>>>CORE OF PROGRAM>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

#---------------------Extract at nearest grid point----------------------





#sys.exit()
#Dont forget to uncomment the h5py module in the import section



with h5py.File(NARR_INPUT,'r') as hf:
	data = hf.get('LAT')
	LAT = np.array(data)
	data = hf.get('LON')
	LON = np.array(data)


#print "minimum latitude: ",np.min(np.min(LAT))
#print "maximum latitude: ",np.max(np.max(LAT))
#print "minimum longitude: ",np.min(np.min(LON))
#print "maximum longitude: ",np.max(np.max(LON))
if((latval <np.min(np.min(LAT))) or ( latval > np.max(np.max(LAT))) \
or (lonval < np.min(np.min(LON))) or (lonval > np.max(np.max(LON)))):
	print "Location outside the NARR domain."
	sys.exit()


distance = (LAT-latval)**2 + (LON-lonval)**2
idy, idx = np.where(distance==distance.min())
idy=int(idy);idx=int(idx);

#If time_flag == 'B', run program twice, once for 1 Jan - 31 Dec (tfs=1), and a second time, for 1 Apr - 31 Oct. (tfe=2)
for topt in range(tfs,tfe+1):
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
	#	
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
			PC=np.concatenate((PC,PC1),axis=1)
			WS=np.concatenate((WS,WS1),axis=1)
			WD=np.concatenate((WD,WD1),axis=1)

	#------------------------------------------------------------------------

	#-----------------------Wind direction processing------------------------

	# Remove spikes in histogram at cardinal wind directions (90,180,270,360) 
	# The spikes are the result of truncating rather than rounding the 
	# u- and v- components to the nearest tenth of a meter per second. 
	#indx=np.random.permutation(WD.size) #original line
	indx=np.random.RandomState(seed=8675309).permutation(WD.size) #tracy - add replacement line per email from Mike Kiefer 2/24/2020 2:13pm
	wd4=[90,180,270,360]
	i4=np.zeros((WD.size,4), dtype=np.int, order='F')
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

			#	


	Isum=np.sum(i4,1)
	I1=Isum>0
	I2=I1.astype(int)
	WDds=np.copy(WD)
	WDds[I2==1]=-999

	#------------------------------------------------------------------------

	#--------Footprint preliminary step 1: compute "windstar chart"----------

	# Proceeding clockwise around wind rose, determine frequency of 
	# each wind-stability class.
	# When plotted, one gets a "windstar chart", as presented in Figure 1 in:
	# Jacobson, L.D., H. Guo, D.R. Schmidt, R.E. Nicolai, J. Zhu, K.A. Janni,
	# 2005. Development of the OFFSET model for determination of 
	# odor-annoyance-free setback distances from animal production sites: 
	# Part I. Review and experiment. Transactions of the ASAE, 48(6).
	dbin=np.arange(11.25,360,22.5)
	wc = np.zeros((16,6), dtype=np.float, order='F')
	for d in range(0,dbin.size):
        	if (d == 0):							
        		PCs = PC[(WDds >= dbin[15]) | ((WDds < dbin[0]) & (WDds >= 0))]
        		WSs = WS[(WDds >= dbin[15]) | ((WDds < dbin[0]) & (WDds >= 0))]		
		else:
        		PCs = PC[(WDds >= dbin[d-1]) & (WDds < dbin[d])]
        		WSs = WS[(WDds >= dbin[d-1]) & (WDds < dbin[d])]				
		#	
		wc[d,0] = float((((PCs == 6) & (WSs <= 1.3)).sum()))/ float((WDds>=0).sum())*100
		wc[d,1] = wc[d,0] + float((((PCs == 6) & (WSs > 1.3) & (WSs <= 3.1)).sum()))/ float((WDds>=0).sum())*100
		wc[d,2] = wc[d,1] + float((((PCs == 5) & (WSs <= 3.1)).sum()))/ float((WDds>=0).sum())*100
		wc[d,3] = wc[d,2] + float((((PCs == 5) & (WSs > 3.1) & (WSs <= 5.4)).sum()))/ float((WDds>=0).sum())*100
		wc[d,4] = wc[d,3] + float((((PCs == 4) & (WSs <= 5.4)).sum()))/ float((WDds>=0).sum())*100
		wc[d,5] = wc[d,4] + float((((PCs == 4) & (WSs > 5.4) & (WSs <= 8.0)).sum()))/ float((WDds>=0).sum())*100



	#------------------------------------------------------------------------

	#------Footprint preliminary step 2: identify 1.5%,3%,5% classess--------

	# Proceeding around the wind rose, identify the most
	# stable wind-stability class 
	# that comes closest to 1.5% frequency, without going over.  
	# Repeat for 3 and 5% frequencies. 
	# 
	# The "np.min" step ensures if two classes round to same frequency, e.g., 1.50%,
	# we pick the more stable class (conservative approach - better to
	# overestimate setback distance than underestimate it).

	# Also, expand to 80 bins for display 
	# purposes (as in original MI footprint). "+1" corrects for python 
	# arrays starting at 0.
	f = np.zeros((5*dbin.size,3), dtype=np.int, order='F')
	for d in range (0,dbin.size):
		tem=np.round(wc[d,:],2)	# Round to nearest hundredth.  1.500008 is 1.50.
					# We don't want digit in 5th or 6th decimal place
					# to determine wind-stability regime.
		if(d==0):
			#S	
			f[37:42,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[37:42,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[37:42,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==1):
			#SSW		
			f[42:47,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[42:47,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[42:47,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==2):
			#SW	
			f[47:52,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[47:52,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[47:52,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==3):
			#WSW	
			f[52:57,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[52:57,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[52:57,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==4):
			#W		
			f[57:62,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[57:62,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[57:62,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==5):
			#WNW	
			f[62:67,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[62:67,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[62:67,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==6):
			#NW	
			f[67:72,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[67:72,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[67:72,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==7):
			#NNW	
			f[72:77,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[72:77,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[72:77,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==8):
			#N	
			f[77:80,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[77:80,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[77:80,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
			f[0:2,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[0:2,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[0:2,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==9):
			#NNE	
			f[2:7,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[2:7,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[2:7,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==10):
			#NE	
			f[7:12,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[7:12,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[7:12,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==11):
			#ENE	
			f[12:17,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[12:17,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[12:17,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==12):
			#E		
			f[17:22,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[17:22,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[17:22,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==13):
			#ESE	
			f[22:27,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[22:27,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[22:27,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==14):
			#SE	
			f[27:32,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[27:32,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[27:32,0]=np.min(np.where(tem==max(tem[tem<=5])))+1
		elif(d==15):
			#SSE	
			f[32:37,2]=np.min(np.where(tem==max(tem[tem<=1.5])))+1
			f[32:37,1]=np.min(np.where(tem==max(tem[tem<=3])))+1
			f[32:37,0]=np.min(np.where(tem==max(tem[tem<=5])))+1


	#	
	#------------------------------------------------------------------------

	#-------Footprint preliminary step 3: compute setback distance (D)-------

	# Formula that follows, D = aE^b, along with empirical coefficients
	# [converted from meters to feet], obtained from:
	# Guo, H., L.D. Jacobson, D.R. Schmidt, R.E. Nicolai, J. Zhu, K.A. Janni, 
	# 2005. Development of the OFFSET model for determination of 
	# odor-annoyance-free setback distances from animal production sites: 
	# Part II. Model development and evaluations. Transactions of the ASAE,
	# 48(6).

	# Total odor emission factor (E):
	# Product of source area, odor emission number, and odor control factor, 
	# divided by 10000, summed over all sources.
	#E=np.sum(np.prod(source,1)/10000.0,0) 
	E = odor_index
	#print "E:",E
	D = np.zeros((5*dbin.size,3), dtype=np.float, order='F')
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


	# Special version of D array, with three "N" rows at top of table and other 
	# two "N" rows at bottom of table.  This is done in order to match how it 
	# is presented in existing MI Odor Print excel spreadsheet.
	Dtbl=np.copy(D)
	Dtbl[1:79,:]=D[0:78,:]
	Dtbl[0]=D[79,:]

	#------------------------------------------------------------------------


	#<<<<<<<<<<<<<<<<<<<<<<<<<<CORE OF PROGRAM<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<

	#>>>>>>>>>>>>>>>>>>>>>>>I/O (SUBJECT TO CHANGE)>>>>>>>>>>>>>>>>>>>>>>>>>>


	#------Plot footprint on polar axes with standard white background-------

	#dbin = np.arange(4.5, 360+4.5, 4.5) #redefined with 4.5 degree bins.
	dbin = np.arange(4.5, 364.5, 4.5) #redefined with 4.5 degree bins.
	#   1.  First image: all three footprints (1.5%,3%,5%)
	
	ax = plt.subplot(111, projection='polar')
	#ax = plt.subplots(211, polar=True)
	#fig = plt.figure()
	#ax = fig.add_subplot(111, projection='polar')
	ax.set_theta_zero_location('N')
	ax.set_theta_direction(-1)
	theta=np.radians(dbin)
	ax.grid(True);ax.yaxis.grid(lw=1, ls='--');
	ax.plot(theta, D[:,0],'r-',theta, D[:,1],'b-',theta, D[:,2],'g-',lw=2.5)
	ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,0],D[0,0]],'r',lw=2.5,label='5%')
	ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,1],D[0,1]],'b',lw=2.5,label='3%')
	ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,2],D[0,2]],'g',lw=2.5,label='1.5%')
	ax.set_xticks(np.arange(0,2*math.pi,2*math.pi/80))
	ax.set_xticklabels(['N','','','','','NNE','','','','','NE' \
	,'','','','','ENE','','','','','E','','','','','ESE' \
	,'','','','','SE','','','','','SSE','','','','','S' \
	,'','','','','SSW','','','','','SW','','','','','WSW' \
	,'','','','','W','','','','','WNW','','','','','NW' \
	,'','','','','NNW'])
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
		#+ '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n' \
		#+ 'Dataset: 1 Jan - 31 Dec' + '\n', va='bottom')
	elif(topt == 2):
		ax.set_title('MI Odor Print - Distance in Miles' + '\n' \
		+ '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n', va='bottom')
		#+ '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n' \
		#+ 'Dataset: 1 Apr - 31 Oct' + '\n', va='bottom')	
	# Shrink current axis by 20%
	box = ax.get_position()
	ax.set_position([box.x0, box.y0, box.width * 0.8, box.height * 0.8])

	# Put a legend to the right of the current axis
	lg=ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.25))
	lg.draw_frame(False)

	if(topt == 1):
		first_half, second_half = OUT_IMG_3_1_FY.rsplit('/',1)
		OUT_IMG_3_1_FY = first_half + "/" + time_stamp + "_" + second_half
		plt.savefig(OUT_IMG_3_1_FY, format='png', dpi=300, transparent=True)
		#sys.exit()
	elif(topt == 2):
		first_half, second_half = OUT_IMG_3_1_WS.rsplit('/',1)
		OUT_IMG_3_1_WS = first_half + "/" + time_stamp + "_" + second_half
		plt.savefig(OUT_IMG_3_1_WS, format='png', dpi=300, transparent=True)
	plt.close()
	
	#   2.   Second image: 5% footprint only.
	ax = plt.subplot(111, projection='polar')
	ax.set_theta_zero_location('N')
	ax.set_theta_direction(-1)
	theta=np.radians(dbin)
	ax.grid(True);ax.yaxis.grid(lw=1, ls='--');
	ax.plot(theta, D[:,0],'r-',lw=2.5)
	ax.plot([theta[79],theta[79]+theta[79]-theta[78]],[D[79,0],D[0,0]],'r',lw=2.5,label='5%')
	ax.set_xticks(np.arange(0,2*math.pi,2*math.pi/80))
	ax.set_xticklabels(['N','','','','','NNE','','','','','NE' \
	,'','','','','ENE','','','','','E','','','','','ESE' \
	,'','','','','SE','','','','','SSE','','','','','S' \
	,'','','','','SSW','','','','','SW','','','','','WSW' \
	,'','','','','W','','','','','WNW','','','','','NW' \
	,'','','','','NNW'])
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
		#+ '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n' \
		#+ 'Dataset: 1 Jan - 31 Dec' + '\n', va='bottom')
	elif(topt == 2):
		ax.set_title('MI Odor Print - Distance in Miles' + '\n' \
		+ '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n', va='bottom')
		#+ '( Total Odor Emission Factor = ' + str(round(E,1)) + ' )' + '\n' \
		#+ 'Dataset: 1 Apr - 31 Oct' + '\n', va='bottom')	
	# Shrink current axis by 20%
	box = ax.get_position()
	ax.set_position([box.x0, box.y0, box.width * 0.8, box.height * 0.8])

	# Put a legend to the right of the current axis
	lg=ax.legend(loc='center left', bbox_to_anchor=(1.1, 0.25))
	lg.draw_frame(False)

	if(topt == 1):
		first_half, second_half = OUT_IMG_FY.rsplit('/',1)
		OUT_IMG_FY = first_half + "/" + time_stamp + "_" + second_half
		plt.savefig(OUT_IMG_FY, format='png', dpi=300, transparent=True)
	elif(topt == 2):
		first_half, second_half = OUT_IMG_WS.rsplit('/',1)
		OUT_IMG_WS = first_half + "/" + time_stamp + "_" + second_half
		plt.savefig(OUT_IMG_WS, format='png', dpi=300, transparent=True)
	plt.close()

	#------------------------------------------------------------------------

	#---------Print formatted table to text file (later: json format)--------

	if(topt == 1):
		first_half, second_half = SETBACK_FY.rsplit('/',1)
		SETBACK_FY = first_half + "/" + time_stamp + "_" + second_half
		f_handle = file(SETBACK_FY, 'a')
	elif(topt == 2):
		first_half, second_half = SETBACK_WS.rsplit('/',1)
		SETBACK_WS = first_half + "/" + time_stamp + "_" + second_half
		f_handle = file(SETBACK_WS, 'a')	
	np.savetxt(f_handle,np.c_[['Toward Distance_in_Miles']],'%6s')
	np.savetxt(f_handle,np.c_[['       5%   3%   1.5%']],'%21s')
	wlab=np.array(['N','-','-','-','-','NNE','-','-','-','-','NE','-','-','-','-', \
	'ENE','-','-','-','-','E','-','-','-','-','ESE','-','-','-','-', \
	'SE','-','-','-','-','SSE','-','-','-','-','S','-','-','-','-', \
	'SSW','-','-','-','-','SW','-','-','-','-','WSW','-','-','-','-', \
	'W','-','-','-','-','WNW','-','-','-','-','NW','-','-','-','-', \
	'NNW','-','-','-','-'])
	mytab = np.zeros(wlab.size, dtype=[('col1', 'S6'), \
	('col2', float), ('col3', float), ('col4', float)])
	mytab['col1'] = wlab
	mytab['col2'] = np.round(Dtbl[:,0],2)
	mytab['col3'] = np.round(Dtbl[:,1],2)
	mytab['col4'] = np.round(Dtbl[:,2],2)
	np.savetxt(f_handle, mytab, fmt="%6s %4.2f %4.2f %4.2f")
	f_handle.close()

	#------------------------------------------------------------------------

	#-----------Generate KML file with footprints drawn as polygons----------

	# Step 1: Compute lat/lon at each point along the perimeter of the footprint
	LL=np.empty((81,3,2), dtype=np.float, order='F')#latitude/longitude as a function of bearing and footprint
	for d in range(0,dbin.size):
		for p in range(0,3):
			LL[d,p,1]=vincenty(miles=D[d,p]).destination(Point(latval, lonval), dbin[d]).latitude
			LL[d,p,0]=vincenty(miles=D[d,p]).destination(Point(latval, lonval), dbin[d]).longitude
	LL[80,:,:]=LL[0,:,:]#Need this to complete polygon
	# Step 2:Create kml object and draw polygons
	kml = simplekml.Kml()
	#---Mark the source location
	pnt=kml.newpoint(name="", coords=[(lonval,latval)])  # Source
	pnt.name = 'E=' +str(E)
	pnt.style.iconstyle.color = simplekml.Color.black
	pnt.style.iconstyle.scale = 1 
	pnt.style.iconstyle.icon.href = PLACE_MARK
	#---Construct polygon from points along the footprint perimeter
	#-----1.5%
	pol=kml.newpolygon(name="1.5% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,2,:]))))
	pol.style.linestyle.color = simplekml.Color.green
	pol.style.linestyle.width = 10
	pol.style.polystyle.outline = 1
	pol.style.polystyle.fill = 0
	pol.visibility=0#Hide it; user must toggle it on in Google Earth
	#-----3%
	pol=kml.newpolygon(name="3% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,1,:]))))
	pol.style.linestyle.color = simplekml.Color.blue
	pol.style.linestyle.width = 10
	pol.style.polystyle.outline = 1
	pol.style.polystyle.fill = 0
	pol.visibility=0#Hide it; user must toggle it on in Google Earth
	#-----5%
	pol=kml.newpolygon(name="5% footprint",outerboundaryis=list(tuple(map(tuple,LL[:,0,:]))))
	pol.style.linestyle.color = simplekml.Color.red
	pol.style.linestyle.width = 10
	pol.style.polystyle.outline = 1
	pol.style.polystyle.fill = 0
	# Step 3: Output kml file.
	if(topt == 1):
		first_half, second_half = SAVE_FOOTPRINT_FY.rsplit('/',1)
		SAVE_FOOTPRINT_FY = first_half + "/" + time_stamp + "_" + second_half
		kml.save(SAVE_FOOTPRINT_FY)
	elif(topt == 2):
		first_half, second_half = SAVE_FOOTPRINT_WS.rsplit('/',1)
		SAVE_FOOTPRINT_WS = first_half + "/" + time_stamp + "_" + second_half
		kml.save(SAVE_FOOTPRINT_WS)
	#------------------------------------------------------------------------

	#----------Create ESRI shapefile (only output 5% footprint)--------------

	#Mark the source location
	w = shapefile.Writer(shapefile.POINT)
	w.point(lonval,latval)
	w.field('Point')
	w.record('Odor_source')
	if(topt == 1):
		first_half, second_half = SHAPE_SOURCE_FY.rsplit('/',1)
		SHAPE_SOURCE_FY = first_half + "/" + time_stamp + "_" + second_half
		w.save(SHAPE_SOURCE_FY)
	elif(topt == 2):
		first_half, second_half = SHAPE_SOURCE_WS.rsplit('/',1)
		SHAPE_SOURCE_WS = first_half + "/" + time_stamp + "_" + second_half
		w.save(SHAPE_SOURCE_WS)
	#Draw polygon depicting footprints
	w = shapefile.Writer(shapefile.POLYGON)
	w.poly(shapeType=3,parts=[LL[:,0,:]])
	w.field('Polygon')
	w.record('5%_footprint')
	if(topt == 1):
		first_half, second_half = SHAPE_FOOTPRINT_FY.rsplit('/',1)
		SHAPE_FOOTPRINT_FY = first_half + "/" + time_stamp + "_" + second_half
		w.save(SHAPE_FOOTPRINT_FY)
	elif(topt == 2):
		first_half, second_half = SHAPE_FOOTPRINT_WS.rsplit('/',1)
		SHAPE_FOOTPRINT_WS = first_half + "/" + time_stamp + "_" + second_half
		w.save(SHAPE_FOOTPRINT_WS)
	#------------------------------------------------------------------------

#------------------------------------------------------------------------

#<<<<<<<<<<<<<<<<<<<<<<<I/O (SUBJECT TO CHANGE)<<<<<<<<<<<<<<<<<<<<<<<<<<

zip_files = []
tmpstr = OUTPUT_LOCATION + time_stamp + '_shp_footprint_FY.shx'
zip_files.append(tmpstr)
tmpstr = OUTPUT_LOCATION + time_stamp + '_shp_footprint_FY.dbf'
zip_files.append(tmpstr)
tmpstr = OUTPUT_LOCATION + time_stamp + '_shp_footprint_FY.shp'
zip_files.append(tmpstr)
tmpstr = OUTPUT_LOCATION + time_stamp + '_shp_source_FY.shx'
zip_files.append(tmpstr)
tmpstr = OUTPUT_LOCATION + time_stamp + '_shp_source_FY.shp'
zip_files.append(tmpstr)
tmpstr = OUTPUT_LOCATION + time_stamp + '_shp_source_FY.dbf'
zip_files.append(tmpstr)


#tmpstr = time_stamp + '_shp_footprint_FY.shx'
#zip_files.append(tmpstr)
#tmpstr = time_stamp + '_shp_footprint_FY.dbf'
#zip_files.append(tmpstr)
#tmpstr = time_stamp + '_shp_footprint_FY.shp'
#zip_files.append(tmpstr)
#tmpstr = time_stamp + '_shp_source_FY.shx'
#zip_files.append(tmpstr)
#tmpstr = time_stamp + '_shp_source_FY.shp'
#zip_files.append(tmpstr)
#tmpstr = time_stamp + '_shp_source_FY.dbf'
#zip_files.append(tmpstr)
tmp_file = './tmp/' + time_stamp+'_shape.zip'

shape_zip = zipfile.ZipFile(tmp_file, 'w')

tmp_str = []
for zfile in zip_files:
	tmp_str = zfile.rsplit('/',1)
	tmp_loc_file = tmp_str[1]
	shape_zip.write(zfile, arcname=tmp_loc_file, compress_type=zipfile.ZIP_DEFLATED)

shape_zip.close()

#Stop timer.
end = time.time()
#print(end - start)

#FIN