"""
Keyboard Router - maps raw input device handles to participant IDs.

Routes key events from physical keyboards to the correct participant
based on device path matching. Uses RawInputListener for device
identification, and optionally InterceptionListener for keyboard
isolation (blocking participant input from other apps).
"""

import threading
import logging
from typing import Optional, Callable, List, Dict
from .raw_input import RawInputListener

logger = logging.getLogger(__name__)

# VK code -> pyglet key constant mapping
# Lazily imported to avoid pyglet import at module level
_VK_TO_PYGLET: Optional[Dict[int, int]] = None


def _build_vk_map() -> Dict[int, int]:
    """Build Win32 VK code -> pyglet key constant mapping."""
    from pyglet.window import key

    vk_map = {}

    # Digits 0-9 (VK_0 = 0x30 .. VK_9 = 0x39)
    for i in range(10):
        vk = 0x30 + i
        pyglet_key = getattr(key, f'_{i}', None)
        if pyglet_key is not None:
            vk_map[vk] = pyglet_key

    # Letters A-Z (VK_A = 0x41 .. VK_Z = 0x5A)
    for i in range(26):
        vk = 0x41 + i
        letter = chr(ord('A') + i)
        pyglet_key = getattr(key, letter, None)
        if pyglet_key is not None:
            vk_map[vk] = pyglet_key

    # Special keys
    special = {
        0x0D: key.RETURN,   # VK_RETURN
        0x20: key.SPACE,    # VK_SPACE
        0x1B: key.ESCAPE,   # VK_ESCAPE
        0x09: key.TAB,      # VK_TAB
        0x08: key.BACKSPACE,  # VK_BACK
        0x25: key.LEFT,     # VK_LEFT
        0x26: key.UP,       # VK_UP
        0x27: key.RIGHT,    # VK_RIGHT
        0x28: key.DOWN,     # VK_DOWN
    }
    vk_map.update(special)

    # Numpad 0-9 (VK_NUMPAD0 = 0x60 .. VK_NUMPAD9 = 0x69)
    for i in range(10):
        vk = 0x60 + i
        pyglet_key = getattr(key, f'NUM_{i}', None)
        if pyglet_key is not None:
            vk_map[vk] = pyglet_key

    return vk_map


def _vk_to_pyglet_key(vk_code: int) -> Optional[int]:
    """Convert a Win32 VK code to a pyglet key constant."""
    global _VK_TO_PYGLET
    if _VK_TO_PYGLET is None:
        _VK_TO_PYGLET = _build_vk_map()
    return _VK_TO_PYGLET.get(vk_code)


def _extract_vid_pid(path: str):
    """Extract (VID, PID) tuple from a device path or hardware ID string."""
    path_upper = path.upper()
    vid = pid = None
    if 'VID_' in path_upper:
        try:
            start = path_upper.index('VID_') + 4
            vid = path_upper[start:start + 4]
        except (ValueError, IndexError):
            pass
    if 'PID_' in path_upper:
        try:
            start = path_upper.index('PID_') + 4
            pid = path_upper[start:start + 4]
        except (ValueError, IndexError):
            pass
    if vid and pid:
        return (vid, pid)
    return None


# Handler callback type: (participant_id: int, pyglet_key: int, is_key_down: bool)
RoutedKeyHandler = Callable[[int, int, bool], None]


