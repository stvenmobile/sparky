import sounddevice as sd

print("------------------------------------------------")
print(f"HOST API: {sd.get_portaudio_version()[1]}")
print("------------------------------------------------")

devices = sd.query_devices()
for i, dev in enumerate(devices):
    # Only show input devices (max_input_channels > 0)
    if dev['max_input_channels'] > 0:
        print(f"Index {i}: {dev['name']}")
        print(f"   --> Channels: {dev['max_input_channels']}, Rate: {dev['default_samplerate']}")
print("------------------------------------------------")