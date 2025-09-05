import xarray as xr
import numpy as np
import glob
import os
import cftime as cf
from datetime import datetime
import xesmf as xe
#TODO: Think through how to delete/archive old logfiles
#TODO: Figure out how to append to existing .nc files rather than start from scratch every time

# GLOBAL VARIABLES
verbose = 1
indir = '/css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000/'
ftype = 'GEOSldas_CN40_9km.tavg24_1d_lnd_Nt.monthly'
outdir = '/discover/nobackup/projects/gmao/geos_carb/embell/ilamb/data/ILAMB_sample/MODELS/CatchCN40-test/'
force_overwrite = 1
years = [2000,2010]  # inclusive range
months = [1,12]     # inclusive range

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

def main():
    with open('drop_catchCN_vars_preprocess.txt') as f:
        drop_vars = [line.replace('\n','') for line in f]
        
    print('Loading data...')
    #testt = xr.open_mfdataset(monthly_files, preprocess=preprocessing, drop_variables=drop_vars,decode_timedelta=True)
    data = load_data(years,months,drop_vars=drop_vars)

    output_variable_files(data,years,months)
    
    breakpoint()    #temp

def files_and_times(years,months):
    print('Finding Catchment-CN monthly files...')
    monthly_files = []
    times = []
    time_bounds = []
    for year in range(years[0],years[1]+1):
        for month in range(months[0],months[1]+1):
            f = glob.glob(f'{indir}/Y{year:0>4}/M{month:0>2}/*{ftype}*.nc4')[0]
            monthly_files.append(f)
            times.append(cf.DatetimeNoLeap(year, month, 1,0,0,0))  
            # Need to define time BOUNDS of each file as well 
            # First we'll need to define the NEXT month/year based on the current -  
            if month == 12:
                nmonth = 1
                nyear = year+1
            elif month < 12:
                nmonth = month+1
                nyear = year
            # And now define 'time bounds'
            time_bounds.append(
                np.array(
                    [cf.DatetimeNoLeap(year,month,1,0,0,0),cf.DatetimeNoLeap(nyear,nmonth,1,0,0,0,0)]
                )
            )        

    # Output a log of which files were used to create our output
    outloc = '/discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/output_log'
    outname = f'{outloc}/{ftype}_{datetime.today().isoformat()[0:-7]}.log'
    print(f'==> Writing list of processed input files out to {outname}.')
    with open(outname,'w') as outfile:
        outfile.write('\n'.join(f for f in monthly_files))
        
    return monthly_files,times,time_bounds,outname

def encode_time(ds,t,tb):
    if verbose:
        print('Encoding time dimension...')
    # Define 'time' coordinate and associated encoding
    ds = ds.assign_coords({'time':[t]})
    ds['time'].attrs['long_name'] = 'time'
    #ds['time'].attrs['units'] = 'days since 1850-01-01'
    #ds['time'].attrs['bounds'] = 'time_bnds'
    ds['time'].attrs['cell_methods'] = 'time: minimum'
    ds['time'].encoding['units'] = 'days since 1850-01-01'
    ds['time'].encoding['calendar'] = 'noleap'
    ds['time'].encoding['bounds'] = 'time_bnds'
    
    # Define our 'time_bounds' variable and attributes
    ds = ds.assign({'time_bnds':(('time','nv'),[tb])})
    #ds['time_bnds'].attrs['units'] = 'days since 1850-01-01'
    ds['time_bnds'].attrs['long_name'] = 'time bounds'
    
    return ds

#def regrid():

def format_variables(ds,logfile=None):
    if verbose:
        print('Formatting variables...')
    # Rename relevant variables
    ds = ds.rename(vmap)
    
    # Add derived variables
    for v in dvmap.keys():
        name = dvmap[v]['name']
        v1,v2 = v.split('-')
        ds = ds.assign({name:(ds[v1].dims, ds[v1].values - ds[v2].values)})
        ds[name].attrs['long_name'] = dvmap[v]['long_name']
        ds[name].attrs['units'] = dvmap[v]['units']
        #breakpoint()

    # Add logfile global attribute
    if logfile:
        ds.attrs['logfile'] = os.path.basename(logfile)

    return ds

