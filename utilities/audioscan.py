import ffmpeg
import sounddevice as sd
import numpy as np
import tempfile
import os
import soundfile as sf  # Import soundfile as sf
import keyboard  # For detecting Escape key press

# Function to generate a sine wave of a given frequency and duration
def generate_sine_wave(frequency=440, duration=2, samplerate=44100):
    t = np.linspace(0, duration, int(samplerate * duration), endpoint=False)
    return 0.5 * np.sin(2 * np.pi * frequency * t)

def test_audio_devices():
    devices = sd.query_devices()
    print("Available audio devices:")

    for i, device in enumerate(devices):
        print(f"Testing (device index: {i}), (device name: {device['name']})")
        
        # Get device info
        device_info = sd.query_devices(i)
        sample_rate = device_info['default_samplerate']
        output_channels = device_info['max_output_channels']
        input_channels = device_info['max_input_channels']
        
        # Print the sample rate and number of channels
        print(f"  Sample rate: {sample_rate}")
        print(f"  Output channels: {output_channels}")
        print(f"  Input channels: {input_channels}")
        
        # Generate the sine wave
        sine_wave = generate_sine_wave(frequency=440, duration=2)
        
        try:
            # Play the sine wave on the current device with the correct sample rate
            sd.play(sine_wave, samplerate=int(sample_rate), device=i)
            sd.wait()  # Wait until sound has finished playing
        except Exception as e:
            print(f"Error with device {i} ({device['name']}): {e}")

# List and test the available audio devices
test_audio_devices()
