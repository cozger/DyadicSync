# Keyboard Isolation Setup

Keyboard isolation prevents participant keypresses from reaching other applications on the control monitor. Only DyadicSync receives input from participant keyboards. The control keyboard is unaffected.

## How It Works

DyadicSync uses the [Interception driver](https://github.com/oblitum/Interception) to intercept keyboard input at the kernel level. When a participant presses a key, the driver captures it before it enters the normal Windows input pipeline. DyadicSync processes the keystroke internally (for ratings, instructions, etc.) but does NOT forward it to other applications.

## Setup (One-Time)

### 1. Install the Interception Driver

1. Download the latest release from [github.com/oblitum/Interception/releases](https://github.com/oblitum/Interception/releases)
2. Extract the archive
3. Open an **Administrator** command prompt
4. Navigate to the extracted folder and run:
   ```
   install-interception.exe /install
   ```
5. **Reboot** the computer (required for the driver to load)

### 2. Install the Interception DLL

The `interception.dll` file from the SDK must be accessible to Python:

- **Option A**: Copy `interception.dll` (from the `library/x64/` folder in the SDK) to the DyadicSync project directory
- **Option B**: Copy it to `C:\Windows\System32\`
- **Option C**: Add the SDK `library/x64/` folder to your system PATH

### 3. Verify Installation

1. Open the DyadicSync Timeline Editor
2. Go to **Devices > Setup Devices**
3. In the Keyboards section, the isolation checkbox should show:
   - "Uses Interception driver..." = Driver available
   - "Requires Interception driver (not installed)" = Driver not found

## Usage

1. Open **Devices > Setup Devices**
2. Identify both participant keyboards using the "Identify" buttons
3. Check **"Isolate participant keyboards"**
4. Save and run your experiment

During the experiment, participant keyboards will only send input to DyadicSync. The control keyboard works normally.

## Troubleshooting

### "Interception driver not available"
- Verify the driver is installed: check Device Manager for "Interception" entries under "Keyboard" devices
- Verify `interception.dll` is accessible (see step 2 above)
- Make sure you rebooted after installing the driver

### Participant keyboards not blocked
- Verify keyboards are correctly identified in Device Setup (VID/PID should match)
- Check the experiment console output for `[InterceptionListener]` messages showing which devices are blocked

### Control keyboard not working
- This should not happen. The Interception listener only blocks devices matching participant VID/PIDs
- If it does happen, the VID/PID of your control keyboard may match a participant keyboard. Use different keyboard models.

## Uninstalling

To remove the Interception driver:
1. Open an **Administrator** command prompt
2. Run: `install-interception.exe /uninstall`
3. Reboot
