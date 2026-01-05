import os
import sounddevice as sd
import soundfile as sf
import numpy as np
import re
import tempfile
import scipy.signal
import subprocess

class TTSService:
    def __init__(self, model_path="modules/voices/ryan.onnx", device_index=0, debug=False):
        self.debug = debug
        self.model_path = model_path
        
        # Hardcoded path to the binary you just downloaded
        # Assuming you extracted it to /home/steve/piper/
        self.piper_binary = "/home/steve/piper/piper"
        
        if not os.path.exists(self.piper_binary):
            raise FileNotFoundError(f"Piper binary not found at {self.piper_binary}")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Voice model not found at {model_path}")

        # Standard USB Audio sample rate
        self.target_rate = 48000
        self.device_index = device_index
        
        print(f"🔊 TTS Service Online (Binary Mode)")
        print(f"   Model: {model_path}")
        print(f"   Binary: {self.piper_binary}")

    def speak(self, text):
        if self.debug:
            print(f"   [TTS Debug] Speaking: '{text[:30]}...'")
            
        sentences = re.split(r'(?<=[.!?])\s+', text)
        for sentence in sentences:
            if not sentence.strip(): continue
            self._play_segment(sentence)
        
        sd.stop()

    def _play_segment(self, text):
        # 1. Create a temp file path
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            temp_path = f.name

        try:
            # 2. Call the Piper Binary via Command Line
            # echo "Hello" | ./piper --model voice.onnx --output_file out.wav
            cmd = [
                self.piper_binary,
                "--model", self.model_path,
                "--output_file", temp_path,
                "--quiet" # Suppress Piper's own logs unless debugging
            ]
            
            # Run the command, passing text to stdin
            result = subprocess.run(
                cmd, 
                input=text.encode('utf-8'),
                capture_output=True
            )
            
            if result.returncode != 0:
                print(f"❌ Piper Binary Error: {result.stderr.decode()}")
                return

            # 3. Read the generated WAV file
            data, fs = sf.read(temp_path)
            
            if len(data) == 0:
                if self.debug: print("   [TTS Debug] ⚠️ Binary generated 0 bytes.")
                return

            # 4. Resample if necessary (22050 -> 48000)
            if fs != self.target_rate:
                # Calculate new length
                number_of_samples = round(len(data) * float(self.target_rate) / fs)
                data = scipy.signal.resample(data, number_of_samples)
                # Convert back to 16-bit PCM
                data = (data * 32767).astype(np.int16)
            
            # 5. Play
            sd.play(data, samplerate=self.target_rate, device=self.device_index)
            sd.wait()
            
        except Exception as e:
            print(f"❌ TTS Playback Error: {e}")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)