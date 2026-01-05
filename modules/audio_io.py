import sounddevice as sd
import soundfile as sf
import numpy as np

# --- CONFIGURATION ---
SAMPLE_RATE = 48000
CHANNELS = 6
OUTPUT_FILENAME = "test_recording.wav"
# We search for this substring in the device name
TARGET_DEVICE_NAME = "USB Audio" 

def get_input_device_id(name_substring):
    """
    Scans for a device containing the target name.
    Returns the ID of the first match, or raises an error.
    """
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        # We only care about Input devices (max_input_channels > 0)
        if name_substring in dev['name'] and dev['max_input_channels'] > 0:
            print(f"✅ Found Target Device: '{dev['name']}' at ID {i}")
            return i
    
    # If we get here, no device was found
    raise ValueError(f"❌ Could not find audio device matching '{name_substring}'")

def extract_primary_channel(audio_data):
    """Extract Channel 0 (Primary Beamformed Channel)"""
    return audio_data[:, 0]

def record_audio(duration, fs, channels, device_id):
    print(f"🎤 Recording for {duration} seconds...")
    raw_recording = sd.rec(int(duration * fs), 
                           samplerate=fs, 
                           channels=channels, 
                           device=device_id, 
                           dtype='float32', 
                           blocking=True)
    clean_mono = extract_primary_channel(raw_recording)
    print("✅ Recording complete.")
    return clean_mono

def play_audio(data, fs, device_id):
    print("🔊 Playing back audio...")
    sd.play(data, fs, device=device_id, blocking=True)
    print("✅ Playback complete.")

def save_to_file(filename, data, fs):
    sf.write(filename, data, fs)
    print(f"💾 Saved to {filename}")

if __name__ == "__main__":
    try:
        # Dynamically find the ID
        device_id = get_input_device_id(TARGET_DEVICE_NAME)
        
        # Run Test
        clean_audio = record_audio(5, SAMPLE_RATE, CHANNELS, device_id)
        play_audio(clean_audio, SAMPLE_RATE, device_id)
        save_to_file(OUTPUT_FILENAME, clean_audio, SAMPLE_RATE)
        
    except Exception as e:
        print(e)
