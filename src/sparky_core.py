import time
import os
import sys
import json
import re
import socket
import subprocess
import requests
import numpy as np
import sounddevice as sd
import soundfile as sf
from datetime import datetime, timedelta
from faster_whisper import WhisperModel
import ollama
import onnxruntime as ort
ort.set_default_logger_severity(3) # (Supress ONNX warnings)

# --- VERSION CONTROL ---
SPARKY_VERSION = "6.2"

# --- LOAD CONFIGURATION ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f: return json.load(f)
    except FileNotFoundError: return {}

CONFIG = load_config()
CMD_LIST = CONFIG.get("commands", {})

# Setup Paths
PIPER_BINARY = os.path.join(BASE_DIR, CONFIG.get("voice", {}).get("binary_path", "src/piper_engine/piper/piper"))
VOICE_MODEL = os.path.join(BASE_DIR, CONFIG.get("voice", {}).get("model_path", "src/piper_engine/en_US-lessac-medium.onnx"))
DATA_DIR = os.path.join(BASE_DIR, "data/users")
os.makedirs(DATA_DIR, exist_ok=True)

# Whisper Setup
WHISPER_SIZE = CONFIG.get("whisper", {}).get("size", "small")
DEVICE = "cuda"
print("⏳ Loading Whisper Model...")
# Loading with float16 for Jetson performance
whisper = WhisperModel(WHISPER_SIZE, device=DEVICE, compute_type="float16")
print("✅ Whisper Loaded.")

# --- OLLAMA SETUP ---
OLLAMA_HOST = CONFIG.get("ollama", {}).get("host", "http://127.0.0.1:11434")
OLLAMA_MODEL = CONFIG.get("ollama", {}).get("model", "llama3.2")
print(f"🧠 Connecting to Ollama at {OLLAMA_HOST}...")
ollama_client = ollama.Client(host=OLLAMA_HOST)

# --- MEMORY MANAGER ---
def load_user_data(filename):
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                data = json.load(f)
                if "history" not in data: data["history"] = []
                if "calendar" not in data: data["calendar"] = []
                return data
        except json.JSONDecodeError: pass
    
    # Fallback / Migration
    txt_path = path.replace(".json", ".txt")
    history = []
    if os.path.exists(txt_path):
        with open(txt_path, "r") as f:
            content = f.read().strip()
            if content: history.append(f"[Migrated] {content}")
    return {"history": history, "calendar": []}

def save_user_data(data, filename):
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f: json.dump(data, f, indent=4)

def cleanup_calendar(data):
    if not data.get("calendar"): return data, 0
    today = datetime.now().date()
    valid_events = []
    cleaned_count = 0
    for item in data["calendar"]:
        try:
            event_date = datetime.strptime(item['date'], "%Y-%m-%d").date()
            if event_date >= today: valid_events.append(item)
            else: cleaned_count += 1
        except ValueError: valid_events.append(item)
    data["calendar"] = valid_events
    return data, cleaned_count

def check_upcoming_events(calendar_data):
    if not calendar_data: return ""
    upcoming = []
    today = datetime.now().date()
    for item in calendar_data:
        try:
            event_date = datetime.strptime(item['date'], "%Y-%m-%d").date()
            delta = (event_date - today).days
            if 0 <= delta <= 5:
                day_name = event_date.strftime("%A")
                if delta == 0: day_name = "Today"
                if delta == 1: day_name = "Tomorrow"
                upcoming.append(f"{day_name}: {item['event']}")
        except ValueError: continue
    if upcoming: return " You have upcoming events: " + ". ".join(upcoming) + "."
    return ""

def process_calendar_request(user_text):
    today_str = datetime.now().strftime("%Y-%m-%d (%A)")
    prompt = (
        f"Current Date: {today_str}. User Input: '{user_text}'. "
        "Extract target date (YYYY-MM-DD) and event. "
        "Return ONLY JSON: {\"date\": \"YYYY-MM-DD\", \"event\": \"description\"}. "
        "If fail, return {\"error\": \"no_date\"}."
    )
    try:
        response = ollama_client.chat(model=OLLAMA_MODEL, messages=[{'role': 'user', 'content': prompt}])
        content = response['message']['content'].replace("```json", "").replace("```", "").strip()
        return json.loads(content)
    except: return {"error": "parsing_failed"}

