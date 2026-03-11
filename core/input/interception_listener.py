"""
Kernel-level keyboard interceptor using the Interception driver.

Blocks keystrokes from specific keyboards (participant devices) at the
driver level, preventing them from reaching any other application.
Non-participant keystrokes are forwarded normally.

Requires:
1. Interception driver installed (github.com/oblitum/Interception)
2. interception.dll in PATH or project directory

Platform: Windows only
"""

import ctypes
import ctypes.wintypes as wintypes
import threading
import logging
import os
from typing import Optional, Callable, Set

logger = logging.getLogger(__name__)

# ─── Constants ────────────────────────────────────────────────────────────────

INTERCEPTION_MAX_KEYBOARD = 10

# Key state flags (from InterceptionKeyState enum)
INTERCEPTION_KEY_DOWN = 0x00
INTERCEPTION_KEY_UP = 0x01
INTERCEPTION_KEY_E0 = 0x02
INTERCEPTION_KEY_E1 = 0x04

# Filter: capture all key events
INTERCEPTION_FILTER_KEY_ALL = 0xFFFF

# MapVirtualKeyW mapping type
MAPVK_VSC_TO_VK_EX = 3

# ─── ctypes Structures ───────────────────────────────────────────────────────

class InterceptionKeyStroke(ctypes.Structure):
    _fields_ = [
        ("code", ctypes.c_ushort),        # scan code
        ("state", ctypes.c_ushort),       # key state flags
        ("information", ctypes.c_uint),   # extra info
    ]


# Predicate function type: int (*)(int device)
InterceptionPredicate = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_int)

# ─── DLL Loading ──────────────────────────────────────────────────────────────

def _load_dll():
    """Load interception.dll, searching standard and project-local paths."""
    # Try standard ctypes loading (PATH, system32, cwd)
    try:
        return ctypes.CDLL("interception.dll")
    except OSError:
        pass

    # Try project-local: DyadicSync/interception/interception.dll
    project_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    for subdir in ["interception", "lib", "."]:
        candidate = os.path.join(project_dir, subdir, "interception.dll")
        if os.path.exists(candidate):
            return ctypes.CDLL(candidate)

    raise ImportError(
        "interception.dll not found. Install the Interception driver and place "
        "interception.dll in your PATH or the project directory. "
        "See docs/KEYBOARD_ISOLATION_SETUP.md for instructions."
    )


def _setup_dll(dll):
    """Configure ctypes function prototypes for the Interception DLL."""
    # interception_create_context() -> void*
    dll.interception_create_context.restype = ctypes.c_void_p
    dll.interception_create_context.argtypes = []

    # interception_destroy_context(void* context)
    dll.interception_destroy_context.restype = None
    dll.interception_destroy_context.argtypes = [ctypes.c_void_p]

    # interception_set_filter(void* context, predicate, ushort filter)
    dll.interception_set_filter.restype = None
    dll.interception_set_filter.argtypes = [ctypes.c_void_p, InterceptionPredicate, ctypes.c_ushort]

    # interception_wait_with_timeout(void* context, ulong ms) -> int device
    dll.interception_wait_with_timeout.restype = ctypes.c_int
    dll.interception_wait_with_timeout.argtypes = [ctypes.c_void_p, ctypes.c_ulong]

    # interception_receive(void* context, int device, void* stroke, uint count) -> int
    dll.interception_receive.restype = ctypes.c_int
    dll.interception_receive.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]

    # interception_send(void* context, int device, void* stroke, uint count) -> int
    dll.interception_send.restype = ctypes.c_int
    dll.interception_send.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]

    # interception_get_hardware_id(void* context, int device, void* buf, uint size) -> uint
    dll.interception_get_hardware_id.restype = ctypes.c_uint
    dll.interception_get_hardware_id.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]

    return dll


# Load and configure the DLL at import time.
# ImportError propagates if DLL not found — callers should catch this.
_dll = _setup_dll(_load_dll())

# user32 for MapVirtualKeyW (scan code → VK code conversion)
_user32 = ctypes.windll.user32

# Keep reference to predicate callback to prevent garbage collection
_is_keyboard_pred = InterceptionPredicate(lambda device: 1 if 1 <= device <= INTERCEPTION_MAX_KEYBOARD else 0)


# ─── Helpers ──────────────────────────────────────────────────────────────────

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


# ─── Callback Type ────────────────────────────────────────────────────────────

# Same signature as RawInputListener: (device_id: int, vk_code: int, is_key_down: bool)
KeyEventCallback = Callable[[int, int, bool], None]


# ─── InterceptionListener ────────────────────────────────────────────────────

