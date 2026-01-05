import os
import sys
import time
import pyaudio
import numpy as np
import openwakeword
from openwakeword.model import Model
from contextlib import contextmanager

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

class WakeWordService:
    def __init__(self, models=["hey_jarvis_v0.1"], sensitivity=0.5):
        self.sensitivity = sensitivity
        self.models = models
        
        # Audio Config
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.MIC_RATE = 48000       
        self.TARGET_RATE = 16000    
        self.CHUNK_SIZE = 1280      
        self.DOWNSAMPLE_FACTOR = int(self.MIC_RATE / self.TARGET_RATE)
        self.READ_CHUNK = self.CHUNK_SIZE * self.DOWNSAMPLE_FACTOR

        # Load Models
        os.environ["ORT_LOGGING_LEVEL"] = "3" 
        print(f"⏳ Loading Wake Word Models: {self.models}...")
        
        # OpenWakeWord natively supports a list of paths
        self.model = Model(wakeword_models=self.models, inference_framework="tflite")
        
        print("🎤 Initializing Microphone...")
        with ignore_stderr():
            self.audio = pyaudio.PyAudio()
        
        self.stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.MIC_RATE,
            input=True,
            frames_per_buffer=self.READ_CHUNK
        )
        
        self.last_trigger_time = 0
        self.cooldown_seconds = 2.0

    def listen(self):
        """
        Blocks until ANY of the loaded wake words are detected.
        Returns True on success.
        """
        self.model.reset()
        while True:
            try:
                raw_bytes = self.stream.read(self.READ_CHUNK, exception_on_overflow=False)
                audio_int16 = np.frombuffer(raw_bytes, dtype=np.int16)
                audio_resampled = audio_int16[::self.DOWNSAMPLE_FACTOR]
                
                # Predict
                prediction = self.model.predict(audio_resampled)
                
                # Check all models
                for model_name, score in prediction.items():
                    if score > self.sensitivity:
                        if (time.time() - self.last_trigger_time) > self.cooldown_seconds:
                            self.last_trigger_time = time.time()
                            # Optional debug print to see which word triggered it
                            # print(f"⚡ Triggered by: {model_name} ({score:.2f})")
                            return True 
                            
            except KeyboardInterrupt:
                return False

    def cleanup(self):
        self.stream.stop_stream()
        self.stream.close()
        self.audio.terminate()