"""
Integration tests for device configuration and management workflow.

Tests the interaction between DeviceScanner, DeviceManager, and DeviceConfig
without requiring actual hardware.
"""

import pytest
from unittest.mock import patch, MagicMock
from core.device_scanner import DeviceScanner
from core.device_manager import DeviceManager
from core.device_config import DeviceConfigHandler


# ==================== SCANNER → MANAGER INTEGRATION ====================

@pytest.mark.integration
@patch('pyglet.window.Window')
@patch('pyglet.canvas.get_display')
def test_device_manager_uses_scanner_data(mock_get_display, mock_window_class,
                                          mock_device_scanner):
    """Test DeviceManager correctly uses DeviceScanner data."""
    # Mock pyglet
    mock_screens = [MagicMock(), MagicMock(), MagicMock()]
    mock_get_display.return_value.get_screens.return_value = mock_screens

    # Create manager and inject scanner
    dm = DeviceManager()
    dm._scanner = mock_device_scanner

    # Configure to use scanned devices
    dm.display_p1 = 1
    dm.display_p2 = 2
    dm.audio_device_p1 = 1  # From mock scanner
    dm.audio_device_p2 = 2  # From mock scanner

    # Initialize should work without errors
    dm.initialize()

    # Verify displays and audio were populated from scanner
    assert len(dm.displays) == 3
    assert len(dm.audio_devices) == 4  # 'all' devices from scanner


@pytest.mark.integration
def test_scanner_to_manager_display_configuration():
    """Test complete workflow: scan displays → configure manager → validate."""
    scanner = DeviceScanner()
    dm = DeviceManager()

    # Inject mock displays into scanner
    from core.device_scanner import DisplayInfo
    scanner._displays_cache = [
        DisplayInfo(0, "Control", 1920, 1080, 0, 0, True),
        DisplayInfo(1, "P1", 1920, 1080, 1920, 0, False),
        DisplayInfo(2, "P2", 1920, 1080, 3840, 0, False),
    ]

    # Inject mock audio devices
    from core.device_scanner import AudioDeviceInfo
    scanner._audio_devices_cache = {
        'input': [],
        'output': [
            AudioDeviceInfo(5, "Dev5", 0, 2, 44100, False, True, False, False, "WASAPI"),
            AudioDeviceInfo(7, "Dev7", 0, 2, 44100, False, True, False, False, "WASAPI"),
        ],
        'all': [
            AudioDeviceInfo(5, "Dev5", 0, 2, 44100, False, True, False, False, "WASAPI"),
            AudioDeviceInfo(7, "Dev7", 0, 2, 44100, False, True, False, False, "WASAPI"),
        ]
    }

    # Inject scanner into manager
    dm._scanner = scanner

    # Configure manager with scanned device indices
    dm.display_p1 = 1
    dm.display_p2 = 2
    dm.audio_device_p1 = 5
    dm.audio_device_p2 = 7

    # Populate manager with scanner data (normally done in initialize())
    dm.displays = scanner.scan_displays()
    dm.audio_devices = scanner.scan_audio_devices()['all']

    # Validate configuration
    errors = dm.validate()

    assert len(errors) == 0, f"Validation errors: {errors}"


# ==================== CONFIG → MANAGER INTEGRATION ====================

@pytest.mark.integration
@patch('pyglet.window.Window')
@patch('pyglet.canvas.get_display')
def test_device_config_to_manager_workflow(mock_get_display, mock_window_class,
                                           mock_device_scanner, tmp_path):
    """Test loading configuration from DeviceConfigHandler into DeviceManager."""
    # Mock pyglet
    mock_screens = [MagicMock(), MagicMock(), MagicMock()]
    mock_get_display.return_value.get_screens.return_value = mock_screens

    # Create config handler with temp file
    config_path = tmp_path / "device_config.json"
    config_handler = DeviceConfigHandler(str(config_path))

    # Set configuration
    config_handler.set('displays.participant_1_monitor', 1)
    config_handler.set('displays.participant_2_monitor', 2)
    config_handler.set('audio.participant_1_output', 5)
    config_handler.set('audio.participant_2_output', 7)

    # Create device manager
    dm = DeviceManager()
    dm._scanner = mock_device_scanner

    # Apply configuration from config handler
    dm.configure({
        'display_p1': config_handler.get('displays.participant_1_monitor'),
        'display_p2': config_handler.get('displays.participant_2_monitor'),
        'audio_device_p1': config_handler.get('audio.participant_1_output'),
        'audio_device_p2': config_handler.get('audio.participant_2_output'),
    })

    # Verify configuration was applied
    assert dm.display_p1 == 1
    assert dm.display_p2 == 2
    assert dm.audio_device_p1 == 5
    assert dm.audio_device_p2 == 7


# ==================== VALIDATION WORKFLOW ====================