class InterceptionListener:
    """
    Kernel-level keyboard interceptor using the Interception driver.

    Runs a blocking wait loop on a background thread. For each keystroke:
    - Identifies which device it came from
    - For participant devices: blocks the keystroke (does not forward to OS)
      and dispatches to the callback
    - For non-participant devices: forwards normally via send()
      and dispatches to the callback

    Thread safety: The wait loop runs on a background daemon thread.
    Callbacks fire on that thread. Callers must marshal to the main thread
    if needed (same pattern as RawInputListener).
    """

    def __init__(self, on_key_event: KeyEventCallback,
                 intercept_device_paths: Set[str]):
        """
        Args:
            on_key_event: Callback(device_id, vk_code, is_key_down) for each key event.
            intercept_device_paths: Set of device path strings whose keystrokes
                should be blocked from reaching other applications.
        """
        self._on_key_event = on_key_event
        self._intercept_vid_pids: set = set()
        for path in intercept_device_paths:
            vp = _extract_vid_pid(path)
            if vp:
                self._intercept_vid_pids.add(vp)

        self._thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._ready = threading.Event()
        self._failed = threading.Event()  # Set if context creation fails
        self._context = None

        # Maps: interception device ID (1-10) → hardware ID string
        self._device_hw_ids: dict = {}
        # Maps: interception device ID → True (blocked) or False (pass-through)
        self._blocked_devices: dict = {}

    def start(self):
        """Start listening and intercepting keyboard input.

        Raises RuntimeError if the Interception driver context cannot be created.
        """
        if self._thread is not None:
            return

        self._running.set()
        self._ready.clear()
        self._failed.clear()
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="InterceptionListener"
        )
        self._thread.start()

        if not self._ready.wait(timeout=5.0):
            logger.warning("InterceptionListener: Startup timed out")

        if self._failed.is_set():
            self._thread = None
            raise RuntimeError("Interception driver context creation failed. Is the driver loaded?")

    def stop(self):
        """Stop listening and clean up."""
        self._running.clear()

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        self._device_hw_ids.clear()
        self._blocked_devices.clear()

    def get_device_path(self, device_id: int) -> Optional[str]:
        """Get hardware ID string for an Interception device ID."""
        return self._device_hw_ids.get(device_id)

    def _run_loop(self):
        """Background thread: create context, map devices, process events."""
        try:
            self._context = _dll.interception_create_context()
            if not self._context:
                print("[InterceptionListener] ERROR: Failed to create context. "
                      "Is the Interception driver installed and loaded?")
                logger.error("InterceptionListener: Failed to create context")
                self._failed.set()
                self._ready.set()
                return

            # Register filter for all keyboard events on all keyboard devices
            _dll.interception_set_filter(
                self._context, _is_keyboard_pred, INTERCEPTION_FILTER_KEY_ALL
            )

            # Map keyboard devices to participants via VID/PID matching
            self._map_devices()

            blocked_count = sum(1 for v in self._blocked_devices.values() if v)
            print(f"[InterceptionListener] Ready: {blocked_count} participant keyboard(s) blocked, "
                  f"{len(self._device_hw_ids) - blocked_count} forwarded")

            self._ready.set()

            # Main event loop
            stroke = InterceptionKeyStroke()
            while self._running.is_set():
                # Wait with timeout so we can check the running flag
                device = _dll.interception_wait_with_timeout(self._context, 100)
                if device == 0:
                    continue  # timeout — check running flag and loop

                if device < 1 or device > INTERCEPTION_MAX_KEYBOARD:
                    continue  # not a keyboard

                n = _dll.interception_receive(
                    self._context, device, ctypes.byref(stroke), 1
                )
                if n <= 0:
                    continue

                is_blocked = self._blocked_devices.get(device, False)

                if not is_blocked:
                    # Non-participant device — forward keystroke to OS
                    _dll.interception_send(
                        self._context, device, ctypes.byref(stroke), 1
                    )

                # Convert scan code to VK code
                vk_code = self._scancode_to_vk(stroke.code, stroke.state)
                if vk_code == 0:
                    # Forward even if we can't convert (shouldn't block unknown keys)
                    if is_blocked:
                        _dll.interception_send(
                            self._context, device, ctypes.byref(stroke), 1
                        )
                    continue

                is_key_down = (stroke.state & INTERCEPTION_KEY_UP) == 0

                # Dispatch to callback
                if self._on_key_event:
                    try:
                        self._on_key_event(device, vk_code, is_key_down)
                    except Exception as e:
                        logger.error(f"InterceptionListener: Callback error: {e}",
                                     exc_info=True)

        except Exception as e:
            print(f"[InterceptionListener] ERROR: {e}")
            logger.error(f"InterceptionListener: Loop error: {e}", exc_info=True)
            self._ready.set()

        finally:
            if self._context:
                _dll.interception_destroy_context(self._context)
                self._context = None
                print("[InterceptionListener] Context destroyed, listener stopped")

    def _map_devices(self):
        """Map Interception device IDs to participant devices via VID/PID."""
        for device in range(1, INTERCEPTION_MAX_KEYBOARD + 1):
            hw_id = self._get_hardware_id(device)
            if not hw_id:
                continue

            self._device_hw_ids[device] = hw_id
            device_vid_pid = _extract_vid_pid(hw_id)

            if device_vid_pid and device_vid_pid in self._intercept_vid_pids:
                self._blocked_devices[device] = True
                print(f"[InterceptionListener] Device {device}: {hw_id[:60]} -> BLOCKED (participant)")
            else:
                self._blocked_devices[device] = False
                print(f"[InterceptionListener] Device {device}: {hw_id[:60]} -> pass-through")

    def _get_hardware_id(self, device: int) -> Optional[str]:
        """Get hardware ID string for a device via the Interception API."""
        buf_size = 500
        buf = ctypes.create_unicode_buffer(buf_size)
        result = _dll.interception_get_hardware_id(
            self._context, device, buf, buf_size * ctypes.sizeof(ctypes.c_wchar)
        )
        if result > 0:
            return buf.value
        return None

    @staticmethod
    def _scancode_to_vk(code: int, state: int) -> int:
        """Convert scan code + state flags to a Windows VK code."""
        scan = code
        if state & INTERCEPTION_KEY_E0:
            # Extended key: use 0xE0 prefix for MapVirtualKeyW
            scan = 0xE000 | code
        return _user32.MapVirtualKeyW(scan, MAPVK_VSC_TO_VK_EX)
