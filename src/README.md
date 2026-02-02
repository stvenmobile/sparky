# Sparky V9: The Edge AI Assistant

Sparky is a local-first, low-latency voice and vision assistant running on the **NVIDIA Jetson Orin NX**. 

Unlike typical cloud assistants, Sparky processes **Vision (YOLO)**, **Speech (Whisper)**, and **Intelligence (Llama 3)** entirely on-device, offering real-time privacy and zero-latency facial animation.

## 🏗 Architecture (V9.4)

The system is composed of three decoupled processes communicating via **UDP Sockets** for maximum speed:

1.  **The Core (`sparky_core.py`):**
    * **Brain:** Llama 3.2 (via Ollama) with Cloud Fallback.
    * **Ears:** `faster-whisper` with Silero VAD.
    * **Voice:** Piper TTS (Local Neural TTS).
    * **Logic:** Handles "Barge-in" interruption, thermal monitoring, and intent parsing.

2.  **The Face (`face_renderer.py`):**
    * **Engine:** PyGame running on the HDMI display (1024x600).
    * **Modes:** Animated Face (Lip-syncs to TTS) OR Live Camera Feed (Vision Mode).
    * **Input:** Listens on Port `5005` (Commands/Visemes) and `5006` (MJPEG Video Stream).

3.  **The Eyes (`sparky_vision.py`):**
    * **Engine:** YOLOv8s (Small) running on GPU/TensorRT.
    * **Function:** Performs real-time object detection and streams optimized video to the Face renderer.

## ✨ Key Features

* **👁️ Computer Vision:**
    * "Vision On/Off": Toggles between the animated face and a live HUD.
    * "What do you see?": Analyzes the scene using YOLOv8 (Prioritizes humans, filters clutter).
    * Smart Letterboxing: Scales 16:9 camera feeds to fit 1024x600 screens without distortion.
* **🗣️ Natural Conversation:**
    * **Barge-In Support:** You can interrupt Sparky while he is speaking (volume-based detection).
    * **Memory:** Context-aware conversations with auto-summarization.
* **🛡️ Self-Protection:**
    * **Thermal Monitor:** Continuously checks CPU temps. Warns at 80°C, Emergency Shutdown at 90°C.
    * **Safe Exit:** Handles `SIGINT` (Ctrl+C) gracefully to prevent C++ memory dumps.

## 🚀 Installation & Setup

### 1. Prerequisites (Jetson / Ubuntu)
```bash
sudo apt-get update
sudo apt-get install python3-pip python3-venv libportaudio2
```

### 2. Python Environment
```bash
git clone [https://github.com/stvenmobile/sparky.git](https://github.com/stvenmobile/sparky.git)
cd sparky
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
# Note: Ensure you have pytorch and onnxruntime-gpu installed for Jetson
```

### 3. Configuration
Settings are managed in config.json. Key fields:

```json
{
    "voice": {
        "model_path": "src/piper_engine/en_US-lessac-medium.onnx",
        "binary_path": "src/piper_engine/piper/piper"
    },
    "whisper": {
        "size": "small",
        "device": "cuda"
    },
    "ollama": {
        "host": "http://127.0.0.1:11434",
        "model": "llama3.2",
        "timeout": 120, 
        "keep_alive": -1
    },
    "cloud_api": {
        "provider": "gemini", 
        "api_key": "<Google API Key>",
        "model": "gemini-3-flash-preview",
        "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    },
    "system_settings": {
        "context_window_size": 14,
        "auto_summary_interval": 10
    },
    "thermal": {
        "enabled": true,
        "warning_temp": 80,
        "shutdown_temp": 90,
        "check_interval": 5
    },
    "interaction": {
        "silence_duration": 1.2,
        "mic_threshold": 0.08,
        "max_listen_duration": 60
    },
    "commands": {
        "vision_on": ["vision mode", "camera mode", "show me what you see", "visuals on", "activate camera"],
        "vision_off": ["exit vision", "normal mode", "face mode", "hide camera", "stop camera"],
        "vision_query": ["what do you see", "describe the room", "who is there", "look around"],
        "exit": ["exit program", "shutdown system", "terminate program"],
        "sleep": ["go to sleep", "sleep now", "hibernate", "standby"],
        "calendar": ["calendar", "schedule", "appointment", "set event"],
        "cloud_query": ["search the web", "google this", "check online", "ask the cloud", "go online", "look up"],
        "wake": ["wake up", "sparky", "systems online"],
        "mute": ["stop listening", "mute microphone", "quiet mode"],
        "text_mode": ["switch to text", "text mode", "keyboard mode", "enable typing"],
        "voice_mode": ["switch to voice", "voice mode", "mic mode", "enable microphone"]
    },   
    "fault_prompt": "You are Sparky, a helpful robot assistant. Be brief. If you do not know the answer to a question, strictly say 'I don't know' or 'I would need to check online for that.' Do not guess facts or numbers.",
    "system_specs": "Running on NVIDIA Jetson Orin NX (16GB RAM).",
    "users": {
        "steve": {
            "birthday": "10/18/1951",
            "prompt": "You are Sparky. Steve is a systems engineer. He likes robotics, AI, art, design and 3d printing. Be technical. If you lack data, admit it immediately.",
            "memory_file": "steve_memory.json"
        },
    }
}


```

### 4. Usage
Standard Start (Voice Mode): Use the helper script to launch the Renderer and Core simultaneously.
```bash
./start_sparky.sh
```

Manual Start: Terminal 1 (Face):
```bash
export DISPLAY=:0
python src/face_renderer.py
```

Manual Start: Terminal 2 (Core):
```bash
python src/sparky_core.py
```

### 5. Voice Commands
| Category | Command Examples | Action |
| :--- | :--- | :--- |
| **Vision** | "Vision On", "Enable Vision" | Switches screen to Camera HUD. |
| | "Vision Off", "Disable Vision" | Switches screen back to Face. |
| | "What do you see?", "Describe view" | Lists detected objects (e.g., "I see you and a cup"). |
| **System** | "Wake Up", "Sparky" | Wakes from sleep mode. |
| | "Go to sleep" | Disables mic, enters low power animation. |
| | "Exit program", "Shutdown" | Safely terminates all processes. |
| **Utility** | "Schedule [event] for [date]" | Adds to calendar memory. |

### 6. Directory Structure
sparky/
├── config.json         # Main settings
├── thermal_log.txt     # Safety logs
├── start_sparky.sh     # Launch script
├── src/
│   ├── sparky_core.py     # Main logic & Audio
│   ├── face_renderer.py   # UI & Video Receiver
│   ├── sparky_vision.py   # YOLO Object Detection
│   └── piper_engine/      # TTS Binary & Models
└── requirements.txt
