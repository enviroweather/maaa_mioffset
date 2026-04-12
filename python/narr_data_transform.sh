#!/bin/bash --login
#SBATCH --job-name=ewx_narr_transform
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=4
#SBATCH --mem=40G
#SBATCH --time=03:59:00

cd ~/docs/enviroweather/maaa-offset

# load modules known to work
ml purge
# loads Python 3.13, gcc 14.2, recent R
module load R/4.5.1-gfbf-2025a virtualenv/20.29.2 powertools
# activate our environment
source .venv/bin/activate

srun python narr_data_transform.py


# Print resource information
scontrol show job $SLURM_JOB_ID
js -j $SLURM_JOB_ID
