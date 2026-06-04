# new_fod.py MODEL ONLY python 2 

import numpy as np
import math

#--------------------------Variable definitions--------------------------

# wc: Frequency of each wind-stability class (float)
# f:  Wind-stability class that occurs closest to but not 
#     greater than 5%, 3%, and 1.5% of the time (integer)
# D:  Setback distance, computed as a function of wind 
#     stability class using OFFSET look-up tables (float)
# odor_index:  Total Odor Emission Factor (float)

def legacy_fod_model(WD: np.ndarray, WS: np.ndarray, PC: np.ndarray, odor_index: float):

    #-----------------------Wind direction processing------------------------

    # Remove spikes in histogram at cardinal wind directions (90,180,270,360) 
    # The spikes are the result of truncating rather than rounding the 
    # u- and v- components to the nearest tenth of a meter per second. 
    #indx=np.random.permutation(WD.size) #original line
    indx=np.random.RandomState(seed=8675309).permutation(WD.size) #tracy - add replacement line per email from Mike Kiefer 2/24/2020 2:13pm
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

            #	


    Isum=np.sum(i4,1)
    I1=Isum>0
    I2=I1.astype(int)
    WDds=np.copy(WD)
    WDds[I2==1]=-999

    #--------Footprint preliminary step 1: compute "windstar chart"----------

    # Proceeding clockwise around wind rose, determine frequency of 
    # each wind-stability class.
    # When plotted, one gets a "windstar chart", as presented in Figure 1 in:
    # Jacobson, L.D., H. Guo, D.R. Schmidt, R.E. Nicolai, J. Zhu, K.A. Janni,
    # 2005. Development of the OFFSET model for determination of 
    # odor-annoyance-free setback distances from animal production sites: 
    # Part I. Review and experiment. Transactions of the ASAE, 48(6).
    dbin=np.arange(11.25,360,22.5)
    wc = np.zeros((16,6), dtype=float, order='F')
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


    f = np.zeros((5*dbin.size,3), dtype=int, order='F')
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

    #-------Footprint preliminary step 3: compute setback distance (D)-------

    # Formula that follows, D = aE^b, along with empirical coefficients
    # [converted from meters to feet], obtained from:
    # Guo, H., L.D. Jacobson, D.R. Schmidt, R.E. Nicolai, J. Zhu, K.A. Janni, 2005. Development of the OFFSET model for determination of odor-annoyance-free setback distances from animal production sites: Part II. Model development and evaluations. Transactions of the ASAE, 48(6).

    # Total odor emission factor (E):
    # Product of source area, odor emission number, and odor control factor, 
    # divided by 10000, summed over all sources.
    D = np.zeros((5*dbin.size,3), dtype=float, order='F')
    for d in range (0,5*dbin.size):
        for p in range (0,3):
            if (f[d,p] == 1):
                D[d,p]=0.1181*math.pow(odor_index,0.5132) # Class 1
            elif (f[d,p] == 2):
                D[d,p]=0.0634*math.pow(odor_index,0.5366) # Class 2
            elif (f[d,p] == 3):
                D[d,p]=0.0399*math.pow(odor_index,0.5397) # Class 3   
            elif (f[d,p] == 4):
                D[d,p]=0.0242*math.pow(odor_index,0.5844) # Class 4   
            elif (f[d,p] == 5):  
                D[d,p]=0.0175*math.pow(odor_index,0.5827) # Class 5
            elif (f[d,p] == 6):
                D[d,p]=0.0101*math.pow(odor_index,0.6264) # Class 6   
                
    return D


