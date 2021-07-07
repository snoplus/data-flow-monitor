#!/bin/bash

set -e

virtualenv python-venv
source python-venv/bin/activate
python -m pip install requests numpy
deactivate