class KeyboardRouter:
    """
    Routes keyboard events to participants based on physical device identity.

    Given two device paths (one per participant), listens for raw input
    and dispatches key events with participant IDs to registered handlers.

    Optionally intercepts participant keyboard input so it doesn't reach
    other applications on the control monitor.
    """

    def __init__(self, p1_device_path: str, p2_device_path: str,
                 intercept: bool = False):
        """
        Args:
            p1_device_path: Win32 device path for Participant 1's keyboard.
            p2_device_path: Win32 device path for Participant 2's keyboard.
            intercept: If True, block participant keyboard input from reaching
                other applications. Control keyboard input is unaffected.
        """
        self._p1_path = p1_device_path
        self._p2_path = p2_device_path
        self._intercept = intercept
        self._using_interception = False

        self._listener = None  # RawInputListener or InterceptionListener
        self._handlers: List[RoutedKeyHandler] = []
        self._handlers_lock = threading.Lock()

        # Cache: device_handle -> device_path (avoids repeated API calls)
        self._handle_to_path: Dict[int, str] = {}
        # Cache: device_handle -> participant_id (1, 2, or 0 for unknown)
        self._handle_to_participant: Dict[int, int] = {}

    def start(self):
        """Start listening for raw keyboard input and routing events."""
        if self._intercept:
            # Try Interception driver for kernel-level keyboard isolation
            try:
                from .interception_listener import InterceptionListener
                self._listener = InterceptionListener(
                    on_key_event=self._on_raw_key,
                    intercept_device_paths={self._p1_path, self._p2_path},
                )
                self._listener.start()
                self._using_interception = True
                logger.info("KeyboardRouter: Using Interception driver for keyboard isolation")
                print("[KeyboardRouter] Keyboard isolation active (Interception driver)")
            except ImportError as e:
                logger.warning(f"KeyboardRouter: Interception driver not available: {e}")
                print(f"[KeyboardRouter] WARNING: Interception driver not available ({e})")
                print("[KeyboardRouter] WARNING: Falling back to Raw Input (no keyboard isolation)")
                self._intercept = False
                # Fall through to RawInputListener
            except Exception as e:
                logger.warning(f"KeyboardRouter: Interception driver failed: {e}")
                print(f"[KeyboardRouter] WARNING: Interception driver failed: {e}")
                print("[KeyboardRouter] WARNING: Falling back to Raw Input (no keyboard isolation)")
                self._intercept = False
                # Fall through to RawInputListener

        if not self._intercept:
            self._listener = RawInputListener(on_key_event=self._on_raw_key)
            self._listener.start()
            self._using_interception = False
            logger.info("KeyboardRouter: Using Raw Input (no keyboard isolation)")

        logger.info(f"KeyboardRouter: Started (P1={self._p1_path[:40]}..., P2={self._p2_path[:40]}...)")

    def stop(self):
        """Stop listening and clean up."""
        if self._listener:
            self._listener.stop()
            self._listener = None

        with self._handlers_lock:
            self._handlers.clear()

        self._handle_to_path.clear()
        self._handle_to_participant.clear()
        logger.info("KeyboardRouter: Stopped")

    def register_handler(self, handler: RoutedKeyHandler):
        """Register a handler to receive routed key events."""
        with self._handlers_lock:
            if handler not in self._handlers:
                self._handlers.append(handler)

    def unregister_handler(self, handler: RoutedKeyHandler):
        """Unregister a previously registered handler."""
        with self._handlers_lock:
            try:
                self._handlers.remove(handler)
            except ValueError:
                pass

    def _on_raw_key(self, device_handle: int, vk_code: int, is_key_down: bool):
        """Callback from RawInputListener - route to participant."""
        # Resolve participant from device handle (cached)
        participant_id = self._resolve_participant(device_handle)

        if participant_id == 0:
            # Unknown device - ignore
            return

        # Convert VK code to pyglet key constant
        pyglet_key = _vk_to_pyglet_key(vk_code)
        if pyglet_key is None:
            return

        # Dispatch to all registered handlers
        with self._handlers_lock:
            handlers = list(self._handlers)

        for handler in handlers:
            try:
                handler(participant_id, pyglet_key, is_key_down)
            except Exception as e:
                logger.error(f"KeyboardRouter: Handler error: {e}", exc_info=True)

    def _resolve_participant(self, device_handle: int) -> int:
        """
        Resolve device handle to participant ID (1 or 2), with caching.

        Supports both exact path matching (Raw Input) and VID/PID matching
        (Interception driver, which uses different path formats).

        Returns:
            1 for P1, 2 for P2, 0 for unknown device.
        """
        # Check cache first
        if device_handle in self._handle_to_participant:
            return self._handle_to_participant[device_handle]

        # Get device path from handle
        if device_handle not in self._handle_to_path:
            if self._listener:
                path = self._listener.get_device_path(device_handle)
                if path:
                    self._handle_to_path[device_handle] = path
                else:
                    self._handle_to_participant[device_handle] = 0
                    return 0
            else:
                return 0

        path = self._handle_to_path[device_handle]

        # Try exact path match first (case-insensitive)
        path_lower = path.lower()
        p1_lower = self._p1_path.lower()
        p2_lower = self._p2_path.lower()

        if path_lower == p1_lower:
            self._handle_to_participant[device_handle] = 1
            logger.debug(f"KeyboardRouter: Handle {device_handle} -> P1 (exact match)")
            return 1
        elif path_lower == p2_lower:
            self._handle_to_participant[device_handle] = 2
            logger.debug(f"KeyboardRouter: Handle {device_handle} -> P2 (exact match)")
            return 2

        # Fallback: VID/PID matching (for Interception driver hardware IDs)
        device_vp = _extract_vid_pid(path)
        if device_vp:
            p1_vp = _extract_vid_pid(self._p1_path)
            p2_vp = _extract_vid_pid(self._p2_path)
            if device_vp == p1_vp:
                self._handle_to_participant[device_handle] = 1
                logger.debug(f"KeyboardRouter: Handle {device_handle} -> P1 (VID/PID match)")
                return 1
            elif device_vp == p2_vp:
                self._handle_to_participant[device_handle] = 2
                logger.debug(f"KeyboardRouter: Handle {device_handle} -> P2 (VID/PID match)")
                return 2

        self._handle_to_participant[device_handle] = 0
        return 0
