#!/bin/bash
sudo pigpiod -d 5 -e 6
python3 control.py

