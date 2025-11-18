"""
Device Scanner Module
Scans available displays, audio input devices, and audio output devices
for the DyadicSync experiment system.

Author: DyadicSync Development Team
Date: 2025-11-15
"""

import platform
import numpy as np
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import sounddevice as sd

# Import pyglet for display enumeration
try:
    import pyglet
    PYGLET_AVAILABLE = True
except ImportError:
    PYGLET_AVAILABLE = False
    print("Warning: pyglet not available. Display scanning disabled.")


@dataclass
class DisplayInfo:
    """Information about a display/monitor"""
    index: int
    name: str
    width: int
    height: int
    x: int
    y: int
    is_primary: bool

    def __str__(self):
        primary_str = " (Primary)" if self.is_primary else ""
        return f"Display {self.index}: {self.name} - {self.width}x{self.height}{primary_str}"

    def to_dict(self):
        return {
            'index': self.index,
            'name': self.name,
            'width': self.width,
            'height': self.height,
            'x': self.x,
            'y': self.y,
            'is_primary': self.is_primary
        }


@dataclass
class AudioDeviceInfo:
    """Information about an audio device"""
    index: int
    name: str
    max_input_channels: int
    max_output_channels: int
    default_samplerate: float
    is_input: bool
    is_output: bool
    is_default_input: bool
    is_default_output: bool
    hostapi: str

    def __str__(self):
        device_type = []
        if self.is_input:
            device_type.append("Input")
        if self.is_output:
            device_type.append("Output")
        type_str = "/".join(device_type)

        default_str = ""
        if self.is_default_input:
            default_str = " [Default Input]"
        elif self.is_default_output:
            default_str = " [Default Output]"

        return f"{self.index}: {self.name} ({type_str}){default_str}"

    def to_dict(self):
        return {
            'index': self.index,
            'name': self.name,
            'max_input_channels': self.max_input_channels,
            'max_output_channels': self.max_output_channels,
            'default_samplerate': self.default_samplerate,
            'is_input': self.is_input,
            'is_output': self.is_output,
            'is_default_input': self.is_default_input,
            'is_default_output': self.is_default_output,
            'hostapi': self.hostapi
        }


