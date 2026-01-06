from faster_whisper import WhisperModel
import logging
import os

# Configuration
MODEL_SIZE = "base.en" 
DEVICE = "cuda" # Uses the Orin's GPU
COMPUTE_TYPE = "float16" # Orin NX supports float16

class STTService:
    def __init__(self):
        print(f"Loading Whisper Model ({MODEL_SIZE}) on {DEVICE}...")
        try:
            self.model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
            print("Whisper Model Loaded Successfully.")
        except Exception as e:
            print(f"Error loading Whisper: {e}")
            print("Fallback: Trying CPU (slower)...")
            self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    def transcribe(self, audio_file_path):
        """
        Transcribes an audio file to text.
        """
        if not os.path.exists(audio_file_path):
            return ""

        segments, info = self.model.transcribe(audio_file_path, beam_size=5)
        
        full_text = ""
        for segment in segments:
            full_text += segment.text
            
        return full_text.strip()

if __name__ == "__main__":
    # Test stub
    stt = STTService()
    print("STT Service Ready.")