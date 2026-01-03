#!/bin/bash

# 1. Create the virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "--- Creating Virtual Environment ---"
    python3 -m venv venv
else
    echo "--- Virtual Environment already exists ---"
fi

# 2. Activate it (temporarily for this script) to install packages
source venv/bin/activate

# 3. Install requirements
echo "--- Installing Python Dependencies ---"
pip install -r requirements.txt

echo "-------------------------------------------------------------"
echo " Setup Complete!                                             "
echo " Run this command manually to start the virtual environment: "
echo "   source venv/bin/activate                                  "
echo "-------------------------------------------------------------"