class DeviceScanner:
    """
    Scans and manages information about available system devices:
    - Displays/Monitors
    - Audio input devices (microphones)
    - Audio output devices (speakers/headphones)
    """

    def __init__(self):
        self.platform = platform.system()
        self._displays_cache = None
        self._audio_devices_cache = None

    def scan_displays(self, force_refresh: bool = False) -> List[DisplayInfo]:
        """
        Scan available displays/monitors using pyglet.

        Args:
            force_refresh: Force re-scan even if cache exists

        Returns:
            List of DisplayInfo objects
        """
        if not PYGLET_AVAILABLE:
            print("Error: pyglet not available for display scanning")
            return []

        if self._displays_cache is not None and not force_refresh:
            return self._displays_cache

        try:
            display = pyglet.display.get_display()
            screens = display.get_screens()

            displays = []
            for idx, screen in enumerate(screens):
                # Determine if this is the primary display
                # Typically screen at index 0 is primary, but check position
                is_primary = (idx == 0)

                display_info = DisplayInfo(
                    index=idx,
                    name=f"Display {idx + 1}",
                    width=screen.width,
                    height=screen.height,
                    x=screen.x,
                    y=screen.y,
                    is_primary=is_primary
                )
                displays.append(display_info)

            self._displays_cache = displays
            return displays

        except Exception as e:
            print(f"Error scanning displays: {e}")
            return []

    def scan_audio_devices(self, force_refresh: bool = False) -> Dict[str, List[AudioDeviceInfo]]:
        """
        Scan available audio devices using sounddevice.

        Args:
            force_refresh: Force re-scan even if cache exists

        Returns:
            Dictionary with 'input', 'output', and 'all' lists of AudioDeviceInfo
        """
        if self._audio_devices_cache is not None and not force_refresh:
            return self._audio_devices_cache

        try:
            devices = sd.query_devices()
            default_input = sd.default.device[0]
            default_output = sd.default.device[1]

            input_devices = []
            output_devices = []
            all_devices = []

            for idx, device in enumerate(devices):
                # Get host API name
                hostapi_info = sd.query_hostapis(device['hostapi'])
                hostapi_name = hostapi_info['name']

                is_input = device['max_input_channels'] > 0
                is_output = device['max_output_channels'] > 0

                device_info = AudioDeviceInfo(
                    index=idx,
                    name=device['name'],
                    max_input_channels=device['max_input_channels'],
                    max_output_channels=device['max_output_channels'],
                    default_samplerate=device['default_samplerate'],
                    is_input=is_input,
                    is_output=is_output,
                    is_default_input=(idx == default_input),
                    is_default_output=(idx == default_output),
                    hostapi=hostapi_name
                )

                all_devices.append(device_info)
                if is_input:
                    input_devices.append(device_info)
                if is_output:
                    output_devices.append(device_info)

            result = {
                'input': input_devices,
                'output': output_devices,
                'all': all_devices
            }

            self._audio_devices_cache = result
            return result

        except Exception as e:
            print(f"Error scanning audio devices: {e}")
            return {'input': [], 'output': [], 'all': []}

    def get_display_by_index(self, index: int) -> Optional[DisplayInfo]:
        """Get display info by index"""
        displays = self.scan_displays()
        for display in displays:
            if display.index == index:
                return display
        return None

    def get_audio_device_by_index(self, index: int) -> Optional[AudioDeviceInfo]:
        """Get audio device info by index"""
        devices = self.scan_audio_devices()
        for device in devices['all']:
            if device.index == index:
                return device
        return None

    def test_audio_output(self, device_index: int, duration: float = 1.0,
                         frequency: float = 440.0) -> Tuple[bool, str]:
        """
        Test an audio output device by playing a sine wave tone.

        Args:
            device_index: Index of audio device to test
            duration: Duration of test tone in seconds
            frequency: Frequency of test tone in Hz

        Returns:
            Tuple of (success: bool, message: str)
        """
        try:
            device = self.get_audio_device_by_index(device_index)
            if device is None:
                return False, f"Device index {device_index} not found"

            if not device.is_output:
                return False, f"Device '{device.name}' is not an output device"

            # Generate sine wave
            samplerate = int(device.default_samplerate)
            t = np.linspace(0, duration, int(samplerate * duration))
            tone = 0.3 * np.sin(2 * np.pi * frequency * t)

            # Play on specific device
            sd.play(tone, samplerate, device=device_index)
            sd.wait()

            return True, f"Successfully tested {device.name}"

        except Exception as e:
            return False, f"Error testing device: {str(e)}"

    def test_audio_input(self, device_index: int, duration: float = 2.0) -> Tuple[bool, str, Optional[float]]:
        """
        Test an audio input device by recording and analyzing signal.

        Args:
            device_index: Index of audio device to test
            duration: Duration of test recording in seconds

        Returns:
            Tuple of (success: bool, message: str, rms_level: Optional[float])
        """
        try:
            device = self.get_audio_device_by_index(device_index)
            if device is None:
                return False, f"Device index {device_index} not found", None

            if not device.is_input:
                return False, f"Device '{device.name}' is not an input device", None

            # Record audio
            samplerate = int(device.default_samplerate)
            recording = sd.rec(
                int(duration * samplerate),
                samplerate=samplerate,
                channels=1,
                device=device_index
            )
            sd.wait()

            # Calculate RMS level
            rms = np.sqrt(np.mean(recording**2))

            if rms < 0.001:
                message = f"Tested {device.name} - Very low signal (check mic)"
            elif rms < 0.01:
                message = f"Tested {device.name} - Low signal"
            else:
                message = f"Tested {device.name} - Good signal"

            return True, message, float(rms)

        except Exception as e:
            return False, f"Error testing device: {str(e)}", None

    def validate_display_config(self, display_indices: List[int]) -> Tuple[bool, str]:
        """
        Validate that specified display indices are available and unique.

        Args:
            display_indices: List of display indices to validate

        Returns:
            Tuple of (valid: bool, message: str)
        """
        displays = self.scan_displays()
        available_indices = [d.index for d in displays]

        for idx in display_indices:
            if idx not in available_indices:
                return False, f"Display index {idx} not found (available: {available_indices})"

        if len(display_indices) != len(set(display_indices)):
            return False, "Duplicate display indices specified"

        return True, "Display configuration valid"

    def validate_audio_config(self, device_indices: List[int],
                            device_type: str = 'output') -> Tuple[bool, str]:
        """
        Validate that specified audio device indices are available and of correct type.

        Args:
            device_indices: List of audio device indices to validate
            device_type: 'input' or 'output'

        Returns:
            Tuple of (valid: bool, message: str)
        """
        devices = self.scan_audio_devices()

        if device_type == 'input':
            valid_devices = devices['input']
        elif device_type == 'output':
            valid_devices = devices['output']
        else:
            return False, f"Invalid device type: {device_type}"

        valid_indices = [d.index for d in valid_devices]

        for idx in device_indices:
            if idx not in valid_indices:
                return False, f"Audio {device_type} device index {idx} not found"

        # Note: We allow duplicate audio devices (same headphones for both participants, etc.)

        return True, f"Audio {device_type} configuration valid"

    def get_display_count(self) -> int:
        """Get number of available displays"""
        return len(self.scan_displays())

    def get_audio_input_count(self) -> int:
        """Get number of available input devices"""
        return len(self.scan_audio_devices()['input'])

    def get_audio_output_count(self) -> int:
        """Get number of available output devices"""
        return len(self.scan_audio_devices()['output'])

    def print_all_devices(self):
        """Print all available devices (for debugging)"""
        print("\n" + "="*60)
        print("AVAILABLE DISPLAYS")
        print("="*60)
        displays = self.scan_displays()
        if displays:
            for display in displays:
                print(f"  {display}")
        else:
            print("  No displays found")

        print("\n" + "="*60)
        print("AVAILABLE AUDIO OUTPUT DEVICES")
        print("="*60)
        audio_devices = self.scan_audio_devices()
        if audio_devices['output']:
            for device in audio_devices['output']:
                print(f"  {device}")
        else:
            print("  No output devices found")

        print("\n" + "="*60)
        print("AVAILABLE AUDIO INPUT DEVICES")
        print("="*60)
        if audio_devices['input']:
            for device in audio_devices['input']:
                print(f"  {device}")
        else:
            print("  No input devices found")
        print("="*60 + "\n")


def main():
    """Test the device scanner"""
    scanner = DeviceScanner()
    scanner.print_all_devices()

    # Test audio output if any available
    audio_devices = scanner.scan_audio_devices()
    if audio_devices['output']:
        print("\nTesting first audio output device...")
        first_output = audio_devices['output'][0]
        success, message = scanner.test_audio_output(first_output.index, duration=0.5)
        print(f"  {message}")


if __name__ == "__main__":
    main()
