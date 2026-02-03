import time
import os
import sys
import json
import re
import socket
import subprocess
import requests
import argparse
import random
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
import onnxruntime as ort
ort.set_default_logger_severity(3) 
from datetime import datetime, timedelta
from faster_whisper import WhisperModel

# --- IMPORT VISION MODULE ---
try:
    from sparky_vision import SparkyVision
except ImportError:
    print("⚠️  Warning: sparky_vision.py not found. Vision features will be disabled.")
    SparkyVision = None

# --- VERSION CONTROL ---
SPARKY_VERSION = "9.6 (Echo Cancellation)"

# --- CONFIG & TUNING ---
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
THERMAL_LOG_PATH = os.path.join(BASE_DIR, "thermal_log.txt")

# TUNING: How loud you must speak to interrupt Sparky (0.0 to 1.0)
# RAISED to 0.30 to prevent self-interruption
INTERRUPT_THRESHOLD = 0.30 

def load_config():
    try:
        with open(CONFIG_PATH, "r") as f: return json.load(f)
    except FileNotFoundError: return {}
CONFIG = load_config()
CMD_LIST = CONFIG.get("commands", {})

# --- FAST GREETINGS ---
GREETINGS = [
    "Hello {name}. Systems are ready.",
    "Greetings {name}. How can I help?",
    "Hi {name}. I am listening.",
    "Welcome back, {name}.",
    "Systems online. Hello {name}."
]

# Setup Paths
PIPER_BINARY = os.path.join(BASE_DIR, CONFIG.get("voice", {}).get("binary_path", "src/piper_engine/piper/piper"))
VOICE_MODEL = os.path.join(BASE_DIR, CONFIG.get("voice", {}).get("model_path", "src/piper_engine/en_US-lessac-medium.onnx"))
DATA_DIR = os.path.join(BASE_DIR, "data/users")
os.makedirs(DATA_DIR, exist_ok=True)

# --- WHISPER LOADING (WITH MEMORY FALLBACK) ---
WHISPER_CFG = CONFIG.get("whisper", {})
WHISPER_SIZE = WHISPER_CFG.get("size", "base.en") 
COMPUTE_TYPE = WHISPER_CFG.get("compute_type", "int8_float16")
DEVICE = "cuda"

print(f"⏳ Loading Whisper ({WHISPER_SIZE} / {COMPUTE_TYPE})...")
try:
    whisper = WhisperModel(WHISPER_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
    print("✅ Whisper Loaded on GPU.")
except Exception as e:
    print(f"⚠️ Whisper GPU Load Failed (OOM?): {e}")
    print("   -> Switching to CPU (int8) to prevent crash.")
    whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    print("✅ Whisper Loaded on CPU (Fallback Mode).")

# Ollama Config
OLLAMA_CFG = CONFIG.get("ollama", {})
OLLAMA_HOST = OLLAMA_CFG.get("host", "http://127.0.0.1:11434")
OLLAMA_MODEL = OLLAMA_CFG.get("model", "llama3.2")
OLLAMA_TIMEOUT = OLLAMA_CFG.get("timeout", 120) 
OLLAMA_KEEP_ALIVE = OLLAMA_CFG.get("keep_alive", -1)
OLLAMA_URL = f"{OLLAMA_HOST}/api/chat"

# --- VISUAL FEEDBACK HELPERS ---
UDP_IP = "127.0.0.1"; UDP_PORT = 5005
def send_face_cmd(mouth_val=None, emotion=None, error_msg=None, command=None):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    data = {}
    if mouth_val is not None: data["mouth"] = mouth_val
    if emotion is not None: data["emotion"] = emotion
    if error_msg is not None: data["error"] = error_msg
    if command is not None: data["command"] = command
    try: sock.sendto(json.dumps(data).encode(), (UDP_IP, UDP_PORT))
    except: pass

def send_error(msg):
    print(f"⚠️ Error: {msg}")
    send_face_cmd(error_msg=msg)

# --- LLM ENGINE ---
def query_local_llm(messages, timeout=None, silent_errors=False):
    if timeout is None: timeout = OLLAMA_TIMEOUT
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "keep_alive": OLLAMA_KEEP_ALIVE
    }
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json()['message']['content']
    except requests.exceptions.Timeout:
        if not silent_errors:
            send_error(f"Brain Timeout ({timeout}s)")
            return "I am thinking too hard and my brain froze."
        return None
    except Exception as e:
        if not silent_errors:
            send_error(f"Brain Error: {str(e)[:20]}")
            return "My internal brain is not responding."
        return None

