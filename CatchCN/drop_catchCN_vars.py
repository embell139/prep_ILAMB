import xarray as xr

fi = '/css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000/Y2000/M08/GEOSldas_CN40_9km.tavg24_1d_lnd_Nt.monthly.200008.nc4'

keep = ['CNNPP','CNGPP','LAI','CNSR','lon','lat']

data = xr.open_dataset(fi,decode_timedelta=True)

#breakpoint()
drop = [v for v in data.variables if v not in keep]

with open('./drop_catchCN_vars_preprocess.txt', 'w') as outfile:
  outfile.write('\n'.join(v for v in drop))

print('Saved droppable variables to drop_catchCN_vars_preprocess.txt.')
print('Done.')
