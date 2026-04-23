#!/bin/bash --login
#SBATCH --job-name=ewx_narr_transform
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=2
#SBATCH --mem=1G
#SBATCH --time=01:45:00
#SBATCH --output=logs/narr_transform_%j.out
#SBATCH --error=logs/narr_transform_%j.err
#SBATCH --array=6-277

# max x = 277

cd /mnt/home/billspat/docs/enviroweather/maaa_mioffset

# load modules known to work
# we don't need the R stuff but there seems to an issue finding things
ml purge
# loads Python 3.13, gcc 14.2, recent R
module load R/4.5.1-gfbf-2025a virtualenv/20.29.2 powertools
# fun with geo-spatial ecology!
module load GEOS/3.13.1-GCC-14.2.0 GDAL/3.11.1-foss-2025a UDUNITS/2.2.28-GCCcore-14.2.0
export R_LIBS_USER=/mnt/ffs24/home/billspat/R/x86_64-pc-linux-gnu-library/4.5
export R_LIBS=$R_LIBS_USER

# activate our environment
source .venv/bin/activate

# run from the script folder
cd python
echo "x coordinate = $SLURM_ARRAY_TASK_ID"
echo "----"
python ../src/mioffset/narr_data_transform.py ${SLURM_ARRAY_TASK_ID}
echo "----"

if [ -n "$SLURM_JOB_ID" ]; then
  scontrol show job $SLURM_JOB_ID
  js -j $SLURM_JOB_ID
fi
