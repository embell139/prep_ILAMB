#!/bin/bash
# SBATCH --job-name=caltest
# SBATCH --account=s1460
# SBATCH --time=00:30:00
# SBATCH --output=/discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/MiCASA/logs/caltest_%j.out
# SBATCH --error=/discover/nobackup/projects/gmao/geos_carb/embell/prep_ilamb/MiCASA/logs/caltest_%j.err

dates=( 2001 2002 2003 2004 )

INDIR="/css/gmao/geos_carb/pub/MiCASA/v1/netcdf/monthly"
OUTDIR="/discover/nobackup/projects/gmao/geos_carb/embell/ilamb/data/ILAMB_sample/MODELS/MiCASA-TEST-Monthly-2001-2004"

# -p flag here means that it will not create the directory OR throw an error
# if the directory already exists
mkdir -p "$OUTDIR"

module purge
module load nco

for date in ${dates[@]}; do
    #echo $date
    for file in "${INDIR}"/"${date}"/*.nc4; do
        #echo -e "\n ${INDIR}/${date}/*.nc4"
        if [ -f "$file" ]; then
            #echo "Adding calendar attribute to ${file}"
            basename=$(basename "$file" .nc4)
            OUTFILE="${OUTDIR}/${basename}_eibcal.nc4"

            #echo -e "-> Infile: ${file}"
            #echo -e "-> Outfile: ${OUTFILE}"
    
            # Check if output file already exists
            if [ -f "$OUTFILE" ]; then
                echo -e "\n  ⏭ Skipping $file (output already exists: $OUTFILE)"
                continue
            fi
            
            # Make a copy of the original file
            cp "$file" "$OUTFILE"
    
            if [ $? -eq 0 ]; then
                echo -e "\n  ✓ Successfully created $OUTFILE"
            else
                echo -e "\n  ✗✗✗✗✗✗ Failed to create $OUTFILE"
                exit 1
            fi
        
            # Add the calendar attribute to the new copy
            ncatted -O -a calendar,time,c,c,"standard" "$OUTFILE"
            if [ $? -eq 0 ]; then
                echo -e "\n  ✓ Successfully added calendar attribute"
            else
                echo -e "\n  ✗✗✗✗✗✗ Failed to add calendar attribute"
                exit 1 
            fi
    
        fi
    done
done
