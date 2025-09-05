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
from scipy.spatial.distance import cdist
from scipy.spatial import cKDTree
from tqdm import tqdm
import time

var = 'CNNPP'

years = [2006]
months = [1,4,8,12]

latrange = [4.1,14.6]
lonrange = [113.1,128.4]

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
    plt.scatter(df['lon'].values, df['lat'].values, c=df[var].values, s=0.5, transform=ccrs.PlateCarree())
    cbar = plt.colorbar(ax=ax)
    if title:
        plt.title(title)
    if latrange:
        plt.ylim(latrange)
    if lonrange:
        plt.xlim(lonrange)
    if savename:
        print(f'Saving to {savename}.')
        plt.savefig(savename,bbox_inches='tight')

    #breakpoint()
    cbrange = [float(cbar.__dict__['vmin']),float(cbar.__dict__['vmax'])]
    
    return cbrange 

def dfplot(df,var,latrange=None,lonrange=None,savename=None,title=None,**kwargs):
    plt.close('all')
    print('Creating regridded plot')
    fig = plt.figure()
    ax = fig.add_subplot(projection=ccrs.PlateCarree())
    ax.coastlines()
    df[var].plot(cmap='viridis',**kwargs)
    if title:
        plt.title(title)
    if latrange:
        plt.ylim(latrange)
    if lonrange:
        plt.xlim(lonrange)
    if savename:
        print(f'Saving to {savename}.')
        plt.savefig(savename,bbox_inches='tight')

    return

def calc_distances(target_points,model_points,batch_size=10000,max_distance=0.1):
    print('Calculating distances between regridded points and original points...')
    # Our dataset is too big to calculate distances between ALL points
    # using some method like scipy.spatial.distance.cdist,
    # so we need to take a more memory-efficient approach.
    # 
    # First, we'll process the data in batches (the loop).
    #
    # We'll also use a k-d tree to find nearest neighbors only. Wikipedia: https://en.wikipedia.org/wiki/K-d_tree
    # "The tree doesn't know or care what units you're using - it just performs Euclidean distance calculations on 
    # the raw numbers you provide."
    # Euclidean distance calculations assume that you're measuring by laying a ruler on a flat plane, basically.
    # This is an acceptable estimation in our case because we're working with fine enough spatial resolution.
    
    # We build a tree from our model points:
    tree = cKDTree(model_points) 

    # And we initialize a mask to identify points too far from the original 
    distance_mask = np.zeros(len(target_points),dtype=bool)

    total_start = time.time()
    with tqdm(total=len(target_points), desc="Processing points", unit="points") as pbar:
        for i in range(0,len(target_points),batch_size):
            batch_start = time.time()
            end_index = min(i+batch_size,len(target_points))
    
            # To find the distance to the nearest model point (k=1) for each target gridpoint:
            distances, indices = tree.query(target_points[i:end_index],k=1)   
     
            # Now we can say which points from the target grid should not be filled in by model data  
            # because they're too far away from any of the original data.
            # We can apply this as a mask to our gridded values!
            distance_mask[i:end_index] = distances > max_distance

            batch_time = time.time() - batch_start
            pbar.update(end_index-i)
            pbar.set_postfix({
                'batch_time':f'{batch_time:.2f}s',
                'rate':f'{(end_index-i)/batch_time:,.0f} pts/sec'
                
            })

    total_time = time.time()-total_start
    print(f'⧖ Total time for batch processing k-d tree: {total_time:.2f} seconds')

    #breakpoint()
    return distance_mask

def regrid(df):
    target_lats = np.arange(-90,90,degout['lat'])
    target_lons = np.arange(-180,180,degout['lon'])
    lon_grid,lat_grid = np.meshgrid(target_lons,target_lats)    # 2D lat/lon matrix
 
    print(f'Regridding {var} onto {degout['lon']}x{degout['lat']} degrees')

    # perform interpolation with scipy griddata
    model_points = np.column_stack((df['lon'].values,df['lat'].values)) # list of [lon,lat] pairs from model data
    target_points = np.column_stack((lon_grid.ravel(),lat_grid.ravel()))    # list of [lon,lat] pairs from target grid 
    #breakpoint()
    grid_start = time.time()
    grid_values = griddata(
        model_points,               # 1D list of [lon,lat] pairs from model
        df[var].values.flatten(),   # 1D list of data values
        target_points,              # 1D list of [lon, lat] pairs from target grid
        method='linear',
        fill_value=np.nan
    )
    grid_time = time.time() - grid_start
    print(f'⧖ Regridding {var} took {grid_time:.2f} seconds')

    # The result: grid_values is a 1D list of data values corresponding to each [lon,lat] pair from the target grid.t

    # Now we need to set the ocean points to zero because there is no data over ocean in the original dataset!
    # First, calculate the distance between target grid lon/lat points and original model lon/lat points - 
    ocean_mask = calc_distances(target_points,model_points)

    grid_values[ocean_mask] = np.nan

    # Put it back into 2D
    final_values = grid_values.reshape(lon_grid.shape)
    
    # Create your output DataFrame 
    df_regridded = xr.Dataset(
        data_vars={
            var:(['lat','lon'],final_values)
        },
        coords={
            'lon':(['lon'],target_lons),
            'lat':(['lat'],target_lats)
        }
    )
    
    return df_regridded

####################
# MAIN CODE
####################
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

        # Scatterplot of original data
        savename = inplot.replace('_testplot.png',f'_{var}_{year}{ms}_testplot.png')
        vmin,vmax = scatterplot(df,var,
            title=f'CatchCN original, {year}{ms}',
            latrange=latrange,
            lonrange=lonrange,
            savename=f'{plotdir}/{savename}',
        )
        #breakpoint()

        # pcolormesh of regridded data
        savename = outplot.replace('_testplot.png',f'_{degout['lon']}x{degout['lat']}deg_{var}_{year}{ms}_testplot.png')
        df_regrid = regrid(df)
        dfplot(df_regrid,var,
            title=f'CatchCN regridded, {year}{ms}, {degout['lon']}x{degout['lat']}deg',
            savename=f'{plotdir}/{savename}',
            latrange=latrange,
            lonrange=lonrange,
            **{'vmin':vmin,'vmax':vmax}
        )
        #breakpoint()

        

        #breakpoint()
        sys.exit()

