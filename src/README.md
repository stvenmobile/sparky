# Sparky V2: The Edge AI Assistant

Sparky V2 is a local-first, low-latency voice assistant running on the **NVIDIA Jetson Orin NX**. 
Unlike V1 (which relied on an ESP32 for the face), V2 uses a direct HDMI connection to a 7-inch display for high-speed, zero-latency facial animation synchronized with speech.

## 🏗 Architecture

* **Brain:** Llama 3.2 (via Ollama) or Gemini Flash / GPT-4o (Cloud Fallback).
* **Ears:** USB Microphone + Silero VAD + Faster-Whisper.
* **Voice:** Piper TTS (running locally on Jetson) with Viseme extraction.
* **Face:** PyGame-based procedural renderer (running on `:0` display).
* **Control:** MQTT for inter-process communication (Face <-> Brain).

## 🚀 Installation

### 1. System Prerequisites (Jetson / Ubuntu)
Install the system-level audio and graphics dependencies:
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv libportaudio2 mosquitto
2. Python SetupClone the repo and set up the virtual environment:Bashgit clone [https://github.com/stvenmobile/sparky.git](https://github.com/stvenmobile/sparky.git)
cd sparky
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
3. Audio & Model SetupOllama: Ensure Ollama is running (systemctl start ollama).Piper TTS: The system expects the Piper binary and voice model in src/modules/piper_engine/.⚙️ ConfigurationCreate a file at config/settings.json. The system defaults to these values if the file is missing:JSON{
  "system_prompt": "You are Sparky, a witty robot assistant.",
  "ollama_model": "llama3.2",
  "cloud_provider": "gemini",
  "wake_word_models": ["hey_jarvis_v0.1"],
  "mqtt_broker": "localhost",
  "vad_threshold": 500,
  "timeout": 120
}
🖥️ UsageRunning the SystemYou typically run the Face and the Brain in separate terminals (or via systemd services).Terminal 1: The Face (HDMI Output)Bashexport DISPLAY=:0 
python src/face_renderer.py
Terminal 2: The Brain (Core Logic)Bashpython src/sparky_core.py
Flags:--cloud: Force use of Cloud LLM (Gemini/OpenAI) instead of local Ollama.🔌 Special ModesSparky listens for specific voice commands to trigger sub-routines:ModeTrigger PhraseDescriptionDictation"Start dictation", "Please record now"Records long-form speech to dictation/ folder. Ignores wake words until you say "Stop recording".Sentry"Receptionist mode", "Lunch mode"Acts as an answering machine. If someone asks for "Steve", it takes a message.Kill Switch"System shutdown", "Terminate program"Safely shuts down the Python process.📂 Directory StructurePlaintextsparky/
├── config/             # JSON settings
├── dictation/          # Saved transcripts and messages
├── logs/               # Daily operation logs
├── src/
│   ├── modules/        # Drivers (STT, TTS, WakeWord)
│   ├── face_renderer.py # PyGame UI
│   └── sparky_core.py  # Main Orchestrator
├── tests/              # Hardware test scripts
└── requirements.txt

### 3. Next Step: Organization
Currently, your uploaded file (which contains the `SparkyBot` class) is likely sitting in the root or named `README.md` by mistake.

**Action:**
1.  Save the Python code you provided as `src/sparky_core.py`.
2.  Save the text above as `README.md`.
3.  Save the dependency list as `requirements.txt`.

