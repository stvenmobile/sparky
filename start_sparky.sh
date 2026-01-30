#!/bin/bash

# 1. Export Display variables
export DISPLAY=:0
export XAUTHORITY=/home/steve/.Xauthority

# 2. Move to the directory
cd /home/steve/sparky

# 3. Kill old instances
pkill -f face_renderer.py
pkill -f sparky_core.py

# 4. Start Face (Using VENV Python)
# We point directly to the python binary inside the venv folder
/home/steve/sparky/venv/bin/python3 src/face_renderer.py &
FACE_PID=$!
echo "Started Face Renderer (PID: $FACE_PID)"

# Wait for face to initialize
sleep 5

# 5. Start Brain (Using VENV Python)
/home/steve/sparky/venv/bin/python3 src/sparky_core.py