def query_cloud_api(messages):
    cfg = CONFIG.get("cloud_api", {})
    key = cfg.get("api_key", "")
    if not key or "YOUR" in key:
        send_error("Config: Missing Cloud API Key")
        return "I need a valid API key."
    try:
        print(f"☁️ Cloud ({cfg.get('model')})...")
        res = requests.post(
            cfg.get("url"),
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"model": cfg.get("model"), "messages": messages, "temperature": 0.7},
            timeout=10
        )
        if res.status_code == 200:
            return res.json()['choices'][0]['message']['content']
        else:
            return f"Cloud Error {res.status_code}"
    except Exception as e:
        send_error("Cloud Connection Failed")
        return "I could not reach the cloud."

# --- THERMAL MONITOR ---
def get_cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
            return int(f.read().strip()) / 1000.0 
    except: return 0.0

# --- MEMORY ---
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
    return {"history": [], "calendar": []}

def save_user_data(data, filename):
    with open(os.path.join(DATA_DIR, filename), "w") as f: json.dump(data, f, indent=4)

def cleanup_calendar(data):
    if not data.get("calendar"): return data, 0
    today = datetime.now().date()
    valid = []; cleaned = 0
    for item in data["calendar"]:
        try:
            if datetime.strptime(item['date'], "%Y-%m-%d").date() >= today: valid.append(item)
            else: cleaned += 1
        except: valid.append(item)
    data["calendar"] = valid
    return data, cleaned

def check_upcoming_events(data):
    if not data: return ""
    upcoming = []
    today = datetime.now().date()
    for item in data:
        try:
            d = datetime.strptime(item['date'], "%Y-%m-%d").date()
            delta = (d - today).days
            if 0 <= delta <= 5:
                day = d.strftime("%A")
                if delta == 0: day = "Today"
                if delta == 1: day = "Tomorrow"
                upcoming.append(f"{day}: {item['event']}")
        except: continue
    return " Upcoming: " + ". ".join(upcoming) + "." if upcoming else ""

def process_calendar_request(text):
    prompt = f"Date: {datetime.now().strftime('%Y-%m-%d')}. Input: '{text}'. Extract JSON {{'date': 'YYYY-MM-DD', 'event': 'desc'}}"
    try:
        content = query_local_llm([{'role': 'user', 'content': prompt}])
        return json.loads(content.replace("```json", "").replace("```", "").strip())
    except:
        send_error("Calendar Parse Fail")
        return {"error": "failed"}

def perform_summarization(history):
    if not history: return None
    prompt = "Summarize the conversation in 1-2 factual sentences. Do NOT reply to user. If trivial, return 'NO_DATA'."
    return query_local_llm([{'role': 'system', 'content': prompt}])

def clean_and_extract_emotion(text):
    actions = re.findall(r'\*(.*?)\*', text)
    for a in actions:
        if "smile" in a or "happy" in a.lower(): send_face_cmd(emotion="happy")
        elif "think" in a.lower(): send_face_cmd(emotion="thinking")
        elif "sleep" in a.lower(): send_face_cmd(emotion="sleep")
    return re.sub(r'\*.*?\*', '', text).strip()

