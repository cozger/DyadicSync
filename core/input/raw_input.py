"""
Low-level Windows Raw Input API listener via ctypes.

Handles Win32 Raw Input registration and message processing for
per-device keyboard identification. Does NOT block keystrokes —
for keyboard isolation, see InterceptionListener.

Platform: Windows only (uses user32.dll, kernel32.dll)
"""

import ctypes
import ctypes.wintypes as wintypes
import threading
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

# ─── Win32 Constants ───────────────────────────────────────────────────────

WM_INPUT = 0x00FF
WM_CLOSE = 0x0010
WM_DESTROY = 0x0002
WM_CREATE = 0x0001

RIM_TYPEKEYBOARD = 1
RID_INPUT = 0x10000003
RIDEV_INPUTSINK = 0x00000100

RIDI_DEVICENAME = 0x20000007
RIDI_DEVICEINFO = 0x2000000B

RI_KEY_MAKE = 0x0000  # Key down
RI_KEY_BREAK = 0x0001  # Key up
RI_KEY_E0 = 0x0002    # Extended key (E0 prefix)

WS_EX_NOACTIVATE = 0x08000000
WS_POPUP = 0x80000000

# Window class style
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001

# ─── ctypes Structures ────────────────────────────────────────────────────

class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class RAWKEYBOARD(ctypes.Structure):
    _fields_ = [
        ("MakeCode", wintypes.USHORT),
        ("Flags", wintypes.USHORT),
        ("Reserved", wintypes.USHORT),
        ("VKey", wintypes.USHORT),
        ("Message", wintypes.UINT),
        ("ExtraInformation", wintypes.ULONG),
    ]


class _RAWINPUT_UNION(ctypes.Union):
    _fields_ = [
        ("keyboard", RAWKEYBOARD),
    ]


class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", _RAWINPUT_UNION),
    ]


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.UINT),
        ("style", wintypes.UINT),
        ("lpfnWndProc", ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HICON),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
        ("hIconSm", wintypes.HICON),
    ]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", wintypes.POINT),
    ]


# ─── Win32 Function Prototypes ────────────────────────────────────────────

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

RegisterRawInputDevices = user32.RegisterRawInputDevices
RegisterRawInputDevices.restype = wintypes.BOOL
RegisterRawInputDevices.argtypes = [ctypes.POINTER(RAWINPUTDEVICE), wintypes.UINT, wintypes.UINT]

GetRawInputData = user32.GetRawInputData
GetRawInputData.restype = wintypes.UINT
GetRawInputData.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT), wintypes.UINT]

GetRawInputDeviceInfoW = user32.GetRawInputDeviceInfoW
GetRawInputDeviceInfoW.restype = wintypes.UINT
GetRawInputDeviceInfoW.argtypes = [wintypes.HANDLE, wintypes.UINT, ctypes.c_void_p, ctypes.POINTER(wintypes.UINT)]

WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

user32.DefWindowProcW.restype = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]

# ─── Callback Type ─────────────────────────────────────────────────────────

# on_key_event(device_handle: int, vk_code: int, is_key_down: bool)
KeyEventCallback = Callable[[int, int, bool], None]


# ─── RawInputListener ─────────────────────────────────────────────────────

