"""
Standalone launcher for the timeline editor with error reporting.
Run this directly from Windows to see any errors.
"""

import sys
import traceback
from pathlib import Path
import time

# Force unbuffered output
sys.stdout = sys.__stdout__
sys.stderr = sys.__stderr__
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(line_buffering=True)

# Add project directory to path
sys.path.insert(0, str(Path(__file__).parent))

def validate_environment():
    """Validate that we're running in the correct conda environment."""
    import os

    # Check if running in 'sync' environment
    env_prefix = sys.prefix.lower()

    if 'sync' not in env_prefix and 'base' in env_prefix:
        print("\n" + "=" * 60, flush=True)
        print("ERROR: Wrong Python Environment Detected!", flush=True)
        print("=" * 60, flush=True)
        print(flush=True)
        print(f"Current Python: {sys.executable}", flush=True)
        print(f"Current version: {sys.version}", flush=True)
        print(flush=True)
        print("This is the BASE environment, which lacks required dependencies.", flush=True)
        print(flush=True)
        print("SOLUTION: Use the provided launcher script instead:", flush=True)
        print("  1. Double-click: launch_editor.bat", flush=True)
        print("  2. Or run manually: conda activate sync && python launch_timeline_editor.py", flush=True)
        print(flush=True)
        print("Why this matters: Running without the 'sync' environment causes", flush=True)
        print("exit code 3221225477 (Access Violation) when loading dependencies.", flush=True)
        print("=" * 60, flush=True)

        # Give user time to read the message
        input("\nPress Enter to exit...")
        sys.exit(1)

    # Verify critical imports are available
    missing_modules = []
    for module_name in ['pyglet', 'sounddevice', 'pandas', 'pylsl']:
        try:
            __import__(module_name)
        except ImportError:
            missing_modules.append(module_name)

    if missing_modules:
        print("\n" + "=" * 60, flush=True)
        print("ERROR: Missing Required Dependencies!", flush=True)
        print("=" * 60, flush=True)
        print(flush=True)
        print(f"Current Python: {sys.executable}", flush=True)
        print(f"Missing modules: {', '.join(missing_modules)}", flush=True)
        print(flush=True)
        print("SOLUTION: Install dependencies in the 'sync' environment:", flush=True)
        print("  conda activate sync", flush=True)
        print("  pip install -r requirements.txt", flush=True)
        print("=" * 60, flush=True)

        input("\nPress Enter to exit...")
        sys.exit(1)

def main():
    print("=" * 60, flush=True)
    print("DyadicSync Timeline Editor - Standalone Launcher", flush=True)
    print("=" * 60, flush=True)
    print(flush=True)

    # Validate environment BEFORE attempting any imports
    print(f"[{time.time():.3f}] Validating environment...", flush=True)
    validate_environment()
    print(f"[{time.time():.3f}] Environment validation passed", flush=True)
    print(flush=True)

    print(f"[{time.time():.3f}] Starting...", flush=True)

    try:
        print(f"[{time.time():.3f}] Importing timeline editor...", flush=True)
        from timeline_editor.editor_window import EditorWindow

        print(f"[{time.time():.3f}] Creating editor window...", flush=True)
        app = EditorWindow()

        print(f"[{time.time():.3f}] Forcing window update and focus...", flush=True)
        app.update_idletasks()  # Force window to draw
        app.update()            # Process all pending events
        app.deiconify()         # Ensure window is shown
        app.lift()              # Bring to front
        app.focus_force()       # Force focus
        print(f"[{time.time():.3f}] Window updated, size={app.winfo_width()}x{app.winfo_height()}", flush=True)

        print(f"[{time.time():.3f}] Launching GUI (entering mainloop)...", flush=True)
        app.mainloop()

        print(f"[{time.time():.3f}] Editor closed normally.", flush=True)

    except Exception as e:
        print(flush=True)
        print("=" * 60, flush=True)
        print("ERROR: Timeline editor failed to launch", flush=True)
        print("=" * 60, flush=True)
        print(flush=True)
        print(f"Error type: {type(e).__name__}", flush=True)
        print(f"Error message: {str(e)}", flush=True)
        print(flush=True)
        print("Full traceback:", flush=True)
        print("-" * 60, flush=True)
        traceback.print_exc()
        print("-" * 60, flush=True)
        print(flush=True)
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
