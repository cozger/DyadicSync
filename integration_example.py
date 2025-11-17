"""
Integration Example: Using Device Configuration with WithBaseline.py

This script demonstrates how to integrate the Device Manager configuration
with the existing WithBaseline.py experiment script.

Author: DyadicSync Development Team
Date: 2025-11-15
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from core.device_config import DeviceConfigHandler
from core.device_scanner import DeviceScanner


def validate_and_load_config():
    """
    Validate configuration and load settings for experiment.

    Returns:
        dict: Experiment configuration if valid, None otherwise
    """
    # Load configuration
    config_handler = DeviceConfigHandler()

    # Check if configuration is ready
    ready, issues = config_handler.is_ready_for_experiment()

    if not ready:
        print("=" * 60)
        print("CONFIGURATION VALIDATION FAILED")
        print("=" * 60)
        print("\nThe following issues were found:\n")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
        print("\nPlease run the Device Manager to configure:")
        print("  python device_manager_gui.py")
        print("=" * 60)
        return None

    # Export configuration for experiment
    exp_config = config_handler.export_for_experiment()

    # Print configuration summary
    print("=" * 60)
    print("DEVICE CONFIGURATION LOADED")
    print("=" * 60)
    print("\nDisplay Configuration:")
    print(f"  Control Monitor:      Display {exp_config['displays']['control']}")
    print(f"  Participant 1 Monitor: Display {exp_config['displays']['participant_1']}")
    print(f"  Participant 2 Monitor: Display {exp_config['displays']['participant_2']}")

    print("\nAudio Configuration:")
    print(f"  Participant 1 Output:  Device {exp_config['audio']['device_1_index']}")
    print(f"  Participant 2 Output:  Device {exp_config['audio']['device_2_index']}")
    print(f"  Audio Offset:          {exp_config['audio']['offset_ms']} ms")

    print("\nExperiment Settings:")
    print(f"  Baseline Length:       {exp_config['experiment']['baseline_length']} seconds")
    print(f"  Video Pairs CSV:       {exp_config['experiment']['csv_path']}")
    print("=" * 60)

    return exp_config


def verify_devices(exp_config):
    """
    Verify that configured devices are still available.

    Args:
        exp_config: Experiment configuration dictionary

    Returns:
        bool: True if all devices are available
    """
    print("\nVerifying device availability...")

    scanner = DeviceScanner()

    # Verify displays
    print("\n  Checking displays...")
    display_indices = [
        exp_config['displays']['control'],
        exp_config['displays']['participant_1'],
        exp_config['displays']['participant_2']
    ]

    valid, message = scanner.validate_display_config(display_indices)
    if not valid:
        print(f"    ✗ Display validation failed: {message}")
        return False
    print(f"    ✓ All displays available")

    # Verify audio output devices
    print("\n  Checking audio output devices...")
    audio_indices = [
        exp_config['audio']['device_1_index'],
        exp_config['audio']['device_2_index']
    ]

    valid, message = scanner.validate_audio_config(audio_indices, device_type='output')
    if not valid:
        print(f"    ✗ Audio validation failed: {message}")
        return False
    print(f"    ✓ All audio devices available")

    print("\n  Device verification complete ✓")
    return True


def show_device_details(exp_config):
    """
    Show detailed information about configured devices.

    Args:
        exp_config: Experiment configuration dictionary
    """
    scanner = DeviceScanner()

    print("\n" + "=" * 60)
    print("DETAILED DEVICE INFORMATION")
    print("=" * 60)

    # Display information
    print("\nConfigured Displays:")
    displays = scanner.scan_displays()

    for key, idx in exp_config['displays'].items():
        display = scanner.get_display_by_index(idx)
        if display:
            role = key.replace('_', ' ').title()
            print(f"\n  {role}:")
            print(f"    Index:      {display.index}")
            print(f"    Name:       {display.name}")
            print(f"    Resolution: {display.width}x{display.height}")
            print(f"    Position:   ({display.x}, {display.y})")
            print(f"    Primary:    {'Yes' if display.is_primary else 'No'}")

    # Audio device information
    print("\nConfigured Audio Devices:")

    p1_audio = scanner.get_audio_device_by_index(exp_config['audio']['device_1_index'])
    if p1_audio:
        print(f"\n  Participant 1 Output:")
        print(f"    Index:       {p1_audio.index}")
        print(f"    Name:        {p1_audio.name}")
        print(f"    Sample Rate: {p1_audio.default_samplerate} Hz")
        print(f"    Host API:    {p1_audio.hostapi}")
        print(f"    Default:     {'Yes' if p1_audio.is_default_output else 'No'}")

    p2_audio = scanner.get_audio_device_by_index(exp_config['audio']['device_2_index'])
    if p2_audio:
        print(f"\n  Participant 2 Output:")
        print(f"    Index:       {p2_audio.index}")
        print(f"    Name:        {p2_audio.name}")
        print(f"    Sample Rate: {p2_audio.default_samplerate} Hz")
        print(f"    Host API:    {p2_audio.hostapi}")
        print(f"    Default:     {'Yes' if p2_audio.is_default_output else 'No'}")

    print("\n" + "=" * 60)


def example_withbaseline_integration():
    """
    Example showing how to use configuration in WithBaseline.py

    This function demonstrates the code changes needed in WithBaseline.py
    to use the device configuration.
    """
    print("\n" + "=" * 60)
    print("INTEGRATION WITH WithBaseline.py")
    print("=" * 60)

    print("""
