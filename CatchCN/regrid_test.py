#import xesmf as xe
import xarray as xr
import matplotlib.pyplot as plt
import numpy as np
import sys
import os
import glob
import cartopy.feature as cf
import cartopy.crs as ccrs
import datetime
from scipy.interpolate import griddata

var = 'CNNPP'

years = [2006]
months = [1,4,8,12]

latrange = [-8,0.7]
lonrange = [-60,-48]

degout = {'lat':0.1,'lon':0.1}

indir = '/css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000'
filetype = 'lnd_Nt.monthly'

plotdir = '/discover/nobackup/projects/gmao/geos_carb/embell/images/spot_check'
inplot = 'CatchCN_testplot.png'
outplot = inplot.replace('CatchCN','CatchCN_regrid')

def scatterplot(df,var,title=None,savename=None,latrange=None,lonrange=None):
    plt.close('all')
    print('Creating scatterplot')
    fig = plt.figure()
    ax = fig.add_subplot(projection=ccrs.PlateCarree())
    ax.coastlines()
    plt.scatter(df['lon'].values, df['lat'].values, c=df[var].values, s=0.25, transform=ccrs.PlateCarree())
    plt.colorbar(ax=ax)
    if title:
        plt.title(title)
    if latrange:
        plt.ylim(latrange)
    if lonrange:
        plt.xlim(lonrange)
    if savename:
        print(f'Saving to {savename}.')
        plt.savefig(savename,bbox_inches='tight')

# xESMF method might not work since our original lat/lons are irregular
#def regrid(df):
#    df_grid = f
#
#    target_grid = xr.Dataset({
#        'lat':(['lat'],np.arange(-90,90,degout['lat'])),
#        'lon':(['lon'],np.arange(-180,180,degout['lon']))
#    })
#
#    regridder = xe.Regridder(df,df_out,method='conservative')
#
#    return regridder(df)

def dfplot(df):
    fig = plt.figure()
    ax = fig.add_subplot(projection=ccrs.PlateCarree())
    ax.coastlines()
    df[var].plot(cmap=viridis)

def regrid(df):
    target_lats = np.arange(-90,90,degout['lat'])
    target_lons = np.arange(-180,180,degout['lon'])
    lon_grid,lat_grid = np.meshgrid(target_lons,target_lats)
 
    print(f'Regridding {var} onto {degout['lon']}x{degout['lat']} degrees')
    # perform interpolation with scipy griddata
    xy_points = np.column_stack((df['lon'].values,df['lat'].values)) 
    #breakpoint()
    grid_values = griddata(xy_points,df[var].values.flatten(),(lon_grid,lat_grid),method='linear',fill_value=np.nan)
    
    df_regridded = xr.Dataset(
        data_vars={
            var:(['lat','lon'],grid_values)
        },
        coords={
            'lon':(['lon'],target_lons),
            'lat':(['lat'],target_lats)
        }
    )
    
    return df_regridded

for year in years:
    for month in months:
        ms = datetime.datetime(year,month,1).strftime('%m')     # zero-padded month number
        ss = f'{indir}/Y{year}/M{ms}/*{filetype}.*'
        try:
            infile = glob.glob(ss)[0]
        except:
            print(f'!!==> No file found matching search string {ss}')
            sys.exit()

        df = xr.open_dataset(infile,decode_timedelta=True)
        print(f'Reading {infile}')

        
        savename = inplot.replace('_testplot.png',f'_{var}_{year}{ms}_testplot.png')
        scatterplot(df,var,
            savename=f'{plotdir}/{savename}',
            title=f'CatchCN original, {year}{ms}',
            latrange=latrange,
            lonrange=lonrange
        )

        savename = outplot.replace('_testplot.png',f'_{var}_{year}{ms}_testplot.png')
        df_regrid = regrid(df)
        #breakpoint()

        

        breakpoint()
        sys.exit()

