import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import os
import time
from collections import deque

# Hardware Config
SAMPLE_RATE = 48000 
CHANNELS = 6
TARGET_CHANNEL = 0  # Beamformed channel
CHUNK_SIZE = 1024   # How many samples to read at a time

class AudioRecorder:
    def __init__(self, output_dir="temp_audio"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def calculate_rms(self, audio_chunk):
        """Calculates the volume (Root Mean Square) of the chunk."""
        # Convert to float for calculation to avoid overflow
        data = audio_chunk.astype(np.float64)
        rms = np.sqrt(np.mean(data**2))
        return rms

    def record(self, max_duration=15, silence_limit=1.5, threshold=500, filename="command.wav"):
        """
        Records audio until silence is detected.
        
        :param max_duration: Force stop after this many seconds (safety net)
        :param silence_limit: Stop recording after this many seconds of silence
        :param threshold: Volume level to trigger 'speech' (adjust based on your mic)
        """
        print(f"👂 Listening... (Max: {max_duration}s, Stop on Silence: {silence_limit}s)")
        
        audio_buffer = [] # Stores valid speech chunks
        pre_speech_buffer = deque(maxlen=int(SAMPLE_RATE / CHUNK_SIZE * 0.5)) # Keeps 0.5s of audio BEFORE speech
        
        silence_start_time = None
        speech_started = False
        start_time = time.time()
        
        # Open the stream
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=CHANNELS, dtype='int16', blocksize=CHUNK_SIZE) as stream:
            while True:
                # 1. Read a chunk of audio
                # 'read' returns (data, overflow_flag)
                data, _ = stream.read(CHUNK_SIZE)
                
                # 2. Extract only the beamformed channel (Mono)
                mono_chunk = data[:, TARGET_CHANNEL]
                
                # 3. Check Volume
                rms = self.calculate_rms(mono_chunk)
                
                # --- LOGIC: WAITING FOR SPEECH ---
                if not speech_started:
                    # Keep a rolling buffer of "silence" so we don't cut off the first syllable
                    pre_speech_buffer.append(mono_chunk)
                    
                    if rms > threshold:
                        print("🎤 Speech Detected! Recording...")
                        speech_started = True
                        # Dump the pre-roll buffer into the main buffer
                        audio_buffer.extend(pre_speech_buffer)
                    
                    # Timeout if no one speaks
                    if (time.time() - start_time) > max_duration:
                        print("❌ Timeout: No speech detected.")
                        return None

                # --- LOGIC: RECORDING ---
                else:
                    audio_buffer.append(mono_chunk)
                    
                    # Check for Silence
                    if rms < threshold:
                        if silence_start_time is None:
                            silence_start_time = time.time()
                        elif (time.time() - silence_start_time) > silence_limit:
                            print("✅ Silence detected. Stopping.")
                            break
                    else:
                        # Reset silence timer if we hear noise again
                        silence_start_time = None

                    # Hard Safety Timeout
                    if (time.time() - start_time) > max_duration:
                        print("⚠️ Max duration reached. Stopping.")
                        break

        # 4. Save to File
        if not audio_buffer:
            return None

        # Concatenate all chunks into one array
        full_audio = np.concatenate(audio_buffer, axis=0)
        
        filepath = os.path.join(self.output_dir, filename)
        wav.write(filepath, SAMPLE_RATE, full_audio)
        
        return filepath

if __name__ == "__main__":
    rec = AudioRecorder()
    # Test it! (Speak, then stop and wait 1.5s)
    path = rec.record(max_duration=10, silence_limit=1.5, threshold=600)
    if path:
        print(f"Saved to {path}")