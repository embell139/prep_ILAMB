module purge

python preprocess_catchCN_final.py \
    --indir /css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000/ \
    --outdir /discover/nobackup/projects/gmao/geos_carb/embell/ilamb/data/ILAMB_sample/MODLES/CatchCN40-native_file_res/ \
    --filetype lnd_Nt.monthly \
    --years 2006 2010 \
    --suffix _ILAMB \
    -f  # forces overwrite of existing files
    > /discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/output_log/catchCN_preprocessing_test.log
