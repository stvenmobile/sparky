import time
import os
import sys
import json
import argparse
import sounddevice as sd
from enum import Enum, auto
import paho.mqtt.client as mqtt
from datetime import datetime

# Cloud AI Libraries
import google.generativeai as genai
from openai import OpenAI

# Import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.wakeword_service import WakeWordService
from audio_recorder import AudioRecorder
from stt_service import STTService
from tts_service import TTSService
import ollama 

# --- Configuration Constants ---
DEBUG_MODE = True
CONFIG_FILE = "config/settings.json"

# --- State Definitions ---
class State(Enum):
    LISTENING = auto()  # Waiting for Wake Word
    RECORDING = auto()  # capturing command
    THINKING = auto()   # Transcribing & LLM
    SPEAKING = auto()   # TTS

# --- The Orchestrator Class ---
class SparkyBot(WakeWordService):
    def __init__(self, use_cloud=False):
        print("\n⏳ Initializing Sparky...")
        
        self.use_cloud = use_cloud
        
        # 1. LOAD SETTINGS
        self.config = self.load_settings()
        
        # 2. Initialize MQTT (The Nervous System)
        self.init_mqtt()

        # 3. Initialize Wake Word (Parent Class)
        super().__init__(models=self.config["wake_word_models"], sensitivity=0.5)
        print(f"✅ Wake Word Loaded: {self.config['wake_word_models']}")
        
        # 4. Initialize Hardware Services
        self.recorder = AudioRecorder()
        self.stt = STTService()
        
        # TTS Setup (Using System Default Audio)
        voice_path = self.config.get("voice_model", "modules/voices/ryan.onnx")
        if os.path.exists(voice_path):
            self.tts = TTSService(voice_path, device_index=None, debug=DEBUG_MODE)
        else:
            print(f"⚠️ Voice model not found at {voice_path}. TTS disabled.")
            self.tts = None
            
        # 5. Initialize Brain (Local or Cloud)
        self.init_brain()
        
        # 6. Initialize Memory & Prompt
        self.chat_history = [] 
        self.system_prompt = self.config.get("system_prompt", "You are Sparky.")

        # Initial State
        self.state = State.LISTENING
        self.current_response = ""
        self.in_conversation = False
        self.last_interaction_time = 0

    def load_settings(self):
        """Loads settings from JSON or returns defaults"""
        defaults = {
            "system_prompt": "You are Sparky, a witty robot assistant.",
            "ollama_model": "llama3.2",
            "cloud_provider": "gemini",
            "wake_word_models": ["hey_jarvis_v0.1"], 
            "voice_model": "modules/voices/ryan.onnx",
            "timeout": 120,
            "mqtt_broker": "192.168.1.40",
            "mqtt_port": 1883,
            "vad_threshold": 500
        }
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, "r") as f:
                    user_config = json.load(f)
                    if "system_prompt" in user_config and isinstance(user_config["system_prompt"], list):
                        user_config["system_prompt"] = "\n".join(user_config["system_prompt"])
                    defaults.update(user_config)
                    print(f"✅ Settings loaded from {CONFIG_FILE}")
            else:
                print("⚠️ Config file not found, using defaults.")
        except Exception as e:
            print(f"⚠️ Error loading settings: {e}")
        return defaults

    def init_mqtt(self):
        """Connects to the robot face"""
        broker = self.config.get("mqtt_broker", "192.168.1.40")
        port = self.config.get("mqtt_port", 1883)
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.connect(broker, port, 60)
            self.mqtt_client.loop_start() 
            print(f"✅ Connected to Robot Face at {broker}")
            self.send_face("emotion", "sleep")
        except Exception as e:
            print(f"❌ MQTT Connection Failed: {e}")
            self.mqtt_client = None

    def send_face(self, topic_suffix, message):
        """Sends MQTT message."""
        if self.mqtt_client:
            self.mqtt_client.publish(f"robot/{topic_suffix}", message)

    def init_brain(self):
        """Sets up the LLM (Gemini, OpenAI, or Ollama)"""
        self.provider = self.config.get("cloud_provider", "gemini")
        
        if self.use_cloud:
            if self.provider == "gemini":
                key = self.config.get("google_api_key")
                if key:
                    genai.configure(api_key=key)
                    
                    # --- CHANGED: Load model name from config ---
                    model_name = self.config.get("cloud_model", "gemini-2.5-flash")
                    self.cloud_model = genai.GenerativeModel(model_name)
                    print(f"⚡ Cloud Brain Enabled: {model_name}")
                    # --------------------------------------------
                else:
                    print("❌ No Google API Key found. Falling back to Local.")
                    self.use_cloud = False
            elif self.provider == "openai":
                key = self.config.get("openai_api_key")
                if key:
                    self.cloud_client = OpenAI(api_key=key)
                    print("☁️ Cloud Brain Enabled: OpenAI GPT")
                else:
                    print("❌ No OpenAI API Key found. Falling back to Local.")
                    self.use_cloud = False
        
        # Fallback or User Choice: Local Brain
        if not self.use_cloud:
            model = self.config["ollama_model"]
            print(f"🏠 Local Brain Enabled: {model}")
            print(f"🧠 Warming up {model}...")
            try:
                ollama.chat(model=model, messages=[{'role': 'user', 'content': 'hi'}])
                print("✅ Brain is ready.")
            except Exception as e:
                print(f"⚠️ Warmup failed: {e}")

    def is_stop_command(self, text):
        if not text: return False
        clean_text = text.lower().strip()
        stop_phrases = ["stop", "exit", "quit", "shut down", "go to sleep"]
        return any(phrase in clean_text for phrase in stop_phrases)

    def run(self):
        print("\n🤖 Sparky is Online.")
        print("-----------------------------------")
        
        sd.stop()
        time.sleep(1) 
        timeout_sec = self.config.get("timeout", 120)
        
        while True:
            # --- STATE 1: LISTENING ---
            if self.state == State.LISTENING:
                clean_names = [os.path.basename(m).replace('.tflite', '') for m in self.models]
                print(f"\n[{self.state.name}] Waiting for {clean_names} ...")
                
                if self.listen():
                    print("✨ WAKE WORD DETECTED")
                    self.send_face("emotion", "wake")
                    self.send_face("emotion", "happy")
                    
                    self.in_conversation = True
                    self.last_interaction_time = time.time()
                    self.state = State.RECORDING
                else:
                    print("👋 Exiting...")
                    self.send_face("emotion", "sleep")
                    break

            # --- STATE 2: RECORDING ---
            elif self.state == State.RECORDING:
                print(f"\n[{self.state.name}] Listening...")
                sd.stop()
                time.sleep(0.2)
                
                # Use VAD threshold from config
                thresh = self.config.get("vad_threshold", 500)
                self.audio_file_path = self.recorder.record(threshold=thresh)
                
                self.state = State.THINKING

            # --- STATE 3: THINKING ---
            elif self.state == State.THINKING:
                print(f"\n[{self.state.name}] Transcribing...")
                
                user_text = self.stt.transcribe(self.audio_file_path)
                
                # --- HALLUCINATION FILTER ---
                has_content = any(char.isalnum() for char in user_text) if user_text else False
                if not has_content:
                    user_text = None 

                # --- SILENCE HANDLING ---
                if not user_text:
                    time_since_active = time.time() - self.last_interaction_time
                    if self.in_conversation and time_since_active < timeout_sec:
                        print(f"... Silence ({int(time_since_active)}s / {timeout_sec}s)")
                        self.state = State.RECORDING
                        continue
                    else:
                        print("⌛ Conversation Timeout.")
                        if self.in_conversation and self.tts:
                            self.send_face("state", "speaking")
                            self.tts.speak("Catch you later.")
                            self.send_face("state", "silent")
                        
                        self.send_face("emotion", "sleep")
                        self.in_conversation = False
                        self.state = State.LISTENING
                        self.chat_history = [] 
                        continue

                # --- VALID INPUT ---
                print(f"🗣️ User said: '{user_text}'")
                self.last_interaction_time = time.time()

                if self.is_stop_command(user_text):
                    print("Stop command received.")
                    if self.tts: 
                        self.send_face("state", "speaking")
                        self.tts.speak("Bye.")
                        self.send_face("state", "silent")
                        time.sleep(1)
                    
                    self.send_face("emotion", "sleep")
                    print("👋 Exiting program.")
                    break 

                print(f"[{self.state.name}] Querying {self.provider if self.use_cloud else 'Local'} Brain...")
                
                now_str = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                dynamic_sys = f"{self.system_prompt} Current Date/Time: {now_str}."

                # Logic for Brain Selection
                try:
                    bot_reply = ""
                    
                    if self.use_cloud and self.provider == "gemini":
                        # GEMINI (Google)
                        # Construct a single prompt block (simplest for Gemini 1.5)
                        full_prompt = f"System: {dynamic_sys}\n\n"
                        for msg in self.chat_history:
                            full_prompt += f"{msg['role']}: {msg['content']}\n"
                        full_prompt += f"user: {user_text}"
                        
                        response = self.cloud_model.generate_content(full_prompt)
                        bot_reply = response.text

                    elif self.use_cloud and self.provider == "openai":
                        # OPENAI (GPT)
                        self.chat_history.append({'role': 'user', 'content': user_text})
                        full_context = [{'role': 'system', 'content': dynamic_sys}] + self.chat_history
                        
                        response = self.cloud_client.chat.completions.create(
                            model=self.config.get("cloud_model", "gpt-4o-mini"),
                            messages=full_context
                        )
                        bot_reply = response.choices[0].message.content
                        
                    else:
                        # LOCAL (Ollama)
                        self.chat_history.append({'role': 'user', 'content': user_text})
                        full_context = [{'role': 'system', 'content': dynamic_sys}] + self.chat_history
                        
                        response = ollama.chat(model=self.config["ollama_model"], messages=full_context)
                        bot_reply = response['message']['content']

                    # Save context & Speak
                    # (Note: For Gemini, we manually track history in the list, even if we send a block)
                    if not (self.use_cloud and self.provider == "openai") and not (not self.use_cloud):
                         self.chat_history.append({'role': 'user', 'content': user_text})

                    self.chat_history.append({'role': 'assistant', 'content': bot_reply})
                    
                    # Trim Memory
                    if len(self.chat_history) > 10:
                        self.chat_history = self.chat_history[-10:]

                    self.current_response = bot_reply
                    self.state = State.SPEAKING

                except Exception as e:
                    print(f"❌ Brain Error: {e}")
                    self.current_response = "I'm having trouble thinking right now."
                    self.state = State.SPEAKING

            # --- STATE 4: SPEAKING ---
            elif self.state == State.SPEAKING:
                print(f"\n[{self.state.name}] Sparky says:")
                print(f"💬 \"{self.current_response}\"")
                
                if self.tts:
                    clean_response = self.current_response.replace('*', '')
                    self.send_face("state", "speaking") 
                    self.tts.speak(clean_response)
                    self.send_face("state", "silent")
                
                self.send_face("emotion", "neutral")
                self.last_interaction_time = time.time()
                self.state = State.RECORDING

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sparky Robot Controller")
    parser.add_argument("--cloud", action="store_true", help="Use Cloud LLM (Gemini/OpenAI) instead of Local Ollama")
    args = parser.parse_args()

    try:
        bot = SparkyBot(use_cloud=args.cloud)
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Sparky shutting down.")