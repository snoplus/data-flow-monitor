#!/bin/bash

virtualenv --no-site-packages python-virtualenv && source python-virtualenv/bin/activate && python-virtualenv/bin/pip install -r requirements.txt
