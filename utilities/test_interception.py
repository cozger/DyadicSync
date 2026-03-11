"""
Standalone test for the Interception driver.

Phase 1: Lists all keyboards and their hardware IDs.
Phase 2: Captures keystrokes, shows which device they come from.
Phase 3: Lets you pick a device to BLOCK, then verifies blocking works.

Run: conda activate sync && python utilities/test_interception.py
"""

import ctypes
import ctypes.wintypes as wintypes
import sys
import os
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.input.interception_listener import (
    _dll, _is_keyboard_pred, _extract_vid_pid,
    InterceptionKeyStroke, InterceptionPredicate,
    INTERCEPTION_MAX_KEYBOARD, INTERCEPTION_FILTER_KEY_ALL,
    INTERCEPTION_KEY_UP, INTERCEPTION_KEY_E0,
    MAPVK_VSC_TO_VK_EX,
)

_user32 = ctypes.windll.user32


def scancode_to_vk(code, state):
    scan = code
    if state & INTERCEPTION_KEY_E0:
        scan = 0xE000 | code
    return _user32.MapVirtualKeyW(scan, MAPVK_VSC_TO_VK_EX)


def vk_to_name(vk):
    """Get key name from VK code."""
    scan = _user32.MapVirtualKeyW(vk, 0)  # MAPVK_VK_TO_VSC
    buf = ctypes.create_unicode_buffer(32)
    result = _user32.GetKeyNameTextW(scan << 16, buf, 32)
    if result > 0:
        return buf.value
    return f"VK_0x{vk:02X}"


