import xesmf as xe
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np
import sys
import os
import glob
import cartopy.feature as cf
import cartopy.crs as ccrs

years = [2006]
months = [1,4,8,12]

indir = '/css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000/'
filetype = 'lnd_Nt.monthly'

plotdir = '/discover/nobackup/projects/gmao/geos_carb/embell/images/spot_check'
inplot = 'CatchCN_[VAR]_testplot_[YYYY][MM].png'
outplot = inplot.replace('_[VAR]','_regrid_[VAR]')

def scatterplot(df,var,savename=None,latrange=None,lonrange=None):

for year in years:
    for month in months:
        ss = f'{indir}/*{filetype}.*'
        infile = glob.glob(ss)[0]
        try:
            df = xr.open_dataset(infile)
        except:
            print(f'!!==> No file found matching search string {ss}')
            sys.exit()
        

