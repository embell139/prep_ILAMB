import xarray as xr
import numpy as np
import glob
import os
import cftime as cf
from datetime import datetime
import sys
from scipy.interpolate import griddata
from scipy.spatial import cKDTree
from tqdm import tqdm
import time

# GLOBAL VARIABLES
verbose = 1

degout = {'lat':0.1,'lon':0.1}
indir = '/css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000/'
ftype = 'GEOSldas_CN40_9km.tavg24_1d_lnd_Nt.monthly'
outdir = '/discover/nobackup/projects/gmao/geos_carb/embell/ilamb/data/ILAMB_sample/MODELS/CatchCN40-test/'
force_overwrite = 1

# map native variable names to CF variable names
vmap = {
    'CNNPP':'npp',
    'CNGPP':'gpp',
    'LAI':'lai',
    'CNSR':'re',
    'lon':'lon',
    'lat':'lat'
}

# then we can use those new variables to define some derived variables
dvmap = {
    'gpp-npp':{
        'name':'rh',
        'long_name':'heterotrophic_respiration',
        'units':'kg m-2 s-1'
    },
    're-rh':{
        'name':'ra',
        'long_name':'autotrophic_respiration',
        'units':'kg m-2 s-1'
    }
}

##########################
##########################
#       MAIN
##########################
##########################
def main():
    args = parse_args()

    try:
        start_year,stop_year = args.years
    except:
        print('\n!!==> Missing the required --years argument.')
        sys.exit()

    start_month,stop_month = args.months
    for year in years:
        for month in months:
            ms = datetime(year,month,1).strftime('%m')  # zero-padded month number

            # Construct input filename
            try: 
                ss = f'{args.indir}Y{year:0>4}/M{month:0>2}/*{args.filetype}*.nc4'
            except:
                print('\n!!==> Missing the required --indir or --filetype argument.')
                sys.exit() 

            # Locate input file
            try: 
                infile = glob.glob(ss)[0]
            except:
                print(f'!!==> No file found matching search string {ss}')
                sys.exit()

            # Construct output filename
            try:
                fout = args.outdir+os.path.basename(f).replace('.nc4',f'{args.suffix}.nc')
                if args.verbose:
                    print(f'• Outfile: {fout}')
            except:
                print('\n!!==> Missing the required --outdir or --filetype argument.')
                sys.exit()

            # Check for existing output file and overwrite if specified
            if os.path.exists(fout):
                if args.force_overwrite:
                    print('Overwriting previous ILAMB-formatted file')
                else:
                    continue

            # Open original Catchment-CN file            
            df = xr.open_dataset(infile, decode_timedelta=True)
            print(f'Reading {infile}')

            # Reformat variables for ILAMB
            df = variable_preprocessing(df)

            # Regrid onto a regular grid defined by degout
            df_regrid = regrid(df)

            # Add the time variable and calendar encoding
            df_regrid = time_encoding(df_regrid,year,month)
           
            # Write to netCDF
            print('Writing '+fout)
            df.to_netcdf(fout,format='NETCDF4')
            del df


########################
#   Argument parser
########################
def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument('--indir',type=str,
        help='Input directory'
    )
    parser.add_argument('--outdir',type=str,
        help='Output directory'
    )
    parser.add_argument('--filetype',type=str,
        default='*',
        help='File type, a substring to use when doing a glob search.'
    )
    parser.add_argument('--years',nargs=2,type=int,
        metavar=('Start','End'),
        help='Start and end years, inclusive. e.g. --years 2020 2025'
    )
    parser.add_argument('--months',nargs=2,type=int,default=[1,12],
        metavar=('Start','End'),
        help='Start and end months, inclusive. Defaults: %(default)s. e.g. --months 1 12'
    )
    parser.add_argument('--suffix',type=str,
        default='-ILAMB',
        help='Suffix to add to filename when writing out changes.')

    parser.add_argument('-v','--verbose',
        action='store_true',
        help='Verbose output')

    parser.add_argument('-f','--force_overwrite',
        action='store_true',
        help='Force overwrite of any existing output files'
    )


    args = parser.parse_args()
    return parser.parse_args()


def variable_preprocessing(df):
    """ 
    Drops variables not used in ILAMB, 
    renames remaining variables per CF conventions,
    adds a couple of derived variables for convenience.
    """ 

    # Get rid of variables we don't need for ILAMB
    try:
        df = df.drop_vars(to_drop)
    except NameError:
        # to_drop hasn't been defined yet - let's do that
        to_drop = [v for v in df.variables if v not in vmap.keys()]
        df = df.drop_vars(to_drop)

    # Next, rename relevant variables
    df = df.rename(vmap)

    # Finally, add derived variables
    for v in dvmap.keys():
        name = dvmap[v]['name']
        v1,v2 = v.split('-')
        df = df.assign({name:(df[v1].dims,df[v1].values-df[v2].values)})
        df[name].attrs['long_name']=dvmap[v]['long_name']
        df[name].attrs['units']=dvmap[v]['units']
        #breakpoint()

    return df
    