# --- CLOUD QUERY ENGINE ---
def query_cloud_api(messages):
    """Sends the context to a cloud provider (OpenAI/Groq/Gemini compatible)."""
    cloud_cfg = CONFIG.get("cloud_api", {})
    api_key = cloud_cfg.get("api_key", "")
    url = cloud_cfg.get("url", "https://api.openai.com/v1/chat/completions")
    model = cloud_cfg.get("model", "gpt-3.5-turbo")

    if not api_key or "YOUR" in api_key:
        return "I need a valid API key in the config file to access the cloud."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "messages": messages,
        "temperature": 0.7
    }

    try:
        print(f"☁️ Contacting Cloud ({model})...")
        response = requests.post(url, headers=headers, json=data, timeout=10)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return f"Cloud Error: {response.status_code} - {response.text}"
    except Exception as e:
        return f"Connection Failed: {e}"

def perform_summarization(history_list):
    if not history_list: return None
    prompt = "Summarize the following conversation chunk into 1-2 factual sentences. Focus on topics and decisions."
    msgs = [{'role': 'system', 'content': prompt}] + history_list
    try:
        response = ollama_client.chat(model=OLLAMA_MODEL, messages=msgs)
        return response['message']['content'].strip()
    except: return None

# --- FACE & AUDIO ---
UDP_IP = "127.0.0.1"; UDP_PORT = 5005
def send_face_cmd(mouth_val=None, emotion=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = {}
    if mouth_val is not None: data["mouth"] = mouth_val
    if emotion is not None: data["emotion"] = emotion
    try: sock.sendto(json.dumps(data).encode(), (UDP_IP, UDP_PORT))
    except: pass

def clean_and_extract_emotion(text):
    actions = re.findall(r'\*(.*?)\*', text)
    for action in actions:
        if "smile" in action or "happy" in action.lower(): send_face_cmd(emotion="happy")
        elif "think" in action.lower(): send_face_cmd(emotion="thinking")
        elif "sleep" in action.lower(): send_face_cmd(emotion="sleep")
    return re.sub(r'\*.*?\*', '', text).strip()

def play_audio_with_sync(filename):
    data, fs = sf.read(filename, dtype='float32')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    blocksize = 2048; current_idx = 0
    def callback(outdata, frames, time, status):
        nonlocal current_idx
        chunk = data[current_idx:current_idx + frames]
        if len(chunk) < frames:
            outdata[:len(chunk)] = chunk.reshape(-1, 1) if chunk.ndim == 1 else chunk
            outdata[len(chunk):] = 0
            raise sd.CallbackStop
        else: outdata[:] = chunk.reshape(-1, 1) if chunk.ndim == 1 else chunk
        viseme = min(np.sqrt(np.mean(chunk**2)) * 10, 1.0)
        try: sock.sendto(json.dumps({"mouth": viseme}).encode(), (UDP_IP, UDP_PORT))
        except: pass
        current_idx += frames
    with sd.OutputStream(samplerate=fs, channels=1, callback=callback, blocksize=blocksize):
        sd.sleep(int(len(data) / fs * 1000) + 100)
    send_face_cmd(mouth_val=0.0)

def speak(text):
    final_text = clean_and_extract_emotion(text)
    if not final_text: return
    print(f"🗣️ Sparky: {final_text}")
    try:
        subprocess.run([PIPER_BINARY, "--model", VOICE_MODEL, "--output_file", "output.wav"], 
                       input=final_text.encode('utf-8'), check=True, stderr=subprocess.DEVNULL)
        play_audio_with_sync("output.wav")
    except Exception as e: print(f"❌ TTS Error: {e}")

# --- UPDATED LISTENER WITH ANTI-HALLUCINATION ---
def listen_to_mic(threshold=0.02, silence_duration=1.2, max_duration=60):
    fs = 16000; block_size = 4096
    audio_buffer = []; silent_chunks = 0; has_spoken = False
    max_silent = int(silence_duration * fs / block_size)
    max_total = int(max_duration * fs / block_size)
    
    with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as stream:
        while True:
            chunk, _ = stream.read(block_size); audio_buffer.append(chunk)
            if np.sqrt(np.mean(chunk**2)) > threshold: silent_chunks = 0; has_spoken = True
            elif has_spoken: silent_chunks += 1
            if has_spoken and silent_chunks > max_silent: break
            if len(audio_buffer) > max_total: break
            
    if not has_spoken: return None
    recording = np.concatenate(audio_buffer, axis=0).flatten()
    
    # ANTI-HALLUCINATION SETTINGS
    segments, _ = whisper.transcribe(
        recording, 
        beam_size=5, 
        language="en",          # Force English to stop Japanese clicking
        vad_filter=True,        # Ignore non-speech noise
        vad_parameters=dict(min_silence_duration_ms=500)
    )
    
    text = "".join([s.text for s in segments]).strip()
    
    # Discard known Whisper hallucinations
    hallucinations = ["Thank you.", "Subtitles by", "Amara.org", "MBC", "Copyright"]
    if any(h in text for h in hallucinations) or len(text) < 2:
        return None
        
    return text

# --- MAIN CLASS ---
class SparkyBot:
    def __init__(self):
        print(f"\n🤖 Sparky V{SPARKY_VERSION} (Mute + Cloud + Anti-Hallucination) Initialized.")
        self.chat_history = []
        self.session_summary_buffer = [] 
        self.is_asleep = False
        self.current_user_name = None
        self.current_memory_file = None
        
        self.sys_settings = CONFIG.get("system_settings", {})
        self.context_window = self.sys_settings.get("context_window_size", 10)
        self.summary_interval = self.sys_settings.get("auto_summary_interval", 10)
        self.turns_since_summary = 0
        
        self.current_base_prompt = CONFIG.get("default_prompt", "You are a robot.")
        self.long_term_memory = ""
        self.user_metadata = "" 
        self.interaction_cfg = CONFIG.get("interaction", {})

    def switch_user(self, name):
        name = name.lower()
        if name not in CONFIG["users"]: return False
        if self.current_memory_file:
            speak(f"Saving session for {self.current_user_name}.")
            self.save_current_session()
        
        self.chat_history = []
        self.session_summary_buffer = []
        self.turns_since_summary = 0
        
        user_config = CONFIG["users"][name]
        self.current_user_name = name.capitalize()
        self.current_memory_file = user_config["memory_file"]
        self.current_base_prompt = user_config["prompt"]
        
        user_data = load_user_data(self.current_memory_file)
        self.long_term_memory = "\n".join(user_data["history"][-5:])
        calendar_reminders = check_upcoming_events(user_data["calendar"])
        
        greeting_extras = calendar_reminders
        if "birthday" in user_config:
             self.user_metadata = f"User: {self.current_user_name}. B-day: {user_config['birthday']}."
        else: self.user_metadata = f"User: {self.current_user_name}."

        print(f"👤 Switched to User: {self.current_user_name}")
        greeting = f"Hello {self.current_user_name}. {greeting_extras} How can I help you today?"
        speak(greeting)
        self.chat_history.append({'role': 'assistant', 'content': greeting})
        return True

    def save_current_session(self):
        final_chunk_summary = perform_summarization(self.chat_history)
        if final_chunk_summary and "NO_DATA" not in final_chunk_summary:
            self.session_summary_buffer.append(final_chunk_summary)
        
        if not self.session_summary_buffer: 
            print("ℹ️ Trivial session. Not saving.")
            return

        print(f"💾 Saving {len(self.session_summary_buffer)} summary chunks...")
        current_data = load_user_data(self.current_memory_file)
        current_data, _ = cleanup_calendar(current_data)
        
        full_session_log = " ".join(self.session_summary_buffer)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        current_data["history"].append(f"[{timestamp}] {full_session_log}")
        
        save_user_data(current_data, self.current_memory_file)
        print("✅ File Updated.")

    def run(self):
        send_face_cmd(emotion="neutral"); speak("Systems online.")
        
        while True:
            try:
                # DYNAMIC CONFIG LOOKUP
                user_text = listen_to_mic(
                    threshold=self.interaction_cfg.get("mic_threshold", 0.02),
                    silence_duration=self.interaction_cfg.get("silence_duration", 1.2),
                    max_duration=self.interaction_cfg.get("max_listen_duration", 60)
                )
            except KeyboardInterrupt: break
            if not user_text: continue
            
            ut_lower = user_text.lower()
            
            # --- WAKE CHECK ---
            if self.is_asleep:
                if any(c in ut_lower for c in CMD_LIST.get("wake", ["wake up"])):
                    self.is_asleep = False
                    send_face_cmd(emotion="happy"); speak("I am awake."); send_face_cmd(emotion="neutral")
                    continue
                else: continue
            
            print(f"👤 You: {user_text}")

            match = re.search(r"(?:this is|i am|it's) (\w+)", ut_lower)
            if match and match.group(1) in CONFIG["users"]:
                if match.group(1) != self.current_user_name:
                    if self.switch_user(match.group(1)): continue

            # --- COMMAND: CALENDAR ---
            if any(c in ut_lower for c in CMD_LIST.get("calendar", [])):
                print("📅 Calendar Triggered")
                cal_data = process_calendar_request(user_text)
                if "error" not in cal_data:
                    data = load_user_data(self.current_memory_file)
                    data["calendar"].append(cal_data)
                    save_user_data(data, self.current_memory_file)
                    speak(f"Scheduled {cal_data['event']} for {cal_data['date']}.")
                    continue

            # --- COMMAND: CLOUD QUERY ---
            if any(c in ut_lower for c in CMD_LIST.get("cloud_query", [])):
                speak("Checking the cloud.")
                
                # Cloud Prompt
                cloud_prompt = [
                    {"role": "system", "content": f"You are Sparky. Answer briefly. {self.user_metadata}"},
                    {"role": "user", "content": user_text}
                ]
                
                start_think = time.time()
                cloud_reply = query_cloud_api(cloud_prompt)
                print(f"☁️ Cloud Latency: {time.time() - start_think:.2f}s")
                
                self.chat_history.append({'role': 'user', 'content': user_text})
                self.chat_history.append({'role': 'assistant', 'content': cloud_reply})
                
                speak(cloud_reply)
                continue 

            # --- COMMAND: MUTE / STOP LISTENING ---
            if any(c in ut_lower for c in CMD_LIST.get("mute", [])):
                speak("Microphone muted. Say 'Sparky' to wake me.")
                self.is_asleep = True
                send_face_cmd(emotion="sleep")
                continue

            # --- COMMAND: SLEEP ---
            if any(c in ut_lower for c in CMD_LIST.get("sleep", [])):
                self.is_asleep = True
                send_face_cmd(emotion="sleep")
                if self.current_memory_file:
                    self.chat_history.append({'role': 'user', 'content': user_text})
                    self.save_current_session()
                speak("Going to sleep.")
                continue

            # --- COMMAND: EXIT ---
            if any(c in ut_lower for c in CMD_LIST.get("exit", [])):
                speak("Shutting down.")
                if self.current_memory_file:
                    self.chat_history.append({'role': 'user', 'content': user_text})
                    self.save_current_session()
                sys.exit(0)

            # --- NORMAL LLM FLOW ---
            if self.turns_since_summary >= self.summary_interval:
                print("🔄 Compressing memory...")
                chunk_to_compress = self.chat_history[:-2] 
                if chunk_to_compress:
                    summary = perform_summarization(chunk_to_compress)
                    if summary: 
                        self.session_summary_buffer.append(summary)
                        print(f"   Stored Summary: {summary}")
                    self.chat_history = self.chat_history[-2:]
                    self.turns_since_summary = 0

            send_face_cmd(emotion="thinking")
            current_date = datetime.now().strftime("%A, %B %d, %Y")
            specs = CONFIG.get("system_specs", "")
            
            session_context = " ".join(self.session_summary_buffer[-3:])
            
            full_system_prompt = (
                f"{self.current_base_prompt}\n"
                f"Date: {current_date}. Hardware: {specs}\n"
                f"User Info: {self.user_metadata}\n"
                f"Long Term Memory: {self.long_term_memory}\n"
                f"Current Session Context: {session_context}"
            )
            
            messages = [{'role': 'system', 'content': full_system_prompt}] + self.chat_history
            messages.append({'role': 'user', 'content': user_text})
            
            start_think = time.time()
            try:
                response = ollama_client.chat(model=OLLAMA_MODEL, messages=messages)
                bot_reply = response['message']['content']
            except Exception as e:
                print(f"Server Error: {e}"); bot_reply = "I'm having a brain freeze."
            print(f"🤔 Thought for {time.time() - start_think:.2f}s")

            self.chat_history.append({'role': 'user', 'content': user_text})
            self.chat_history.append({'role': 'assistant', 'content': bot_reply})
            self.turns_since_summary += 1
            
            if len(self.chat_history) > self.context_window: 
                self.chat_history = self.chat_history[-self.context_window:]

            send_face_cmd(emotion="neutral")
            speak(bot_reply)
            send_face_cmd(emotion="neutral")

if __name__ == "__main__":
    bot = SparkyBot()
    bot.run()