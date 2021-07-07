#!/bin/bash

set -e

if [ ! -d $HOME/data-flow-monitor ]; then
    echo "data-flow-monitor not installed to home directory; please move it to $HOME and try again"
    exit 1
fi

cd $HOME/data-flow-monitor

# Install venv if not already setup
if [ ! -d python-venv ]; then
    echo "data-flow-monitor virtual env does not exist; now creating..."
    ./install_venv.sh
    echo "data-flow-monitor virtual env created"
fi

# Activate venv
source python-venv/bin/activate

# Run the script with the virtual env
python data_processor.py token.txt

# Deactivate
deactivate
