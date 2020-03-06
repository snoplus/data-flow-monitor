#!/bin/bash

virtualenv --no-site-packages python-venv && source python-venv/bin/activate && python -m pip install requests numpy && deactivate