def regrid(df):
    """ 
    Regrids native data onto the resolution
    specified by `degout`. 
    Also applies NaN values to any points on the
    new lat/lon grid which are too far from the original data points 
    (avoids interpolating into areas with no data).
    """
    target_lats = np.arange(-90,90,degout['lat'])
    target_lons = np.arange(-180,180,degout['lon'])
    lon_grid,lat_grid = np.meshgrid(target_lons,target_lats)    # 2D lat/lon matrix

    print(f'Regridding data onto {degout['lon']}x{degout['lat']} degrees')

    # Create your output DataFrame
    df_regridded = xr.Dataset(
        coords={
            'lon':(['lon'],target_lons),
            'lat':(['lat'],target_lats)
        }
    )

    # perform interpolation with scipy griddata
    model_points = np.column_stack((df['lon'].values,df['lat'].values)) # list of [lon,lat] pairs from model data
    target_points = np.column_stack((lon_grid.ravel(),lat_grid.ravel()))    # list of [lon,lat] pairs from target grid

    # Now we need to set the ocean points to zero because there is no data over ocean in the original dataset!
    # First, calculate the distance between target grid lon/lat points and original model lon/lat points -
    ocean_mask = calc_distances(target_points,model_points)

    #breakpoint()
    grid_start = time.time()
    for var in df.variables:
        grid_values = griddata(
            model_points,               # 1D list of [lon,lat] pairs from model
            df[var].values.flatten(),   # 1D list of data values
            target_points,              # 1D list of [lon, lat] pairs from target grid
            method='linear',
            fill_value=np.nan
        )
        # The result: grid_values is a 1D list of data values corresponding to each [lon,lat] pair from the target grid.t

        # Apply ocean mask
        grid_values[ocean_mask] = np.nan

        # Put it back into 2D
        final_values = grid_values.reshape(lon_grid.shape)
        
        # Add it to the new xarray dataset
        df_regridded[var] = (['lon','lat'],final_values) 

    grid_time = time.time() - grid_start
    print(f'⧖ Regridding variables took {grid_time:.2f} seconds')

    return df_regridded


def calc_distances(target_points,model_points,batch_size=10000,max_distance=0.1):
    """ 
    Uses batch processing and a k-d tree
    to calculate Euclidean distances between data points
    and return a mask for points further apart than 
    the specified `max_distance`.
    See comments for detailed walk-through.
    """
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
            # tqdm package and the lines below produce a progress bar
            # to indicate how far we are through this loop and report some timing details
            pbar.update(end_index-i)
            pbar.set_postfix({
                'batch_time':f'{batch_time:.2f}s',
                'rate':f'{(end_index-i)/batch_time:,.0f} pts/sec'

            })

    total_time = time.time()-total_start
    print(f'⧖ Total time for batch processing k-d tree: {total_time:.2f} seconds')

    #breakpoint()
    return distance_mask


def time_encoding(df,year,month):
    """ 
    Adds a time coordinate, time_bounds attribute, and calendar attribute.
    """
    # Before we write out we also need to create a time *coordinate*
    df = df.assign_coords({'time':[cf.DatetimeNoLeap(year, month, 1,0,0,0)]})
    df['time'].attrs['long_name'] = 'time'
    #df['time'].attrs['units'] = 'days since 1850-01-01'
    #df['time'].attrs['bounds'] = 'time_bnds'
    df['time'].attrs['cell_methods'] = 'time: minimum'
    df['time'].attrs['calendar'] = 'noleap'
    df['time'].encoding['units'] = 'days since 1850-01-01'
    df['time'].encoding['calendar'] = 'noleap'
    df['time'].encoding['bounds'] = 'time_bnds'
    if month == 12:
        nmonth = 1
        nyear = year+1
    elif month < 12:
        nmonth = month+1
        nyear = year
 
    # And define the cell/timestep's *time bounds*
    tb = np.array(
        [cf.DatetimeNoLeap(year,month,1,0,0,0),cf.DatetimeNoLeap(nyear,nmonth,1,0,0,0,0)]
    )
    df = df.assign({'time_bnds':(('time','nv'),[tb])})
    #df['time_bnds'].attrs['units'] = 'days since 1850-01-01'
    df['time_bnds'].attrs['long_name'] = 'time bounds'
    #breakpoint()

    return df
    

if __name__=='__main__':
    main()
