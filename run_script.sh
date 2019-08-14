#!/bin/bash -l

# USE THIS FOR DEBUGGING/TESTING
#singularity shell docker://buildkite/puppeteer

# Modify this to be the installation directory of the monitor
cd ~/cron/monitoring/grafana-monitor/new/data-flow-monitor

# If the virtual environment isn't set up, do so first
if [ ! -d python-virtualenv ]; then
    ./install_venv.sh
fi

# Now activate the venv
source python-virtualenv/bin/activate

# Ensure we are using the correct version of singularity
module load singularity/2.6

# Execute the scraper using puppeteer in a container
singularity exec docker://buildkite/puppeteer node grafana-automation.js

# Following execution, data.json will be produced. Now process it
python2 data_processor.py

# After completion, deactivate virtualenv
deactivate