# --- AUDIO PLAYER (INTERRUPT ENABLED + ECHO GUARD) ---
def play_audio(filename, allow_interrupt=True):
    data, fs = sf.read(filename, dtype='float32')
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    chunk_size = 1024
    current_pos = 0
    was_interrupted = False
    
    # Track playback time for the Grace Period
    playback_start_time = time.time()
    GRACE_PERIOD = 1.5 # Ignore interruptions for the first 1.5 seconds

    out_stream = sd.OutputStream(samplerate=fs, channels=1, blocksize=chunk_size)
    out_stream.start()
    
    in_stream = None
    if allow_interrupt:
        try:
            in_stream = sd.InputStream(channels=1, blocksize=chunk_size)
            in_stream.start()
        except Exception:
            allow_interrupt = False

    try:
        while current_pos < len(data):
            chunk = data[current_pos : current_pos + chunk_size]
            if len(chunk) < chunk_size:
                chunk = np.pad(chunk, (0, chunk_size - len(chunk)))
            out_stream.write(chunk)
            
            amplitude = float(np.sqrt(np.mean(chunk**2))) 
            viseme = min(amplitude * 10, 1.0)
            sock.sendto(json.dumps({"mouth": viseme}).encode(), (UDP_IP, UDP_PORT))

            if allow_interrupt and in_stream:
                try:
                    mic_chunk, _ = in_stream.read(chunk_size)
                    mic_vol = np.sqrt(np.mean(mic_chunk**2))
                    
                    # --- NEW: Check Grace Period ---
                    elapsed = time.time() - playback_start_time
                    if elapsed > GRACE_PERIOD and mic_vol > INTERRUPT_THRESHOLD:
                        print(f"🛑 INTERRUPT DETECTED (Vol: {mic_vol:.3f})")
                        was_interrupted = True
                        break
                except Exception: pass
            current_pos += chunk_size
    except Exception as e:
        print(f"Audio Error: {e}")
    
    out_stream.stop(); out_stream.close()
    if in_stream: in_stream.stop(); in_stream.close()
    send_face_cmd(mouth_val=0.0)
    return was_interrupted

def speak(text, interruptible=True):
    final = clean_and_extract_emotion(text)
    if not final: return False
    print(f"🗣️ Sparky: {final}")
    try:
        subprocess.run([PIPER_BINARY, "--model", VOICE_MODEL, "--output_file", "output.wav"], 
                       input=final.encode('utf-8'), check=True, stderr=subprocess.DEVNULL)
        interrupted = play_audio("output.wav", allow_interrupt=interruptible)
        return interrupted 
    except Exception as e: 
        send_error("TTS Generation Failed")
        print(e)
        return False

def listen_to_mic(threshold, silence, max_dur):
    fs=16000; blk=4096; buf=[]; silent=0; spoken=False
    max_s = int(silence*fs/blk); max_t = int(max_dur*fs/blk)
    time.sleep(0.3) 
    
    with sd.InputStream(samplerate=fs, channels=1, dtype='float32') as st:
        while True:
            ch, _ = st.read(blk); buf.append(ch)
            if np.sqrt(np.mean(ch**2)) > threshold: silent=0; spoken=True
            elif spoken: silent+=1
            if spoken and silent>max_s: break
            if len(buf)>max_t: break
    if not spoken: return None
    
    segs, _ = whisper.transcribe(
        np.concatenate(buf).flatten(), 
        beam_size=5, 
        language="en", 
        vad_filter=True, 
        vad_parameters=dict(min_silence_duration_ms=500),
        initial_prompt="Hello Sparky. This is a conversation." 
    )

    txt = "".join([s.text for s in segs]).strip()
    if any(h in txt for h in ["Thank you", "Subtitles", "Copyright"]) or len(txt)<2: return None
    return txt

