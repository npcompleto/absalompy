import sounddevice as sd
import json

devices = sd.query_devices()
print(f"Total devices: {len(devices)}")
for i, d in enumerate(devices):
    print(f"[{i}] {d['name']} - Max Input: {d['max_input_channels']}, Default Rate: {d['default_samplerate']}")

print("\n--- Testing 16000 on all input devices ---")
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        try:
            sd.check_input_settings(device=i, samplerate=16000)
            print(f"Device [{i}] supports 16000 Hz")
        except Exception as e:
            print(f"Device [{i}] DOES NOT support 16000 Hz: {e}")

print("\n--- Testing 44100 on all input devices ---")
for i, d in enumerate(devices):
    if d['max_input_channels'] > 0:
        try:
            sd.check_input_settings(device=i, samplerate=44100)
            print(f"Device [{i}] supports 44100 Hz")
        except Exception as e:
            print(f"Device [{i}] DOES NOT support 44100 Hz: {e}")
