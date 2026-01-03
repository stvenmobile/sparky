# Sparky: Local Voice Assistant on Jetson Orin NX

Sparky is a modular, privacy-first voice assistant designed for the NVIDIA Jetson Orin NX. It leverages local LLMs (Ollama), faster-whisper for speech recognition, and MQTT for a decoupled, event-driven architecture.

## Hardware Stack
* **Compute:** NVIDIA Jetson Orin NX (16GB)
* **Carrier Board:** Seeed Studio reComputer J4012
* **Audio:** Kaysuda SP200 Speakerphone (Connected via USB for low latency)
* **Operating System:** Ubuntu 22.04 (JetPack 6.x via Seeed System Image)

## Software Architecture
* **Brain:** Ollama (Llama 3.2 3B Instruct)
* **Ears:** faster-whisper (CUDA accelerated)
* **Mouth:** Piper TTS (Planned)
* **Nervous System:** MQTT (Mosquitto)
* **Language:** Python 3.10+

## Project Structure
```text
sparky/
├── config/                 # Configuration files (YAML)
├── modules/                # Python Logic Modules
│   ├── audio_io.py         # Microphone/Speaker handling
│   ├── stt_service.py      # Speech-to-Text
│   ├── llm_service.py      # Ollama Interface
│   └── tts_service.py      # Text-to-Speech
├── scripts/                # Setup & Maintenance Scripts
│   ├── install_dependencies.sh
│   └── setup_services.sh
├── main.py                 # Orchestrator
├── requirements.txt        # Python Packages
└── setup_env.sh            # One-click Virtual Env creator
Installation

### 1. Clone the Repository
Bash

git clone git@github.com:yourusername/sparky.git
cd sparky
### 2. Install System Dependencies
This script installs system-level libraries (PortAudio, Mosquitto), installs Ollama, and pulls the default LLM model.

Bash

sudo ./scripts/install_dependencies.sh
### 3. Set up Python Environment
This script creates the venv and installs all Python requirements.

Bash

./setup_env.sh
Usage
Always activate the virtual environment first:

Bash

source venv/bin/activate
Run the Audio Test (Mic Check):

Bash

python3 modules/audio_io.py
(Records 5 seconds of audio and plays it back to verify hardware)