def preprocessing(files,times,time_bounds,drop_vars=None,logfile=None):
    print('Adding time dimension, adjusting variable names, and concatenating monthly files...')
    for f,t,tb,i in zip(files,times,time_bounds,range(len(times))):
        print(os.path.basename(f).split('.')[-2])

        # Open native Catchment-CN monthly data
        data_month = xr.open_dataset(f,decode_timedelta=True,drop_variables=drop_vars)
        # Add your time and time bounds
        data_month = encode_time(data_month,t,tb)
        # Now adjust variable names and add derived variables
        data_month = format_variables(data_month,logfile=logfile)

        # Concatenate monthly data
        if i == 0:
            data = data_month
        else:
            data = xr.concat([data, data_month],dim='time')
        #breakpoint()

    # Finally, make sure lat and lon are set as dimensions for tile
    # This will make regridding possible later
    # This step sets lat and lon as a MultiIndex
    data = data.set_index(tile=['lat','lon'])

    return data

def load_data(years,months,drop_vars=None):
    files,times,time_bounds,logfile = files_and_times(years,months)
    data = preprocessing(files,times,time_bounds,drop_vars=drop_vars,logfile=logfile)

    return data

def output_variable_files(ds,years,months):
    # Add contact info 
    ds.attrs['CreatedBy'] = 'Emily Bell, emily.i.bell@nasa.gov'
    keep_dims = ['lon','lat','time','time_bnds']
    for v in ds.variables:
        if v in keep_dims:
            continue
        else:
            keep_dims_temp = keep_dims.copy()
            keep_dims_temp.append(v)
            drop_vars = [n for n in ds.variables if n not in keep_dims_temp]
            
            ds_temp = ds.drop_vars(drop_vars)

            # Check for the appropriate variable-specific directory and create it if it doesn't exist yet
            if not os.path.exists(outdir+v+'/'):
                print(f'Creating directory {outdir}{v}/')
                os.mkdir(outdir+v+'/')

            # Add creation time
            ds.attrs['Date'] = datetime.today().isoformat()
             
            outfile = f'{outdir}{v}/{v}_{ftype}_{years[0]}{months[0]}-{years[1]}{months[1]}.nc'

            print(outfile)  #temp

            print(f'\n==> Saving {v} for full time period as {outfile}.')
            ds_temp.to_netcdf(outfile,format='NETCDF4')

def draft_stuff():
    
    #    for month in range(start_month,stop_month+1):
    #        print(f'{year}, Month {month}')
    #        # read the (monthly average?) file
    #        fname = f'{indir}Y{year:0>4}/M{month:0>2}/*{ftype}*.nc4'
    #        f = glob.glob(fname)[0]
    #        fout = outdir+'gpp_'+os.path.basename(f).replace('.nc4','-ILAMB.nc')
    #        if os.path.exists(fout):
    #            if force_overwrite:
    #                print('Overwriting previous ILAMB-formatted file')
    #            else:
    #                continue
    #        data = xr.open_dataset(f,decode_timedelta=True)
    #        #breakpoint()
    #        # First, get rid of variables we don't need for ILAMB
    #        to_drop = [v for v in data.variables if v not in vmap.keys()]
    #        data = data.drop_vars(to_drop)
    #
    #        # Before we write out we also need to create a time *coordinate*
    #        data = data.assign_coords({'time':[cf.DatetimeNoLeap(year, month, 1,0,0,0)]})
    #    
    #        #breakpoint()
    #        # Write to netCDF
    #        print('Writing '+fout)
    #        data.to_netcdf(fout,format='NETCDF4')
    #        del data
    print('Done')



if __name__=='__main__':
    main()
