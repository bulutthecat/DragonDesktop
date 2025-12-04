#!/bin/bash

# Start Xephyr
#Xephyr -br -ac -noreset -screen 800x600 -mouse ephyr,,,5 :7 &
#xephyr_pid=$!
#sleep 1

#export DISPLAY=:7

# SET BACKGROUND TO GREY so we can see black windows
xsetroot -solid gray

# Run WM
python3 main.py &
wm_pid=$!

# Run xterm
#sleep 1
#xterm &
#xterm &
#xclock &
#xcalc &
#xeyes &

wait $wm_pid
#kill $xephyr_pid
