"""
DeviceManager class for DyadicSync Framework.

Manages all hardware devices (displays, audio, input).
"""

from typing import List, Dict, Any, Optional
import logging
import pyglet
import sounddevice as sd
import numpy as np
from .device_scanner import DeviceScanner, DisplayInfo, AudioDeviceInfo

logger = logging.getLogger(__name__)


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

        # Windowed debug mode (small windows on control monitor instead of fullscreen)
        self.windowed_mode: bool = False

        # Keyboard routing (optional)
        self.keyboard_device_p1: Optional[str] = None  # Device path string
        self.keyboard_device_p2: Optional[str] = None  # Device path string
        self.intercept_keyboards: bool = False  # Block participant keyboards from other apps
        self.keyboard_router = None  # KeyboardRouter instance (created in initialize())

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

        # Keyboard device paths (optional)
        if config.get('keyboard_device_p1'):
            self.keyboard_device_p1 = config['keyboard_device_p1']
        if config.get('keyboard_device_p2'):
            self.keyboard_device_p2 = config['keyboard_device_p2']
        self.intercept_keyboards = config.get('intercept_keyboards', False)

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

        # Windowed debug mode: small side-by-side windows on screen 0
        if self.windowed_mode:
            print(f"[DeviceManager] WINDOWED MODE: Creating debug windows on screen 0")

            debug_width = 800
            debug_height = 600

            self.window1 = pyglet.window.Window(
                width=debug_width, height=debug_height,
                caption="P1 Preview", screen=screens[0]
            )
            self.window1.set_exclusive_keyboard(False)
            self.window1.set_location(screens[0].x + 50, screens[0].y + 100)

            self.window2 = pyglet.window.Window(
                width=debug_width, height=debug_height,
                caption="P2 Preview", screen=screens[0]
            )
            self.window2.set_exclusive_keyboard(False)
            self.window2.set_location(screens[0].x + 50 + debug_width + 20, screens[0].y + 100)

            print(f"[DeviceManager] Debug windows created: {debug_width}x{debug_height} side-by-side")
            self._initialize_keyboard_router()
            return

        # Create borderless fullscreen windows for both participants
        # Uses borderless windowed mode instead of exclusive fullscreen so that
        # focus changes on the control monitor (e.g. taskbar previews) don't
        # cause participant windows to minimize.
        try:
            screen_p1 = screens[self.display_p1]
            screen_p2 = screens[self.display_p2]

            print(f"[DeviceManager] Creating window 1 on screen {self.display_p1}...")
            self.window1 = pyglet.window.Window(
                width=screen_p1.width, height=screen_p1.height,
                style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
                screen=screen_p1
            )
            self.window1.set_location(screen_p1.x, screen_p1.y)
            self.window1.set_exclusive_keyboard(False)
            print(f"[DeviceManager] Window 1 created successfully")

            print(f"[DeviceManager] Creating window 2 on screen {self.display_p2}...")
            self.window2 = pyglet.window.Window(
                width=screen_p2.width, height=screen_p2.height,
                style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
                screen=screen_p2
            )
            self.window2.set_location(screen_p2.x, screen_p2.y)
            self.window2.set_exclusive_keyboard(False)
            print(f"[DeviceManager] Window 2 created successfully")

            self._exclude_from_peek(self.window1)
            self._exclude_from_peek(self.window2)
            print(f"[DeviceManager] Both windows created successfully on displays {self.display_p1} and {self.display_p2}")
            self._initialize_keyboard_router()

        except Exception as e:
            print(f"[DeviceManager] ERROR creating fullscreen windows: {e}")
            print(f"[DeviceManager] Attempting fallback to windowed mode...")

            try:
                # Fallback: borderless windowed mode
                screen_p1 = screens[self.display_p1]
                screen_p2 = screens[self.display_p2]

                self.window1 = pyglet.window.Window(
                    width=screen_p1.width, height=screen_p1.height,
                    style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
                    screen=screen_p1
                )
                self.window1.set_location(screen_p1.x, screen_p1.y)
                self.window1.set_exclusive_keyboard(False)

                self.window2 = pyglet.window.Window(
                    width=screen_p2.width, height=screen_p2.height,
                    style=pyglet.window.Window.WINDOW_STYLE_BORDERLESS,
                    screen=screen_p2
                )
                self.window2.set_location(screen_p2.x, screen_p2.y)
                self.window2.set_exclusive_keyboard(False)

                self._exclude_from_peek(self.window1)
                self._exclude_from_peek(self.window2)
                print(f"[DeviceManager] Created windowed mode windows successfully")
                self._initialize_keyboard_router()

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

    @staticmethod
    def _exclude_from_peek(window):
        """Exclude a window from Windows Aero Peek so it stays visible
        when taskbar thumbnails are previewed on the control monitor."""
        try:
            import ctypes
            from ctypes import wintypes
            dwm = ctypes.windll.dwmapi
            DWMWA_EXCLUDED_FROM_PEEK = 12
            hwnd = window._hwnd  # Pyglet exposes the native handle
            val = ctypes.c_int(1)
            dwm.DwmSetWindowAttribute(hwnd, DWMWA_EXCLUDED_FROM_PEEK,
                                      ctypes.byref(val), ctypes.sizeof(val))
        except Exception as e:
            print(f"[DeviceManager] Could not exclude window from Aero Peek: {e}")

    def _initialize_keyboard_router(self):
        """Initialize keyboard router if both device paths are configured."""
        if self.keyboard_device_p1 and self.keyboard_device_p2:
            try:
                from .input.keyboard_router import KeyboardRouter
                self.keyboard_router = KeyboardRouter(
                    p1_device_path=self.keyboard_device_p1,
                    p2_device_path=self.keyboard_device_p2,
                    intercept=self.intercept_keyboards,
                )
                self.keyboard_router.start()
                print(f"[DeviceManager] Keyboard router started (per-keyboard input routing enabled)")
            except Exception as e:
                logger.warning(f"Failed to start keyboard router: {e}")
                print(f"[DeviceManager] WARNING: Keyboard router failed to start: {e}")
                print(f"[DeviceManager] WARNING: Falling back to separate key bindings")
                self.keyboard_router = None
        else:
            if self.keyboard_device_p1 or self.keyboard_device_p2:
                print(f"[DeviceManager] WARNING: Only one keyboard configured - both required for routing")
            self.keyboard_router = None

    def cleanup(self):
        """Close windows and release devices."""
        # Stop keyboard router first
        if self.keyboard_router:
            self.keyboard_router.stop()
            self.keyboard_router = None

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

        # In windowed mode, skip display validation (both windows go on screen 0)
        if not self.windowed_mode:
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
        config = {
            'display_p1': self.display_p1,
            'display_p2': self.display_p2,
            'audio_device_p1': self.audio_device_p1,
            'audio_device_p2': self.audio_device_p2
        }
        if self.keyboard_device_p1:
            config['keyboard_device_p1'] = self.keyboard_device_p1
        if self.keyboard_device_p2:
            config['keyboard_device_p2'] = self.keyboard_device_p2
        return config

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
