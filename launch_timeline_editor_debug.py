"""
Debug launcher for the timeline editor - shows detailed startup info.
"""

import sys
import traceback
from pathlib import Path

# Add project directory to path
sys.path.insert(0, str(Path(__file__).parent))

def main():
    print("=" * 60)
    print("Timeline Editor - Debug Launcher")
    print("=" * 60)
    print()

    try:
        print("[1/5] Importing modules...")
        from timeline_editor.editor_window import EditorWindow
        from config.experiment import ExperimentConfig
        print("      OK - Modules imported")

        print("[2/5] Creating default configuration...")
        from timeline_editor.config_io import create_default_config
        config = create_default_config()
        print(f"      OK - Config created with {len(config.trials)} trials")

        print("[3/5] Creating editor window...")
        sys.stdout.flush()  # Force output

        # Monkey-patch to add debug output
        original_init = EditorWindow.__init__
        def debug_init(self, *args, **kwargs):
            print("      [3a] Calling parent __init__...")
            sys.stdout.flush()
            original_init(self, *args, **kwargs)
            print("      [3b] Editor window created")
            sys.stdout.flush()
        EditorWindow.__init__ = debug_init

        app = EditorWindow(config)
        print("      OK - Window initialized")

        print("[4/5] Starting GUI event loop...")
        sys.stdout.flush()
        app.mainloop()

        print("[5/5] GUI closed normally")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user (Ctrl+C)")
        sys.exit(0)

    except Exception as e:
        print()
        print("=" * 60)
        print("ERROR OCCURRED")
        print("=" * 60)
        print()
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print()
        print("Full traceback:")
        print("-" * 60)
        traceback.print_exc()
        print("-" * 60)
        print()
        sys.exit(1)

if __name__ == "__main__":
    main()