class RawInputListener:
    """
    Listens for raw keyboard input from all keyboards via Windows Raw Input API.

    Creates a hidden window in a background thread, registers for keyboard
    raw input with RIDEV_INPUTSINK (receives input even when not focused),
    and dispatches key events with device handles to a callback.

    This class handles device identification only. For keyboard isolation
    (blocking participant keystrokes from other apps), see InterceptionListener.
    """

    def __init__(self, on_key_event: KeyEventCallback):
        """
        Args:
            on_key_event: Callback(device_handle, vk_code, is_key_down) for each key event.
        """
        self._on_key_event = on_key_event
        self._thread: Optional[threading.Thread] = None
        self._hwnd: Optional[int] = None
        self._running = threading.Event()
        self._ready = threading.Event()
        # Must prevent GC of the WNDPROC callback
        self._wndproc_ref = None

    def start(self):
        """Start listening for raw keyboard input in a background thread."""
        if self._thread is not None:
            return

        self._running.set()
        self._ready.clear()
        self._thread = threading.Thread(target=self._run_message_pump, daemon=True, name="RawInputListener")
        self._thread.start()

        # Wait for the hidden window to be created (up to 5 seconds)
        if not self._ready.wait(timeout=5.0):
            logger.warning("RawInputListener: Hidden window creation timed out")

    def stop(self):
        """Stop listening and clean up."""
        self._running.clear()

        if self._hwnd:
            try:
                user32.PostMessageW(self._hwnd, WM_CLOSE, 0, 0)
            except Exception:
                pass

        if self._thread is not None:
            self._thread.join(timeout=3.0)
            self._thread = None

        self._hwnd = None

    def get_device_path(self, handle: int) -> Optional[str]:
        """
        Get the stable device path for a raw input device handle.

        Args:
            handle: Device handle from WM_INPUT message.

        Returns:
            Device path string (e.g., '\\\\?\\HID#VID_046D&PID_C52B...') or None on failure.
        """
        return self._get_device_info_string(handle, RIDI_DEVICENAME)

    def get_device_name(self, handle: int) -> Optional[str]:
        """
        Get human-readable device name for a raw input device handle.

        Falls back to extracting VID/PID from device path if product string
        is not available.

        Args:
            handle: Device handle from WM_INPUT message.

        Returns:
            Human-readable name or None on failure.
        """
        # Try to extract a friendly name from the device path
        path = self.get_device_path(handle)
        if path:
            # Extract VID and PID from path like \\?\HID#VID_046D&PID_C52B...
            vid = pid = None
            path_upper = path.upper()
            if 'VID_' in path_upper:
                try:
                    vid_start = path_upper.index('VID_') + 4
                    vid = path_upper[vid_start:vid_start + 4]
                except (ValueError, IndexError):
                    pass
            if 'PID_' in path_upper:
                try:
                    pid_start = path_upper.index('PID_') + 4
                    pid = path_upper[pid_start:pid_start + 4]
                except (ValueError, IndexError):
                    pass

            if vid and pid:
                return f"Keyboard (VID:{vid} PID:{pid})"

        return "Unknown Keyboard"

    def _get_device_info_string(self, handle: int, info_type: int) -> Optional[str]:
        """Get device info string via GetRawInputDeviceInfoW."""
        # First call: get required buffer size
        size = wintypes.UINT(0)
        result = GetRawInputDeviceInfoW(handle, info_type, None, ctypes.byref(size))

        if size.value == 0:
            return None

        # Second call: get the actual data
        buf = ctypes.create_unicode_buffer(size.value)
        result = GetRawInputDeviceInfoW(handle, info_type, buf, ctypes.byref(size))

        if result == 0xFFFFFFFF:  # UINT_MAX = error
            return None

        return buf.value

    def _run_message_pump(self):
        """Background thread: create hidden window and run Win32 message pump."""
        try:
            # Create window procedure
            def wnd_proc(hwnd, msg, wparam, lparam):
                if msg == WM_INPUT:
                    self._handle_wm_input(lparam)
                    return 0
                elif msg == WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
                return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

            # Keep reference to prevent GC
            self._wndproc_ref = WNDPROC(wnd_proc)

            # Register window class
            hinstance = kernel32.GetModuleHandleW(None)
            class_name = "DyadicSyncRawInput"

            wc = WNDCLASSEXW()
            wc.cbSize = ctypes.sizeof(WNDCLASSEXW)
            wc.style = CS_HREDRAW | CS_VREDRAW
            wc.lpfnWndProc = self._wndproc_ref
            wc.cbClsExtra = 0
            wc.cbWndExtra = 0
            wc.hInstance = hinstance
            wc.hIcon = None
            wc.hCursor = None
            wc.hbrBackground = None
            wc.lpszMenuName = None
            wc.lpszClassName = class_name
            wc.hIconSm = None

            atom = user32.RegisterClassExW(ctypes.byref(wc))
            if not atom:
                logger.error("RawInputListener: Failed to register window class")
                return

            # Create hidden message-only window
            self._hwnd = user32.CreateWindowExW(
                0,  # dwExStyle
                class_name,
                "DyadicSync Raw Input",
                0,  # dwStyle (invisible)
                0, 0, 0, 0,  # x, y, w, h
                None,  # hWndParent (not HWND_MESSAGE, to receive RIDEV_INPUTSINK)
                None,  # hMenu
                hinstance,
                None  # lpParam
            )

            if not self._hwnd:
                logger.error(f"RawInputListener: Failed to create hidden window (error: {kernel32.GetLastError()})")
                user32.UnregisterClassW(class_name, hinstance)
                return

            # Register for raw keyboard input
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = 0x01  # Generic Desktop Controls
            rid.usUsage = 0x06  # Keyboard
            rid.dwFlags = RIDEV_INPUTSINK  # Receive input even without focus
            rid.hwndTarget = self._hwnd

            success = RegisterRawInputDevices(ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE))
            if not success:
                logger.error(f"RawInputListener: Failed to register raw input devices (error: {kernel32.GetLastError()})")
                user32.DestroyWindow(self._hwnd)
                user32.UnregisterClassW(class_name, hinstance)
                self._hwnd = None
                return

            logger.info("RawInputListener: Registered for raw keyboard input")

            self._ready.set()

            # Message pump
            msg = MSG()
            while self._running.is_set():
                ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                if ret <= 0:
                    break
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

            # Cleanup
            if self._hwnd:
                user32.DestroyWindow(self._hwnd)
            user32.UnregisterClassW(class_name, hinstance)
            self._hwnd = None

        except Exception as e:
            logger.error(f"RawInputListener: Message pump error: {e}", exc_info=True)
            self._ready.set()  # Unblock start() even on failure

    def _handle_wm_input(self, lparam):
        """Process a WM_INPUT message and dispatch to callback."""
        try:
            # Get required buffer size
            size = wintypes.UINT(0)
            GetRawInputData(lparam, RID_INPUT, None, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))

            if size.value == 0:
                return

            # Allocate buffer and read raw input
            buf = ctypes.create_string_buffer(size.value)
            GetRawInputData(lparam, RID_INPUT, buf, ctypes.byref(size), ctypes.sizeof(RAWINPUTHEADER))

            raw = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents

            # Only handle keyboard events
            if raw.header.dwType != RIM_TYPEKEYBOARD:
                return

            device_handle = raw.header.hDevice
            vk_code = raw.data.keyboard.VKey
            flags = raw.data.keyboard.Flags
            is_key_down = (flags & RI_KEY_BREAK) == 0

            # Dispatch to callback (for all devices — router filters by participant)
            if self._on_key_event and device_handle:
                self._on_key_event(device_handle, vk_code, is_key_down)

        except Exception as e:
            logger.error(f"RawInputListener: Error handling WM_INPUT: {e}", exc_info=True)

