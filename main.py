import time
import os
import sys
import sounddevice as sd
from enum import Enum, auto
import paho.mqtt.client as mqtt  # <--- NEW IMPORT

# Import our modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'modules'))

from modules.wakeword_service import WakeWordService
from audio_recorder import AudioRecorder
from stt_service import STTService
from tts_service import TTSService
import ollama 

# --- Configuration ---
DEBUG_MODE = True
OLLAMA_MODEL = "llama3.2" 
ACTIVE_MODELS = ["hey_jarvis_v0.1"]
VOICE_MODEL = "modules/voices/ryan.onnx"
CONVERSATION_TIMEOUT = 120  # 2 Minutes

# MQTT Configuration
MQTT_BROKER = "192.168.1.40"
MQTT_PORT = 1883

# --- State Definitions ---
class State(Enum):
    LISTENING = auto()  # Waiting for Wake Word
    RECORDING = auto()  # capturing command
    THINKING = auto()   # Transcribing & LLM
    SPEAKING = auto()   # TTS

# --- The Orchestrator Class ---
class SparkyBot(WakeWordService):
    def __init__(self):
        print("\n⏳ Initializing Sparky...")
        
        # 1. Initialize MQTT (The Nervous System)
        self.init_mqtt()

        # 2. Initialize Wake Word (Parent Class)
        super().__init__(models=ACTIVE_MODELS, sensitivity=0.5)
        print(f"✅ Wake Word Loaded: {ACTIVE_MODELS}")
        
        # 3. Initialize Hardware Services
        self.recorder = AudioRecorder()
        self.stt = STTService()
        
        if os.path.exists(VOICE_MODEL):
            self.tts = TTSService(VOICE_MODEL, device_index=0, debug=DEBUG_MODE)
        else:
            print(f"⚠️ Voice model not found at {VOICE_MODEL}. TTS disabled.")
            self.tts = None
        
        self.warmup_brain()
        
        # Initial State
        self.state = State.LISTENING
        self.current_response = ""
        
        # Conversation Logic
        self.in_conversation = False
        self.last_interaction_time = 0

    def init_mqtt(self):
        """Connects to the robot face"""
        try:
            self.mqtt_client = mqtt.Client()
            self.mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
            self.mqtt_client.loop_start() # Run in background
            print(f"✅ Connected to Robot Face at {MQTT_BROKER}")
            
            # Reset Face to Sleep on Boot
            self.send_face("emotion", "sleep")
        except Exception as e:
            print(f"❌ MQTT Connection Failed: {e}")
            self.mqtt_client = None

    def send_face(self, topic_suffix, message):
        """Helper to send MQTT commands safely"""
        if self.mqtt_client:
            self.mqtt_client.publish(f"robot/{topic_suffix}", message)

    def warmup_brain(self):
        print("🧠 Warming up neural pathways...")
        try:
            ollama.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': 'hi'}])
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
        
        while True:
            # --- STATE 1: LISTENING (Deep Sleep) ---
            if self.state == State.LISTENING:
                print(f"\n[{self.state.name}] Waiting for wake word...")
                
                # Blocks here until "Hey Jarvis" is heard
                if self.listen():
                    print("✨ WAKE WORD DETECTED")
                    
                    # --- WAKE UP THE ROBOT ---
                    self.send_face("emotion", "wake")  # Open Eyes
                    self.send_face("emotion", "happy") # Smile
                    # -------------------------

                    self.in_conversation = True
                    self.last_interaction_time = time.time()
                    self.state = State.RECORDING

            # --- STATE 2: RECORDING ---
            elif self.state == State.RECORDING:
                print(f"\n[{self.state.name}] Listening...")
                
                sd.stop()
                time.sleep(0.2)
                
                # Record 5 seconds of audio
                audio_file = self.recorder.record(duration=5)
                self.audio_file_path = audio_file
                self.state = State.THINKING

            # --- STATE 3: THINKING ---
            elif self.state == State.THINKING:
                print(f"\n[{self.state.name}] Transcribing...")
                
                # Optional: Look "Puzzled" while thinking
                # self.send_face("emotion", "puzzled")
                
                user_text = self.stt.transcribe(self.audio_file_path)
                
                # --- SILENCE HANDLING ---
                if not user_text:
                    time_since_active = time.time() - self.last_interaction_time
                    
                    if self.in_conversation and time_since_active < CONVERSATION_TIMEOUT:
                        print(f"... Silence ({int(time_since_active)}s / {CONVERSATION_TIMEOUT}s)")
                        self.state = State.RECORDING
                        continue
                    else:
                        print("⌛ Conversation Timeout.")
                        if self.in_conversation and self.tts:
                            self.send_face("state", "speaking")
                            self.tts.speak("Catch you later.")
                            self.send_face("state", "silent")
                        
                        # --- GO TO SLEEP ---
                        self.send_face("emotion", "sleep")
                        # -------------------

                        self.in_conversation = False
                        self.state = State.LISTENING
                        continue

                # --- VALID INPUT ---
                print(f"🗣️ User said: '{user_text}'")
                self.last_interaction_time = time.time()

                if self.is_stop_command(user_text):
                    print("Stop command received.")
                    if self.tts: 
                        self.send_face("state", "speaking")
                        self.tts.speak("Bye. Catch you later.")
                        self.send_face("state", "silent")
                        time.sleep(1) # Let animation finish
                    
                    self.send_face("emotion", "sleep")
                    print("👋 Exiting program.")
                    break 

                print(f"[{self.state.name}] Querying Ollama...")
                try:
                    response = ollama.chat(model=OLLAMA_MODEL, messages=[
                        {'role': 'system', 'content': "You are Sparky. Concise answers only."},
                        {'role': 'user', 'content': user_text},
                    ])
                    self.current_response = response['message']['content']
                    self.state = State.SPEAKING
                except Exception as e:
                    print(f"❌ Ollama Error: {e}")
                    self.current_response = "My brain is lagging."
                    self.state = State.SPEAKING

            # --- STATE 4: SPEAKING ---
            elif self.state == State.SPEAKING:
                print(f"\n[{self.state.name}] Sparky says:")
                print(f"💬 \"{self.current_response}\"")
                
                if self.tts:
                    # 1. Start Animation
                    self.send_face("state", "speaking") 
                    
                    # 2. Play Audio (Blocks until done)
                    self.tts.speak(self.current_response)
                    
                    # 3. Stop Animation
                    self.send_face("state", "silent")
                
                # Reset to Neutral mood after talking?
                self.send_face("emotion", "neutral")

                self.last_interaction_time = time.time()
                self.state = State.RECORDING

if __name__ == "__main__":
    try:
        bot = SparkyBot()
        bot.run()
    except KeyboardInterrupt:
        print("\n👋 Sparky shutting down.")