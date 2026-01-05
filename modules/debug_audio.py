import sounddevice as sd
import soundfile as sf
import numpy as np
import os

# --- CONFIGURATION ---
SAMPLE_RATE = 48000
CHANNELS = 6
DURATION = 5
DEVICE_ID = 0  # Based on your previous output, 0 is the SP200

def debug_device_info():
    """Prints detailed info about the selected device."""
    try:
        info = sd.query_devices(DEVICE_ID)
        print(f"\n🔍 INSPECTING DEVICE {DEVICE_ID}:")
        print(f"   Name: {info['name']}")
        print(f"   Max Input Channels: {info['max_input_channels']}")
        print(f"   Default Sample Rate: {info['default_samplerate']}")
        print("-" * 40)
    except Exception as e:
        print(f"❌ Error finding device {DEVICE_ID}: {e}")

def analyze_channels(audio_data):
    """Analyzes volume of each channel to see which are active."""
    print("\n📊 CHANNEL ANALYSIS:")
    print("   (RMS Amplitude - Higher is louder)")
    
    best_channel = 0
    max_vol = 0
    
    for i in range(CHANNELS):
        # Calculate volume (Root Mean Square)
        col = audio_data[:, i]
        volume = np.sqrt(np.mean(col**2))
        
        # Check for silence or clipping
        status = "🟢 OK"
        if volume < 0.001: status = "⚪ SILENT"
        if volume > 0.9:   status = "🔴 CLIPPING"
        
        print(f"   Channel {i}: {volume:.5f}  [{status}]")
        
        if volume > max_vol:
            max_vol = volume
            best_channel = i
            
    print(f"\n🏆 Loudest Channel appears to be: {best_channel}")
    return best_channel

if __name__ == "__main__":
    debug_device_info()
    
    print(f"\n🎤 Recording {DURATION} seconds on {CHANNELS} channels...")
    print("   Please speak continuously: 'Testing 1, 2, 3...'")
    
    # Record raw 6-channel audio
    recording = sd.rec(int(DURATION * SAMPLE_RATE), 
                       samplerate=SAMPLE_RATE, 
                       channels=CHANNELS, 
                       device=DEVICE_ID, 
                       dtype='float32', 
                       blocking=True)
    print("✅ Recording complete.\n")

    # 1. Analyze Volumes
    analyze_channels(recording)

    # 2. Save the full multi-channel file (for reference)
    sf.write("debug_full_6ch.wav", recording, SAMPLE_RATE)
    print(f"💾 Saved raw output to: debug_full_6ch.wav")

    # 3. Save EACH channel individually
    print("💾 Splitting channels to separate files...")
    for i in range(CHANNELS):
        filename = f"debug_channel_{i}.wav"
        # Extract just column 'i'
        single_channel = recording[:, i]
        sf.write(filename, single_channel, SAMPLE_RATE)
        print(f"   -> Saved {filename}")

    print("\n🧐 ACTION REQUIRED:")
    print("   Please listen to 'debug_channel_0.wav', 'debug_channel_1.wav', etc.")
    print("   The one that sounds clear is the one we should use.")