@pytest.mark.integration
def test_end_to_end_validation_workflow():
    """Test complete validation workflow from scanning to validation."""
    # Create scanner
    scanner = DeviceScanner()

    # Inject mock data
    from core.device_scanner import DisplayInfo, AudioDeviceInfo
    scanner._displays_cache = [
        DisplayInfo(0, "D0", 1920, 1080, 0, 0, True),
        DisplayInfo(1, "D1", 1920, 1080, 1920, 0, False),
    ]
    scanner._audio_devices_cache = {
        'input': [],
        'output': [
            AudioDeviceInfo(3, "Audio3", 0, 2, 44100, False, True, False, False, "WASAPI"),
        ],
        'all': [
            AudioDeviceInfo(3, "Audio3", 0, 2, 44100, False, True, False, False, "WASAPI"),
        ]
    }

    # Create manager
    dm = DeviceManager()
    dm._scanner = scanner

    # Populate from scanner
    dm.displays = scanner.scan_displays()
    dm.audio_devices = scanner.scan_audio_devices()['all']

    # Test valid configuration
    dm.display_p1 = 0
    dm.display_p2 = 1
    dm.audio_device_p1 = 3
    dm.audio_device_p2 = 3  # Same device for both (valid)

    errors = dm.validate()
    assert len(errors) == 0

    # Test invalid configuration (missing display)
    dm.display_p2 = 5
    errors = dm.validate()
    assert len(errors) > 0
    assert any("Display 5 not found" in e for e in errors)


# ==================== ERROR HANDLING ====================

@pytest.mark.integration
def test_scanner_error_propagation():
    """Test that scanner errors are properly handled by manager."""
    scanner = DeviceScanner()
    dm = DeviceManager()
    dm._scanner = scanner

    # Inject empty device lists (simulating hardware detection failure)
    scanner._displays_cache = []
    scanner._audio_devices_cache = {'input': [], 'output': [], 'all': []}

    # Populate from scanner
    dm.displays = scanner.scan_displays()
    dm.audio_devices = scanner.scan_audio_devices()['all']

    # Validation should fail with helpful messages
    errors = dm.validate()

    assert len(errors) > 0
    assert any("not found" in e for e in errors)


@pytest.mark.integration
def test_configuration_mismatch_detection():
    """Test that configuration mismatches are detected."""
    scanner = DeviceScanner()
    dm = DeviceManager()
    dm._scanner = scanner

    # Scanner reports 2 displays
    from core.device_scanner import DisplayInfo
    scanner._displays_cache = [
        DisplayInfo(0, "D0", 1920, 1080, 0, 0, True),
        DisplayInfo(1, "D1", 1920, 1080, 1920, 0, False),
    ]

    # Manager configured for 3 displays
    dm.display_p1 = 1
    dm.display_p2 = 2  # Doesn't exist

    # Populate from scanner
    dm.displays = scanner.scan_displays()

    # Should detect mismatch
    errors = dm.validate()
    assert len(errors) > 0
    assert any("Display 2 not found" in e for e in errors)


# ==================== DEVICE INFO SERIALIZATION ROUND-TRIP ====================

@pytest.mark.integration
def test_display_info_serialization_round_trip():
    """Test DisplayInfo can be serialized and deserialized."""
    from core.device_scanner import DisplayInfo

    original = DisplayInfo(
        index=1,
        name="Test Display",
        width=2560,
        height=1440,
        x=1920,
        y=0,
        is_primary=False
    )

    # Serialize to dict
    data = original.to_dict()

    # Reconstruct from dict
    reconstructed = DisplayInfo(
        index=data['index'],
        name=data['name'],
        width=data['width'],
        height=data['height'],
        x=data['x'],
        y=data['y'],
        is_primary=data['is_primary']
    )

    # Should match
    assert reconstructed.index == original.index
    assert reconstructed.name == original.name
    assert reconstructed.width == original.width
    assert reconstructed.is_primary == original.is_primary


@pytest.mark.integration
def test_audio_device_info_serialization_round_trip():
    """Test AudioDeviceInfo can be serialized and deserialized."""
    from core.device_scanner import AudioDeviceInfo

    original = AudioDeviceInfo(
        index=5,
        name="Test Audio",
        max_input_channels=0,
        max_output_channels=2,
        default_samplerate=48000.0,
        is_input=False,
        is_output=True,
        is_default_input=False,
        is_default_output=True,
        hostapi="WASAPI"
    )

    # Serialize to dict
    data = original.to_dict()

    # Reconstruct from dict
    reconstructed = AudioDeviceInfo(
        index=data['index'],
        name=data['name'],
        max_input_channels=data['max_input_channels'],
        max_output_channels=data['max_output_channels'],
        default_samplerate=data['default_samplerate'],
        is_input=data['is_input'],
        is_output=data['is_output'],
        is_default_input=data['is_default_input'],
        is_default_output=data['is_default_output'],
        hostapi=data['hostapi']
    )

    # Should match
    assert reconstructed.index == original.index
    assert reconstructed.name == original.name
    assert reconstructed.is_output == original.is_output
    assert reconstructed.hostapi == original.hostapi


# ==================== TEST SUMMARY ====================

"""
Integration Test Coverage Summary:
- Scanner → Manager integration: 2 tests
- Config → Manager integration: 1 test
- Validation workflow: 1 test
- Error handling: 2 tests
- Serialization round-trip: 2 tests
Total: 8 tests

All tests use mocks and do not require actual hardware.
"""
