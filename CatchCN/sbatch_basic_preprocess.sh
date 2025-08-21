#!/bin/bash
# SBATCH --job-name=catch_prepr
# SBATCH --output=/discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/output_log/catch_prepr_%j.out
# SBATCH --error=/discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/output_log/catch_prepr_%j.err
# SBATCH --time=00:30:00
# SBATCH --account=s1460
# SBATCH --no-requeue

module purge

srun python basic_catchCN_preprocess.py \
    --indir /css/gmao/geos_carb/archive/jkolassa/GEOSldas_CN40_9km/output/SMAP_EASEv2_M09_GLOBAL/cat/ens0000/ \
    --outdir /discover/nobackup/projects/gmao/geos_carb/embell/ilamb/data/ILAMB_sample/MODELS/CatchCN40-native_file_res/ \
    --filetype lnd_Nt.monthly \
    --years 2006 2010 \
    -f \    # this option forces an overwrite of existing files
    > /discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/output_log/catch_prepr_test.log
    
