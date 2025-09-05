import xarray as xr
import numpy as np
import glob
import os
import cftime as cf
import argparse
import sys
import xesmf as xe

"""
This script is used to:
- adjust variable names to match CF conventions
- add lat and lon as indices, not just as variables
- add a time coordinate
- remove extraneous variables 
from original Catchment-CN files (faster I/O smaller files?)

The resulting output will be in the same time resolution as the original files.
"""

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

def main():
    args = parse_args()
    
    try:
        start_year,stop_year = args.years
    except:
        print('\n!!==> Missing the required --years argument.')
        sys.exit()

    start_month,stop_month = args.months
    
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
    # you could also just define derived variables in ILAMB config files 
    # but i'll test it here
    dvmap = {
        'gpp-npp':{
            'name':'rh',
            'long_name':'heterotrophic_respiration',
            'units':'kg m-2 s-1',
            'description':'CNGPP - CNNPP'
        },
        're-rh':{
            'name':'ra',
            'long_name':'autotrophic_respiration',
            'units':'kg m-2 s-1',
            'description':'CNSR-(CNGPP-CNNPP)'
        }
    }
    
    # Loop through monthly files
    for year in range(start_year,stop_year+1):
        for month in range(start_month,stop_month+1):
            print(f'{year}, Month {month}')

            # read the monthly average file
            try:
                fname = f'{args.indir}Y{year:0>4}/M{month:0>2}/*{args.filetype}*.nc4'
            except:
                print('\n!!==> Missing the required --indir or --filetype argument.')
                sys.exit()
            
            f = glob.glob(fname)[0]
            if args.verbose:
                print(f'• Infile: {f}')

            # Construct output filename
            try:
                fout = args.outdir+os.path.basename(f).replace('.nc4',f'{args.suffix}.nc')
                if args.verbose:
                    print(f'• Outfile: {fout}')
            except:
                print('\n!!==> Missing the required --outdir or --filetype argument.')
                sys.exit()

            #continue    # DEBUG
            if os.path.exists(fout):
                if args.force_overwrite:
                    print('Overwriting previous ILAMB-formatted file')
                else:
                    continue

            # read input data
            data = xr.open_dataset(f,decode_timedelta=True)
            #breakpoint()
    
            # First, get rid of variables we don't need for ILAMB
            try:
                data = data.drop_vars(to_drop)
            except NameError:
                # to_drop hasn't been defined yet - let's do that
                to_drop = [v for v in data.variables if v not in vmap.keys()]
                data = data.drop_vars(to_drop)
    
            # Next, rename relevant variables
            data = data.rename(vmap)
            # Finally, add derived variables
            for v in dvmap.keys():
                name = dvmap[v]['name']
                v1,v2 = v.split('-')
                data = data.assign({name:(data[v1].dims,data[v1].values-data[v2].values)})
                data[name].attrs['long_name']=dvmap[v]['long_name']
                data[name].attrs['units']=dvmap[v]['units']
                #breakpoint()
    
            # Set lat/lon as indices
            data = data.set_index(tile=['lat','lon'])
    
            # Before we write out we also need to create a time *coordinate*
            data = data.assign_coords({'time':[cf.DatetimeNoLeap(year, month, 1,0,0,0)]})
            data['time'].attrs['long_name'] = 'time'
            #data['time'].attrs['units'] = 'days since 1850-01-01'
            #data['time'].attrs['bounds'] = 'time_bnds'
            data['time'].attrs['cell_methods'] = 'time: minimum'
            data['time'].attrs['calendar'] = 'noleap'
            data['time'].encoding['units'] = 'days since 1850-01-01'
            data['time'].encoding['calendar'] = 'noleap'
            data['time'].encoding['bounds'] = 'time_bnds'
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
            data = data.assign({'time_bnds':(('time','nv'),[tb])})
            #data['time_bnds'].attrs['units'] = 'days since 1850-01-01'
            data['time_bnds'].attrs['long_name'] = 'time bounds'
            #breakpoint()
    
            # Write to netCDF
            print('Writing '+fout)
            data.to_netcdf(fout,format='NETCDF4')
            del data
    
    print('Done')

if __name__ == '__main__':
    main()
