import sounddevice as sd
import numpy as np

print("📋 Available Audio Devices:")
print(sd.query_devices())

print("\n🎵 Playing a test tone to the 'default' device...")
fs = 44100
seconds = 2
t = np.linspace(0, seconds, seconds * fs, False)
# Generate a 440Hz sine wave
note = np.sin(440 * t * 2 * np.pi)

# Normalize to 16-bit range and convert, just like our pipeline
audio = (note * 32767).astype(np.int16)

try:
    sd.play(audio, fs)
    sd.wait()
    print("✅ Done. Did you hear a beep?")
except Exception as e:
    print(f"❌ Playback failed: {e}")