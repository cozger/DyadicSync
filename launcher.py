"""
DyadicSync Launcher
Simple menu for running different components of the system.

Usage:
    python launcher.py

Author: DyadicSync Development Team
Date: 2025-11-15
"""

import sys
import subprocess
from pathlib import Path


def print_header():
    """Print application header"""
    print("\n" + "=" * 70)
    print(" " * 20 + "DYADICSYNC LAUNCHER")
    print("=" * 70)


def print_menu():
    """Print main menu"""
    print("\nPlease select an option:\n")
    print("  1. Timeline Editor (Design Experiments)")
    print("  2. Test Device Scanner (check hardware)")
    print("  3. Open Device Manager GUI (configure devices)")
    print("  4. Run Integration Example (verify config)")
    print("  5. Launch Experiment (WithBaseline.py)")
    print("  6. Show Documentation")
    print("  7. Exit")
    print("\n" + "-" * 70)


def run_script(script_name, description):
    """Run a Python script"""
    print(f"\n▶ Running {description}...")
    print("-" * 70)

    script_path = Path(__file__).parent / script_name

    if not script_path.exists():
        print(f"✗ Error: {script_name} not found!")
        return False

    try:
        # Run script and wait for completion
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=Path(__file__).parent
        )
        return result.returncode == 0

    except KeyboardInterrupt:
        print("\n\n✗ Interrupted by user")
        return False

    except Exception as e:
        print(f"\n✗ Error running script: {str(e)}")
        return False


def show_documentation():
    """Show available documentation"""
    print("\n" + "=" * 70)
    print("AVAILABLE DOCUMENTATION")
    print("=" * 70)

    docs = [
        ("QUICK_START_DEVICE_MANAGER.md", "Quick start guide (recommended)"),
        ("DEVICE_MANAGER_README.md", "Complete device manager documentation"),
        ("CLAUDE.md", "Project overview and architecture"),
        ("code_analysis.md", "Technical code analysis"),
        ("gui_style_analysis.md", "GUI design patterns"),
        ("Exp Setup Instructions.txt", "Full experimental setup procedure"),
        ("CodeBook.txt", "LSL marker definitions"),
    ]

    print("\nDocumentation files in the project:\n")

    project_root = Path(__file__).parent

    for filename, description in docs:
        filepath = project_root / filename
        exists = filepath.exists()
        status = "✓" if exists else "✗"
        print(f"  {status} {filename}")
        print(f"     {description}")
        print()

    print("-" * 70)
    print("\nTo view a document, open it in your text editor or markdown viewer.")


def check_prerequisites():
    """Check if required packages are installed"""
    print("\n" + "=" * 70)
    print("CHECKING PREREQUISITES")
    print("=" * 70)

    required_packages = [
        'pyglet',
        'sounddevice',
        'soundfile',
        'numpy',
        'pandas',
        'pylsl',
    ]

    all_ok = True

    print("\nRequired Python packages:\n")

    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} (NOT INSTALLED)")
            all_ok = False

    if not all_ok:
        print("\n" + "-" * 70)
        print("⚠ Some packages are missing. Install them with:")
        print("\n  pip install " + " ".join(required_packages))
        print("\n" + "-" * 70)
    else:
        print("\n✓ All required packages installed!")

    return all_ok


def main():
    """Main launcher function"""
    print_header()

    # Check prerequisites first
    if not check_prerequisites():
        print("\n⚠ Please install missing packages before continuing.")
        input("\nPress Enter to exit...")
        return

    while True:
        print_menu()

        try:
            choice = input("Enter your choice (1-7): ").strip()

            if choice == '1':
                # Timeline Editor
                success = run_script("timeline_editor/editor_window.py", "Timeline Editor")
                input("\nPress Enter to continue...")

            elif choice == '2':
                # Test device scanner
                success = run_script("test_device_scanner.py", "Device Scanner Test")
                input("\nPress Enter to continue...")

            elif choice == '3':
                # Open device manager GUI
                success = run_script("device_manager_gui.py", "Device Manager GUI")
                input("\nPress Enter to continue...")

            elif choice == '4':
                # Run integration example
                success = run_script("integration_example.py", "Integration Example")
                input("\nPress Enter to continue...")

            elif choice == '5':
                # Launch experiment
                print("\n⚠ Make sure you have:")
                print("  1. Configured all devices in Device Manager")
                print("  2. Validated the configuration")
                print("  3. Integrated the config code into WithBaseline.py")
                print("\nContinue? (y/n): ", end='')

                if input().strip().lower() == 'y':
                    success = run_script("WithBaseline.py", "DyadicSync Experiment")
                else:
                    print("Launch cancelled.")

                input("\nPress Enter to continue...")

            elif choice == '6':
                # Show documentation
                show_documentation()
                input("\nPress Enter to continue...")

            elif choice == '7':
                # Exit
                print("\nExiting DyadicSync Launcher. Goodbye!")
                break

            else:
                print("\n✗ Invalid choice. Please enter 1-7.")
                input("Press Enter to continue...")

        except KeyboardInterrupt:
            print("\n\nExiting DyadicSync Launcher. Goodbye!")
            break

        except Exception as e:
            print(f"\n✗ Unexpected error: {str(e)}")
            input("Press Enter to continue...")


if __name__ == "__main__":
    main()
