"""
Keyboard Identifier - "Press any key" identification flow.

Used by the Device Setup dialog to identify which physical keyboard
belongs to which participant. Creates a temporary RawInputListener,
waits for a keypress, and returns device info.
"""

import threading
import logging
from dataclasses import dataclass
from typing import Optional
from .raw_input import RawInputListener

logger = logging.getLogger(__name__)


@dataclass
class KeyboardDeviceInfo:
    """Information about an identified keyboard device."""
    device_path: str    # Stable Win32 device path (e.g., '\\\\?\\HID#VID_046D&PID_C52B...')
    device_name: str    # Human-readable name (e.g., 'Keyboard (VID:046D PID:C52B)')

    @property
    def vendor_id(self) -> Optional[str]:
        """Extract vendor ID from device path."""
        path_upper = self.device_path.upper()
        if 'VID_' in path_upper:
            try:
                start = path_upper.index('VID_') + 4
                return path_upper[start:start + 4]
            except (ValueError, IndexError):
                pass
        return None

    @property
    def product_id(self) -> Optional[str]:
        """Extract product ID from device path."""
        path_upper = self.device_path.upper()
        if 'PID_' in path_upper:
            try:
                start = path_upper.index('PID_') + 4
                return path_upper[start:start + 4]
            except (ValueError, IndexError):
                pass
        return None


class KeyboardIdentifier:
    """
    Identifies a keyboard by waiting for a keypress on any connected keyboard.

    Usage:
        identifier = KeyboardIdentifier()
        identifier.start_listening()
        info = identifier.wait_for_keypress(timeout=10)
        identifier.stop_listening()

        if info:
            print(f"Detected: {info.device_name} at {info.device_path}")
    """

    def __init__(self):
        self._listener: Optional[RawInputListener] = None
        self._result: Optional[KeyboardDeviceInfo] = None
        self._event = threading.Event()

    def start_listening(self):
        """Start a temporary raw input listener."""
        self._result = None
        self._event.clear()
        self._listener = RawInputListener(on_key_event=self._on_key_event)
        self._listener.start()
        logger.info("KeyboardIdentifier: Listening for keypress...")

    def wait_for_keypress(self, timeout: float = 10.0) -> Optional[KeyboardDeviceInfo]:
        """
        Block until a key is pressed on any keyboard.

        Args:
            timeout: Maximum seconds to wait. Default 10.

        Returns:
            KeyboardDeviceInfo for the keyboard that was pressed, or None on timeout.
        """
        self._event.wait(timeout=timeout)
        return self._result

    def poll_result(self) -> Optional[KeyboardDeviceInfo]:
        """
        Non-blocking check for a keypress result.

        Returns:
            KeyboardDeviceInfo if a key was pressed, None otherwise.
        """
        if self._event.is_set():
            return self._result
        return None

    def stop_listening(self):
        """Stop the temporary listener and clean up."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        logger.info("KeyboardIdentifier: Stopped listening")

    def _on_key_event(self, device_handle: int, vk_code: int, is_key_down: bool):
        """Callback from RawInputListener."""
        # Only respond to key-down events and only the first one
        if not is_key_down or self._event.is_set():
            return

        if not self._listener:
            return

        # Get device info
        device_path = self._listener.get_device_path(device_handle)
        if not device_path:
            logger.warning(f"KeyboardIdentifier: Could not get device path for handle {device_handle}")
            return

        device_name = self._listener.get_device_name(device_handle)
        if not device_name:
            device_name = "Unknown Keyboard"

        self._result = KeyboardDeviceInfo(
            device_path=device_path,
            device_name=device_name
        )
        self._event.set()
        logger.info(f"KeyboardIdentifier: Detected {device_name} ({device_path[:50]}...)")
