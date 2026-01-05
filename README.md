# Sparky: Local Voice Assistant on Jetson Orin NX

Sparky is a modular, privacy-first voice assistant designed for the NVIDIA Jetson Orin NX. It features a **"Split-Brain" architecture**: the **Jetson** handles high-level cognition (LLMs, STT, TTS), while a separate **ESP32** microcontroller handles real-time reflexes, facial animations, and physical hardware interaction.

## 🧠 System Architecture

Sparky uses a decoupled, event-driven architecture connected by a central "Nervous System" (MQTT).

* **The Brain (Jetson Orin NX):** Runs the heavy AI workloads. It listens, thinks, and decides *what* to say.
* **The Body (ESP32-S3 / CYD):** Handles the "face" (display), motor control, and immediate physical feedback. It acts as a puppet controlled by the Brain.
* **The Bridge (MQTT):** The Brain publishes state changes (e.g., "I am thinking") to the Body, ensuring the physical robot reacts instantly to the AI's internal state.

## 🛠 Hardware Stack

### Cognition Layer (The Brain)
* **Compute:** NVIDIA Jetson Orin NX (16GB)
* **Carrier Board:** Seeed Studio reComputer J4012
* **Audio:** Kaysuda SP200 Speakerphone (USB)
* **OS:** Ubuntu 22.04 (JetPack 6.x)

### Physical Layer (The Body - "myFriend")
* **Controller:** ESP32-S3 (Cheap Yellow Display - CYD)
* **Display:** 2.8" or 3.5" Touchscreen (Face/Eyes)
* **Actuators:** Servos for head/arm movement
* **Input:** Arduino Nano 33 BLE "Magic Wand" (communicates via BLE to ESP32)

## 📡 MQTT Communication Protocol

The Jetson acts as the publisher, broadcasting its internal state to the local network. The ESP32 subscribes to these topics to animate the face.

**Broker:** Mosquitto (Running on Jetson/Sentinel @ `localhost` or `192.168.1.40`)

| Topic | Payload | Description | ESP32 Reaction (Example) |
| :--- | :--- | :--- | :--- |
| `robot/state` | `listening` | Mic is active, waiting for wake word. | Ears perk up, eyes widen, look attentive. |
| `robot/state` | `recording` | Wake word detected, recording command. | Show "Recording" icon or listening animation. |
| `robot/state` | `thinking` | Audio processing / LLM inference. | Eyes look up/right, rapid blinking, "processing" spinner. |
| `robot/state` | `speaking` | TTS is currently playing audio. | **Start lip-sync loop** (move mouth/jaw). |
| `robot/state` | `idle` | System is asleep or standby. | Slow blink rate, wandering eyes, "breathing" LED. |
| `robot/emotion`| `happy` | Positive sentiment detected. | Eyes shape turns to arches (`^^`). |
| `robot/emotion`| `neutral` | Default sentiment. | Round/Normal eyes. |

## 📂 Project Structure

```text
sparky/
├── config/                 # Configuration files (YAML)
├── modules/                # Python Logic Modules
│   ├── audio_recorder.py   # Raw audio capture (PyAudio/SoundDevice)
│   ├── robot_face.py       # MQTT Interface for ESP32 control
│   ├── stt_service.py      # Speech-to-Text (Faster-Whisper)
│   ├── tts_service.py      # Text-to-Speech (Piper)
│   ├── wakeword_service.py # Wake Word Detection (OpenWakeWord)
│   └── voices/             # ONNX Voice models for Piper
├── scripts/                # Setup & Maintenance Scripts
│   ├── install_dependencies.sh
│   └── setup_services.sh
├── main.py                 # Orchestrator (State Machine)
├── requirements.txt        # Python Packages
└── setup_env.sh            # One-click Virtual Env creator
```
## 🧩 Key Modules
```text
1. Wake Word Service (wakeword_service.py)
Engine: openWakeWord.

Features:

Robust Resampling: Automatically handles the conversion from the system's 48kHz audio (required by Piper/Linux) to the model's required 16kHz.

Multi-Model Support: Can listen for "Hey Jarvis" (high reliability) and "Hey Sparky" (custom) simultaneously.

Cooldown Logic: Prevents double-triggering on the same word.

2. Robot Face (robot_face.py)
Function: Abstraction layer for MQTT.

Usage: The main orchestrator simply calls self.face.set_state("thinking"), and this module handles the connection and publishing to the broker.

3. Orchestrator (main.py)
Logic: Implements a blocking loop State Machine.

States: LISTENING -> RECORDING -> THINKING -> SPEAKING.

Conversation Mode: Includes a "Conversation Window" feature. After the first wake word, Sparky stays active for 2 minutes (listening for follow-up commands without requiring the wake word) before saying "Catch you later" and returning to deep sleep.
```

##🚀 Installation
1. Clone the Repository

```bash
git clone git@github.com:yourusername/sparky.git
cd sparky
```
2. Install System Dependencies
Installs PortAudio (audio drivers), Mosquitto (MQTT Broker), and system tools.

```bash
sudo ./scripts/install_dependencies.sh
```
3. Set up Python Environment
Creates the virtual environment and installs Python requirements (Ollama, PyAudio, etc.).

```bash
./setup_env.sh
```

⚡️ Usage - Always activate the virtual environment first:

```bash
source venv/bin/activate
python3 main.py
```

Monitor MQTT Messages (Debug): Open a separate terminal to see what messages Sparky is sending to the robot body:

```bash
mosquitto_sub -h localhost -t "robot/#" -v
```
