import os
import sys
import time
import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model
from contextlib import contextmanager

# --- SILENCE ALSA ERRORS ---
@contextmanager
def ignore_stderr():
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        old_stderr = os.dup(2)
        sys.stderr.flush()
        os.dup2(devnull, 2)
        os.close(devnull)
        yield
    finally:
        os.dup2(old_stderr, 2)
        os.close(old_stderr)

# --- CONFIGURATION ---
TARGET_RATE = 16000 
MIC_RATE = 48000    
CHUNK_SIZE = 1280   
DOWNSAMPLE_FACTOR = int(MIC_RATE / TARGET_RATE)
READ_CHUNK = CHUNK_SIZE * DOWNSAMPLE_FACTOR 

# THRESHOLD (Adjust this if Sparky is too deaf or too sensitive)
THRESHOLD = 0.5

# --- LOAD SPARKY MODEL ---
os.environ["ORT_LOGGING_LEVEL"] = "3" 
print("⏳ Loading 'Hey jarvis' model...")

# *** UPDATED PATH HERE ***
owwModel = Model(wakeword_models=["jarvis_v0.1.tflite"], inference_framework="tflite")

# --- AUDIO SETUP ---
print("🎤 Initializing Audio...")
with ignore_stderr():
    audio = pyaudio.PyAudio()

stream = audio.open(
    format=pyaudio.paInt16,
    channels=1,
    rate=MIC_RATE,
    input=True,
    frames_per_buffer=READ_CHUNK
)

print(f"\n👂 Listening for 'Hey jarvis'...")
print(f"   (Threshold: {THRESHOLD})")
print("------------------------------------------------")

try:
    while True:
        # 1. Read & Process
        raw_bytes = stream.read(READ_CHUNK, exception_on_overflow=False)
        audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
        audio_resampled = audio_int16[::DOWNSAMPLE_FACTOR]

        # 2. Predict
        prediction = owwModel.predict(audio_resampled)
        
        # 3. Check Results
        for model_name, score in prediction.items():
            if score > THRESHOLD:
                print(f"\n⚡ SPARKY DETECTED! (Score: {score:.3f})")
                owwModel.reset()
            elif score > 0.1:
                # Print a dot for near-misses so you know it's listening
                print(".", end="", flush=True)

except KeyboardInterrupt:
    print("\n👋 Stopping...")
    stream.stop_stream()
    stream.close()
    audio.terminate()