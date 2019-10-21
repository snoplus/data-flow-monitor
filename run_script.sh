#!/bin/bash -l

# USE THIS FOR DEBUGGING/TESTING
#singularity shell docker://buildkite/puppeteer

# Make the script safe
#set -eox pipefail

# Modify this to be the installation directory of the monitor
cd ~/cron/monitoring/data-flow-monitor

# If the virtual environment isn't set up, do so first
if [ ! -d python-virtualenv ]; then
    ./install_venv.sh
fi

# Now activate the venv
source python-virtualenv/bin/activate

# Ensure we are using the correct version of singularity
module load singularity/3.2

# Execute the scraper using puppeteer in a container
singularity exec puppeteer.img node grafana-automation.js

# Following execution, data.json will be produced. Now process it
python2 data_processor.py

# After completion, deactivate virtualenv
deactivate
