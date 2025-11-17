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

def main():
    print("=" * 60, flush=True)
    print("DyadicSync Timeline Editor - Standalone Launcher", flush=True)
    print("=" * 60, flush=True)
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
