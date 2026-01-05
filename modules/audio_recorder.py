import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os

# Hardware Config (Must match your Wakeword config)
SAMPLE_RATE = 48000 
CHANNELS = 6
TARGET_CHANNEL = 0 # Beamformed channel

class AudioRecorder:
    def __init__(self, output_dir="temp_audio"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
            
    def record(self, duration=5, filename="command.wav"):
        print(f"Listening for {duration} seconds...")
        
        # Record raw audio
        recording = sd.rec(
            int(duration * SAMPLE_RATE), 
            samplerate=SAMPLE_RATE, 
            channels=CHANNELS, 
            dtype='int16' # Whisper expects float, but we save as WAV first
        )
        sd.wait()  # Wait until recording is finished
        
        # Slicing: Extract only the beamformed channel
        # We process it to make it mono for Whisper
        mono_audio = recording[:, TARGET_CHANNEL]
        
        # Save to file
        filepath = os.path.join(self.output_dir, filename)
        wav.write(filepath, SAMPLE_RATE, mono_audio)
        
        print("Recording complete.")
        return filepath

if __name__ == "__main__":
    rec = AudioRecorder()
    rec.record(3)