def main():
    print("=" * 60)
    print("INTERCEPTION DRIVER TEST")
    print("=" * 60)

    # Phase 1: Create context and list devices
    print("\n--- Phase 1: Creating context and listing keyboards ---\n")

    ctx = _dll.interception_create_context()
    if not ctx:
        print("ERROR: Failed to create Interception context!")
        print("Is the Interception driver installed?")
        print("Run: install-interception.exe /install (as admin) then reboot")
        return

    print("Context created successfully.\n")

    # Set filter for all keyboard events
    _dll.interception_set_filter(ctx, _is_keyboard_pred, INTERCEPTION_FILTER_KEY_ALL)
    print("Filter set for all keyboard events.\n")

    # List all keyboards
    devices = {}
    print(f"{'ID':<4} {'Hardware ID':<70} {'VID/PID'}")
    print("-" * 90)
    for device in range(1, INTERCEPTION_MAX_KEYBOARD + 1):
        buf = ctypes.create_unicode_buffer(500)
        result = _dll.interception_get_hardware_id(
            ctx, device, buf, 500 * ctypes.sizeof(ctypes.c_wchar)
        )
        if result > 0:
            hw_id = buf.value
            vid_pid = _extract_vid_pid(hw_id)
            vp_str = f"{vid_pid[0]}:{vid_pid[1]}" if vid_pid else "N/A"
            devices[device] = hw_id
            print(f"{device:<4} {hw_id:<70} {vp_str}")

    if not devices:
        print("No keyboards detected by Interception driver!")
        _dll.interception_destroy_context(ctx)
        return

    # Phase 2: Capture keystrokes to identify devices
    print(f"\n--- Phase 2: Press keys on EACH keyboard to identify them ---")
    print(f"--- Press keys on different keyboards. Press ESC to continue ---\n")

    stroke = InterceptionKeyStroke()
    device_seen = {}

    while True:
        device = _dll.interception_wait_with_timeout(ctx, 200)
        if device == 0:
            continue

        if device < 1 or device > INTERCEPTION_MAX_KEYBOARD:
            continue

        n = _dll.interception_receive(ctx, device, ctypes.byref(stroke), 1)
        if n <= 0:
            continue

        # Always forward during identification phase
        _dll.interception_send(ctx, device, ctypes.byref(stroke), 1)

        is_down = (stroke.state & INTERCEPTION_KEY_UP) == 0
        if not is_down:
            continue  # Only show key-down

        vk = scancode_to_vk(stroke.code, stroke.state)
        key_name = vk_to_name(vk) if vk else f"scan={stroke.code}"
        hw_id = devices.get(device, "unknown")
        vid_pid = _extract_vid_pid(hw_id) if hw_id != "unknown" else None

        device_seen[device] = hw_id
        print(f"  Device {device}: key={key_name:<15} hw_id={hw_id[:50]}")

        # ESC to continue
        if vk == 0x1B:
            print("\nESC pressed, moving to Phase 3...\n")
            break

    # Phase 3: Block a device
    print("--- Phase 3: Select a device to BLOCK ---\n")
    print("Detected keyboards:")
    for dev_id, hw_id in sorted(device_seen.items()):
        vid_pid = _extract_vid_pid(hw_id)
        vp_str = f"{vid_pid[0]}:{vid_pid[1]}" if vid_pid else "N/A"
        print(f"  [{dev_id}] {hw_id[:60]}  (VID:PID = {vp_str})")

    print(f"\nEnter device ID to block (or 0 to skip): ", end="", flush=True)

    # Read input by capturing keystrokes (since we're intercepting everything)
    input_buf = []
    while True:
        device = _dll.interception_wait_with_timeout(ctx, 200)
        if device == 0:
            continue
        if device < 1 or device > INTERCEPTION_MAX_KEYBOARD:
            continue

        n = _dll.interception_receive(ctx, device, ctypes.byref(stroke), 1)
        if n <= 0:
            continue

        # Forward all during input
        _dll.interception_send(ctx, device, ctypes.byref(stroke), 1)

        is_down = (stroke.state & INTERCEPTION_KEY_UP) == 0
        if not is_down:
            continue

        vk = scancode_to_vk(stroke.code, stroke.state)
        if vk == 0x0D:  # Enter
            print()
            break
        if 0x30 <= vk <= 0x39:  # Digits
            digit = chr(vk)
            input_buf.append(digit)
            print(digit, end="", flush=True)

    try:
        block_id = int("".join(input_buf)) if input_buf else 0
    except ValueError:
        block_id = 0

    if block_id == 0 or block_id not in device_seen:
        print("No device selected for blocking. Exiting.")
        _dll.interception_destroy_context(ctx)
        return

    blocked_hw = device_seen[block_id]
    print(f"\nBLOCKING device {block_id}: {blocked_hw[:60]}")
    print("Keys from this device will NOT reach other apps.")
    print("Keys from other keyboards will work normally.")
    print("Press ESC on any OTHER keyboard to exit.\n")

    key_count = 0
    while True:
        device = _dll.interception_wait_with_timeout(ctx, 200)
        if device == 0:
            continue
        if device < 1 or device > INTERCEPTION_MAX_KEYBOARD:
            continue

        n = _dll.interception_receive(ctx, device, ctypes.byref(stroke), 1)
        if n <= 0:
            continue

        is_down = (stroke.state & INTERCEPTION_KEY_UP) == 0
        vk = scancode_to_vk(stroke.code, stroke.state)
        key_name = vk_to_name(vk) if vk else f"scan={stroke.code}"

        if device == block_id:
            # BLOCKED — do NOT call send()
            if is_down:
                key_count += 1
                print(f"  BLOCKED: device={device} key={key_name} (#{key_count})")
        else:
            # Forward normally
            _dll.interception_send(ctx, device, ctypes.byref(stroke), 1)
            if is_down:
                print(f"  forwarded: device={device} key={key_name}")
                if vk == 0x1B:  # ESC
                    print("\nESC on non-blocked keyboard. Exiting.")
                    break

    print(f"\nTest complete. Blocked {key_count} keystrokes from device {block_id}.")
    _dll.interception_destroy_context(ctx)
    print("Context destroyed. All keyboards restored to normal.")


if __name__ == "__main__":
    main()
