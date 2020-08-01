#!/bin/bash
sudo pigpiod -d 5 -e 6
python3 /home/pi/jajucha-server/control.py

