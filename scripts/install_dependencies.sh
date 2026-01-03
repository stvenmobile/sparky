#!/bin/bash

echo "--- Updating System Repositories ---"
sudo apt update

echo "--- Installing Audio & System Libraries ---"
# alsa-utils: Command line audio tools (aplay, arecord)
# portaudio19-dev: Required to compile Python 'sounddevice'
# libsndfile1: Required for 'soundfile' library
# mosquitto: The MQTT Broker (The Nervous System)
# mosquitto-clients: CLI tools to test MQTT
# libgomp1: OpenMP support (often needed for faster-whisper/CTranslate2)
sudo apt install -y python3-pip python3-venv portaudio19-dev libsndfile1 mosquitto mosquitto-clients alsa-utils libgomp1

echo "--- Checking for Ollama ---"
if ! command -v ollama &> /dev/null
then
    echo "Ollama could not be found. Installing..."
    curl -fsSL https://ollama.com/install.sh | sh
    
    # Pre-pull the model so the first run isn't slow
    echo "Pulling Llama 3.2 3B model..."
    ollama pull llama3.2:3b
else
    echo "Ollama is already installed."
fi

echo "--- Enabling Services ---"
sudo systemctl enable mosquitto
sudo systemctl start mosquitto

echo "--- Dependencies Installed Successfully ---"