To integrate this configuration with WithBaseline.py, add the following
code at the beginning of the script (after imports):

    # === DEVICE CONFIGURATION INTEGRATION ===
    from core.device_config import DeviceConfigHandler

    # Load and validate configuration
    config_handler = DeviceConfigHandler()
    ready, issues = config_handler.is_ready_for_experiment()

    if not ready:
        print("Configuration not ready. Run: python device_manager_gui.py")
        sys.exit(1)

    # Export configuration
    exp_config = config_handler.export_for_experiment()

    # Replace hardcoded values
    audio_device_1_index = exp_config['audio']['device_1_index']
    audio_device_2_index = exp_config['audio']['device_2_index']
    audio_offset_ms = exp_config['audio']['offset_ms']
    baseline_length = exp_config['experiment']['baseline_length']
    csv_path = exp_config['experiment']['csv_path']

    # Display indices
    participant_1_display_idx = exp_config['displays']['participant_1']
    participant_2_display_idx = exp_config['displays']['participant_2']

Then, update the window creation code (around lines 127-128):

    # OLD CODE:
    # window1 = pyglet.window.Window(fullscreen=True, screen=screens[1])
    # window2 = pyglet.window.Window(fullscreen=True, screen=screens[2])

    # NEW CODE:
    window1 = pyglet.window.Window(
        fullscreen=True,
        screen=screens[participant_1_display_idx]
    )
    window2 = pyglet.window.Window(
        fullscreen=True,
        screen=screens[participant_2_display_idx]
    )

And update the CSV loading (around line 105):

    # OLD CODE:
    # csv_path = r"D:\\Projects\\DyadicSync\\video_pairs_extended.csv"

    # NEW CODE:
    # csv_path already loaded from configuration above
    """)

    print("=" * 60)


def main():
    """
    Main demonstration function.

    This shows the complete workflow of loading, validating, and using
    the device configuration.
    """
    print("\n" + "=" * 60)
    print("DYADICSYNC DEVICE CONFIGURATION INTEGRATION")
    print("=" * 60)

    # Step 1: Load and validate configuration
    print("\nStep 1: Loading configuration...")
    exp_config = validate_and_load_config()

    if exp_config is None:
        print("\n❌ Configuration not ready. Exiting.")
        return

    # Step 2: Verify devices are available
    print("\nStep 2: Verifying device availability...")
    if not verify_devices(exp_config):
        print("\n❌ Device verification failed. Please check connections.")
        return

    # Step 3: Show detailed device information
    show_device_details(exp_config)

    # Step 4: Show integration instructions
    example_withbaseline_integration()

    # All checks passed
    print("\n" + "=" * 60)
    print("✓ CONFIGURATION READY")
    print("=" * 60)
    print("\nAll devices configured and available!")
    print("You can now run the experiment with confidence.")
    print("\nNext steps:")
    print("  1. Review the integration instructions above")
    print("  2. Update WithBaseline.py with the integration code")
    print("  3. Run the experiment: python WithBaseline.py")
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