class SparkyBot:
    def __init__(self, start_mode="voice"):
        print(f"\n🤖 Sparky V{SPARKY_VERSION} Initialized.")
        
        # --- START VISION (WITH EFFICIENCY DEFAULTS) ---
        if SparkyVision:
            # Default to 'n' (nano) model if not specified in config
            v_size = CONFIG.get("vision", {}).get("model_size", "n")
            self.vision = SparkyVision(model_size=v_size)
            self.vision.start()
        else:
            self.vision = None

        print(f"⚙️ LLM Timeout set to: {OLLAMA_TIMEOUT}s")
        self.chat_history = []
        self.session_buffer = [] 
        self.is_asleep = True 
        self.curr_user = None; self.curr_mem = None
        self.input_mode = start_mode
        self.sys_cfg = CONFIG.get("system_settings", {})
        self.base_prompt = CONFIG.get("default_prompt", "You are a robot.")
        self.lt_mem = ""; self.meta = "" 
        self.int_cfg = CONFIG.get("interaction", {})
        self.thermal_cfg = CONFIG.get("thermal", {})
        
        print("🧠 Pre-loading Ollama model...")
        threading.Thread(target=query_local_llm, args=([{'role':'user','content':'hi'}],), 
                         kwargs={'timeout': OLLAMA_TIMEOUT, 'silent_errors': True}).start()

        if self.thermal_cfg.get("enabled", False):
            try:
                with open(THERMAL_LOG_PATH, "w") as f:
                    f.write(f"--- Sparky Thermal Log: {datetime.now()} ---\n")
                print(f"🌡️ Logging thermals to: {THERMAL_LOG_PATH}")
            except: pass

    def switch_user(self, name):
        name = name.lower()
        if name not in CONFIG["users"]: return False
        if self.curr_mem: self.save_session()
        
        self.chat_history = []; self.session_buffer = []
        ucfg = CONFIG["users"][name]
        self.curr_user = name.capitalize(); self.curr_mem = ucfg["memory_file"]
        self.base_prompt = ucfg["prompt"]
        
        udata = load_user_data(self.curr_mem)
        self.lt_mem = "\n".join(udata["history"][-5:])
        cal = check_upcoming_events(udata["calendar"])
        
        self.meta = f"User: {self.curr_user}."
        if "birthday" in ucfg: self.meta += f" B-day: {ucfg['birthday']}."

        print(f"👤 Switched to User: {self.curr_user}")
        base_greet = random.choice(GREETINGS).format(name=self.curr_user)
        full_greet = f"{base_greet} {cal}"
        speak(full_greet)
        self.chat_history.append({'role': 'assistant', 'content': full_greet})
        return True

    def save_session(self):
        summ = perform_summarization(self.chat_history)
        if summ and "NO_DATA" not in summ and "Error" not in summ:
            self.session_buffer.append(summ)
        if not self.session_buffer: return
        print(f"💾 Saving Session...")
        udata = load_user_data(self.curr_mem)
        udata, _ = cleanup_calendar(udata)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        udata["history"].append(f"[{ts}] {' '.join(self.session_buffer)}")
        save_user_data(udata, self.curr_mem)
        print("✅ Saved.")

    def monitor_thermals(self):
        cfg = self.thermal_cfg
        if not cfg.get("enabled", False): return
        warn_thresh = cfg.get("warning_temp", 80)
        crit_thresh = cfg.get("shutdown_temp", 90)
        interval = cfg.get("check_interval", 5)
        warned = False
        while True:
            temp = get_cpu_temp()
            try:
                with open(THERMAL_LOG_PATH, "a") as f:
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    f.write(f"[{timestamp}] Temp: {temp}°C\n")
            except: pass

            if temp >= crit_thresh:
                send_face_cmd(emotion="angry", error_msg=f"OVERHEAT {temp}C")
                speak(f"Critical temperature {temp} degrees. Initiating emergency shutdown.", interruptible=False)
                if self.curr_mem: self.save_session()
                if self.vision: self.vision.stop()
                send_face_cmd(command="shutdown")
                print(f"🔥 THERMAL SHUTDOWN TRIGGERED ({temp}°C)")
                time.sleep(1)
                os._exit(0) 
            elif temp >= warn_thresh and not warned:
                send_face_cmd(emotion="angry", error_msg=f"HIGH TEMP {temp}C")
                speak(f"Warning. Core temperature is {temp} degrees.", interruptible=False)
                warned = True 
            elif temp < warn_thresh - 5:
                warned = False 
            time.sleep(interval)

    def run(self):
        t_thread = threading.Thread(target=self.monitor_thermals, daemon=True)
        t_thread.start()

        send_face_cmd(emotion="neutral")
        
        if self.input_mode == "text":
            self.is_asleep = False
            speak("Systems ready. Text mode active.", interruptible=False)
            print("⌨️ Text Mode.")
        else:
            self.is_asleep = True
            send_face_cmd(emotion="sleep")
            speak("Systems online. Waiting for wake word.", interruptible=False)
            print("💤 Systems online (Asleep). Say 'Wake Up' or 'Sparky'.")
        
        while True:
            try:
                if self.input_mode=="text": txt = input("\n⌨️ You: ")
                else: txt = listen_to_mic(self.int_cfg.get("mic_threshold", 0.02), self.int_cfg.get("silence_duration", 1.2), 60)
            except KeyboardInterrupt: break
            if not txt: continue
            
            txt_low = txt.lower()

            # --- BUG FIX: COMMON MISHEARINGS ---
            if "vision of" in txt_low:
                txt_low = txt_low.replace("vision of", "vision off")
                print("🛠️ Auto-correction: 'vision of' -> 'vision off'")
            # -----------------------------------
            
            # --- WAKE WORD LOGIC ---
            if self.is_asleep and self.input_mode=="voice":
                if any(c in txt_low for c in CMD_LIST.get("wake", ["wake up"])):
                    self.is_asleep=False
                    send_face_cmd(emotion="happy"); speak("I'm awake."); send_face_cmd(emotion="neutral")
                    print("🔔 Woke up!")
                else:
                    print(f"💤 Ignored: {txt}")
                continue
            
            if self.input_mode=="voice": print(f"👤 You: {txt}")

            # --- USER COMMANDS ---
            m = re.search(r"(?:this is|i am|it's) (\w+)", txt_low)
            if m and m.group(1) in CONFIG["users"]:
                if m.group(1) != self.curr_user: self.switch_user(m.group(1)); continue

            if any(c in txt_low for c in CMD_LIST.get("text_mode", [])):
                self.input_mode="text"; self.is_asleep=False; speak("Text mode."); continue
            if any(c in txt_low for c in CMD_LIST.get("voice_mode", [])):
                self.input_mode="voice"; speak("Voice mode."); continue

            if any(c in txt_low for c in CMD_LIST.get("calendar", [])):
                cd = process_calendar_request(txt)
                if "error" not in cd:
                    d = load_user_data(self.curr_mem)
                    d["calendar"].append(cd); save_user_data(d, self.curr_mem)
                    speak(f"Scheduled for {cd['date']}."); continue

            # --- VISION MODES ---
            vision_on_cmds = CMD_LIST.get("vision_on", []) + ["vision on", "enable vision", "activate vision"]
            vision_off_cmds = CMD_LIST.get("vision_off", []) + ["vision off", "disable vision", "stop vision"]
            
            # 1. Turn ON Vision Mode
            if any(c in txt_low for c in vision_on_cmds):
                if self.vision:
                    speak("Vision system online. Displaying camera feed.")
                    send_face_cmd(command="view_camera") 
                    self.vision.set_streaming(True)      
                else:
                    speak("Vision module not loaded.")
                continue
            
            # 2. Turn OFF Vision Mode
            if any(c in txt_low for c in vision_off_cmds):
                if self.vision:
                    speak("Vision system disabled. Returning to interface.")
                    send_face_cmd(command="view_face")   
                    self.vision.set_streaming(False)     
                continue

            # 3. Vision QUERY (What do you see?)
            vision_query_cmds = CMD_LIST.get("vision_query", []) + ["what do you see", "describe view", "what is that", "look at this"]
            
            if any(c in txt_low for c in vision_query_cmds):
                if self.vision:
                    scene_desc = self.vision.get_what_i_see()
                    print(f"👁️ Vision: {scene_desc}")
                    if "don't see" in scene_desc:
                        speak("I am having trouble seeing anything clearly.")
                    else:
                        speak(f"My sensors detect {scene_desc.replace('I can see', '')}")
                    self.chat_history.append({'role': 'user', 'content': txt})
                    vision_context = f"User asked: '{txt}'. Your visual sensors detect: {scene_desc}."
                    bot_reply = query_local_llm(self.chat_history + [{'role': 'system', 'content': vision_context}])
                    self.chat_history.append({'role': 'assistant', 'content': bot_reply})
                    
                    was_interrupted = speak(bot_reply)
                    if was_interrupted:
                        speak("Sorry, listening...", interruptible=False)
                else:
                    speak("I do not have eyes right now.")
                continue
            # ------------------------

            if any(c in txt_low for c in CMD_LIST.get("cloud_query", [])):
                speak("Checking cloud.")
                cp = [{"role": "system", "content": f"You are Sparky. {self.meta}"}, {"role": "user", "content": txt}]
                cr = query_cloud_api(cp)
                self.chat_history.append({'role': 'user', 'content': txt})
                self.chat_history.append({'role': 'assistant', 'content': cr})
                
                was_interrupted = speak(cr)
                if was_interrupted:
                    speak("Sorry, listening...", interruptible=False)
                continue 

            if any(c in txt_low for c in CMD_LIST.get("mute", [])):
                speak("Muted."); self.is_asleep=True; send_face_cmd(emotion="sleep"); continue

            if any(c in txt_low for c in CMD_LIST.get("sleep", [])):
                self.is_asleep=True; send_face_cmd(emotion="sleep")
                if self.curr_mem: self.save_session()
                speak("Going to sleep."); continue

            if any(c in txt_low for c in CMD_LIST.get("exit", [])):
                speak("Shutdown."); 
                if self.curr_mem: self.save_session()
                if self.vision: self.vision.stop()
                send_face_cmd(command="shutdown")
                time.sleep(0.2)
                sys.exit(0)

            # Auto-Summarization
            if len(self.chat_history) > self.sys_cfg.get("auto_summary_interval", 10):
                print("🔄 Compressing...")
                summ = perform_summarization(self.chat_history[:-2])
                if summ and "Error" not in summ: self.session_buffer.append(summ)
                self.chat_history = self.chat_history[-2:]

            # Normal Chat Processing
            send_face_cmd(emotion="thinking")
            spec = CONFIG.get("system_specs", "")
            sc = " ".join(self.session_buffer[-3:])
            sys_p = f"{self.base_prompt}\nDate: {datetime.now().strftime('%A')}. {spec}\nUser: {self.meta}\nMem: {self.lt_mem}\nCtx: {sc}"
            
            msgs = [{'role': 'system', 'content': sys_p}] + self.chat_history
            msgs.append({'role': 'user', 'content': txt})
            
            bot_reply = query_local_llm(msgs) 

            self.chat_history.append({'role': 'user', 'content': txt})
            self.chat_history.append({'role': 'assistant', 'content': bot_reply})
            if len(self.chat_history) > 10: self.chat_history = self.chat_history[-10:]

            send_face_cmd(emotion="neutral")
            
            was_interrupted = speak(bot_reply)
            if was_interrupted:
                speak("Sorry, listening...", interruptible=False)
                
            send_face_cmd(emotion="neutral")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true", help="Start in Text Mode")
    args = parser.parse_args()
    bot = SparkyBot(start_mode="text" if args.text else "voice")
    
    # --- SAFE EXIT ON CTRL+C ---
    try:
        bot.run()
    except KeyboardInterrupt:
        print("\n🛑 Force Stopping Sparky...")
        if bot.vision: 
            bot.vision.stop()
        send_face_cmd(command="shutdown")
        # FORCE KILL to prevent C++ memory dump
        os._exit(0)