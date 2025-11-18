"""
DeviceManager class for DyadicSync Framework.

Manages all hardware devices (displays, audio, input).
"""

from typing import List, Dict, Any, Optional
import pyglet
import sounddevice as sd
import numpy as np
from .device_scanner import DeviceScanner, DisplayInfo, AudioDeviceInfo


class DeviceManager:
    """
    Manages all hardware devices (displays, audio, input).

    Responsibilities:
    - Enumerate available devices
    - Validate device configuration
    - Create players with correct device routing
    - Manage multi-display setup
    - Create and manage Pyglet windows
    """

    def __init__(self):
        """Initialize device manager."""
        self.displays: List[DisplayInfo] = []
        self.audio_devices: List[AudioDeviceInfo] = []

        # Configuration (set via config file or GUI)
        self.display_p1: int = 1
        self.display_p2: int = 2
        self.audio_device_p1: int = 9
        self.audio_device_p2: int = 7

        # Windows (created during initialization)
        self.window1: Optional[pyglet.window.Window] = None
        self.window2: Optional[pyglet.window.Window] = None

        # Scanner instance
        self._scanner = DeviceScanner()

    def configure(self, config: Dict[str, Any]):
        """
        Configure device indices from configuration dictionary.

        Args:
            config: Dictionary with device configuration
                   Expected keys: 'display_p1', 'display_p2', 'audio_device_p1', 'audio_device_p2'
        """
        self.display_p1 = config.get('display_p1', self.display_p1)
        self.display_p2 = config.get('display_p2', self.display_p2)
        self.audio_device_p1 = config.get('audio_device_p1', self.audio_device_p1)
        self.audio_device_p2 = config.get('audio_device_p2', self.audio_device_p2)

    def initialize(self):
        """
        Initialize devices and create windows.

        This must be called before execute() is run on any phases.
        """
        # Enumerate devices
        self.displays = self._scanner.scan_displays()
        self.audio_devices = self._scanner.scan_audio_devices()['all']  # Extract 'all' devices list from dict

        # Validate configuration
        errors = self.validate()
        if errors:
            raise RuntimeError(f"Device validation failed: {'; '.join(errors)}")

        # Get Pyglet screens
        display = pyglet.display.get_display()
        screens = display.get_screens()

        print(f"[DeviceManager] Found {len(screens)} screens")
        for i, screen in enumerate(screens):
            print(f"[DeviceManager]   Screen {i}: {screen.width}x{screen.height}")

        # Create fullscreen windows for both participants
        # Note: set_exclusive_keyboard(False) is critical for multi-window setups
        # to prevent OpenGL context conflicts on Windows
        try:
            print(f"[DeviceManager] Creating window 1 on screen {self.display_p1}...")
            self.window1 = pyglet.window.Window(
                fullscreen=True,
                screen=screens[self.display_p1]
            )
            # Disable exclusive keyboard - required for multi-window Pyglet on Windows
            # Prevents wglChoosePixelFormatARB errors
            self.window1.set_exclusive_keyboard(False)
            print(f"[DeviceManager] Window 1 created successfully")

            print(f"[DeviceManager] Creating window 2 on screen {self.display_p2}...")
            self.window2 = pyglet.window.Window(
                fullscreen=True,
                screen=screens[self.display_p2]
            )
            # Disable exclusive keyboard on second window
            self.window2.set_exclusive_keyboard(False)
            print(f"[DeviceManager] Window 2 created successfully")

            print(f"[DeviceManager] Both windows created successfully on displays {self.display_p1} and {self.display_p2}")

        except Exception as e:
            print(f"[DeviceManager] ERROR creating fullscreen windows: {e}")
            print(f"[DeviceManager] Attempting fallback to windowed mode...")

            try:
                # Fallback: Create large windowed mode instead of fullscreen
                self.window1 = pyglet.window.Window(
                    width=screens[self.display_p1].width,
                    height=screens[self.display_p1].height,
                    screen=screens[self.display_p1]
                )
                self.window1.set_exclusive_keyboard(False)

                self.window2 = pyglet.window.Window(
                    width=screens[self.display_p2].width,
                    height=screens[self.display_p2].height,
                    screen=screens[self.display_p2]
                )
                self.window2.set_exclusive_keyboard(False)

                print(f"[DeviceManager] Created windowed mode windows successfully")

            except Exception as e2:
                raise RuntimeError(
                    f"Failed to create Pyglet windows: {e}\n\n"
                    f"Windowed fallback also failed: {e2}\n\n"
                    f"This may indicate:\n"
                    f"1. Pyglet version incompatibility (try: pip install pyglet==1.5.29)\n"
                    f"2. Graphics driver issues\n"
                    f"3. Invalid display indices (check Device Setup)\n\n"
                    f"Please verify:\n"
                    f"- All monitors are connected and detected\n"
                    f"- Graphics drivers are up to date\n"
                    f"- Pyglet version is compatible"
                )

    def cleanup(self):
        """Close windows and release devices."""
        if self.window1:
            self.window1.close()
            self.window1 = None

        if self.window2:
            self.window2.close()
            self.window2 = None

        # Stop any audio playback
        sd.stop()

        print("[DeviceManager] Cleanup complete")

    def create_video_player(self, video_path: str, display_id: int, audio_device_id: int):
        """
        Factory method to create configured video player.

        Args:
            video_path: Path to video file
            display_id: 0 for P1, 1 for P2
            audio_device_id: Audio output device index

        Returns:
            SynchronizedPlayer instance
        """
        # Import here to avoid circular dependency
        # SynchronizedPlayer will be in playback/ module
        from playback.synchronized_player import SynchronizedPlayer

        window = self.window1 if display_id == 0 else self.window2
        return SynchronizedPlayer(video_path, audio_device_id, window)

    def validate(self) -> List[str]:
        """
        Validate device configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Ensure devices are scanned before validation (defensive check)
        if not self.displays:
            print("[DeviceManager] Auto-scanning displays for validation...")
            self.displays = self._scanner.scan_displays()
        if not self.audio_devices:
            print("[DeviceManager] Auto-scanning audio devices for validation...")
            audio_result = self._scanner.scan_audio_devices()
            self.audio_devices = audio_result['all']

        # Check displays exist
        num_displays = len(self.displays)
        if self.display_p1 >= num_displays:
            errors.append(f"Display {self.display_p1} not found (only {num_displays} displays available)")
        if self.display_p2 >= num_displays:
            errors.append(f"Display {self.display_p2} not found (only {num_displays} displays available)")

        # Check audio devices exist (search by device index, not list position)
        audio_device_indices = [dev.index for dev in self.audio_devices]
        if self.audio_device_p1 not in audio_device_indices:
            errors.append(f"Audio device {self.audio_device_p1} not found (available: {audio_device_indices})")
        if self.audio_device_p2 not in audio_device_indices:
            errors.append(f"Audio device {self.audio_device_p2} not found (available: {audio_device_indices})")

        return errors

    def test_audio_device(self, device_id: int, duration: float = 1.0, frequency: float = 440.0):
        """
        Play test tone on specified device.

        Args:
            device_id: Audio device index
            duration: Test tone duration in seconds
            frequency: Test tone frequency in Hz (default 440Hz = A4)
        """
        # Generate sine wave test tone
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = 0.5 * np.sin(2 * np.pi * frequency * t)

        # Play on specified device
        print(f"[DeviceManager] Playing test tone on audio device {device_id}")
        sd.play(tone, sample_rate, device=device_id)
        sd.wait()
        print(f"[DeviceManager] Test tone complete")

    def get_display_info(self, display_id: int) -> Optional[DisplayInfo]:
        """
        Get information about a display.

        Args:
            display_id: Display index

        Returns:
            DisplayInfo object or None if not found
        """
        if display_id < len(self.displays):
            return self.displays[display_id]
        return None

    def get_audio_device_info(self, device_id: int) -> Optional[AudioDeviceInfo]:
        """
        Get information about an audio device.

        Args:
            device_id: Audio device index (sounddevice index, not list position)

        Returns:
            AudioDeviceInfo object or None if not found
        """
        # Search for device by its index attribute
        for device in self.audio_devices:
            if device.index == device_id:
                return device
        return None

    def enumerate_devices(self) -> Dict[str, Any]:
        """
        Get current device enumeration.

        Returns:
            Dictionary with 'displays' and 'audio_devices' lists
        """
        return {
            'displays': self.displays,
            'audio_devices': self.audio_devices
        }

    def get_config(self) -> Dict[str, Any]:
        """
        Get current device configuration.

        Returns:
            Dictionary with device indices
        """
        return {
            'display_p1': self.display_p1,
            'display_p2': self.display_p2,
            'audio_device_p1': self.audio_device_p1,
            'audio_device_p2': self.audio_device_p2
        }

    def __repr__(self):
        return (
            f"DeviceManager("
            f"displays={len(self.displays)}, "
            f"audio_devices={len(self.audio_devices)}, "
            f"display_p1={self.display_p1}, "
            f"display_p2={self.display_p2}, "
            f"audio_p1={self.audio_device_p1}, "
            f"audio_p2={self.audio_device_p2})"
        )
