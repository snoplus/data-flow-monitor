#!/bin/bash -l

# Modify this to be the installation directory of the monitor
cd ~/cron/monitoring/data-flow-monitor

# Install venv if not already setup
if [ ! -d ~/monitoring/data-flow-monitor/python-venv ]; then
    ./install_venv.sh
fi

# Activate venv
source python-venv/bin/activate

# Run the script with the virtual env
python2 data_processor.py

# Deactivate
deactivate
