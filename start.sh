#!/bin/bash

python3 ss.py &
PID1=$!

python3 ap.py &
PID2=$!

python3 pp.py &
PID3=$!

wait $PID1 $PID2 $PID3
