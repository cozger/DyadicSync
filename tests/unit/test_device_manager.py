"""
Unit tests for DeviceManager.

Tests device management, window creation, validation, and configuration
without requiring actual hardware. Uses mocked DeviceScanner and Pyglet windows.
"""

import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from core.device_manager import DeviceManager


# ==================== INITIALIZATION TESTS ====================

@pytest.mark.unit
def test_device_manager_creation():
    """Test DeviceManager can be instantiated."""
    dm = DeviceManager()

    assert dm is not None
    assert dm.window1 is None
    assert dm.window2 is None
    assert dm._scanner is not None


@pytest.mark.unit
def test_device_manager_default_configuration():
    """Test DeviceManager has sensible default configuration."""
    dm = DeviceManager()

    # Check default display assignments
    assert dm.display_p1 == 1
    assert dm.display_p2 == 2

    # Check default audio assignments (from legacy config)
    assert dm.audio_device_p1 == 9
    assert dm.audio_device_p2 == 7


@pytest.mark.unit
def test_device_manager_configure():
    """Test configure() method sets device indices."""
    dm = DeviceManager()

    config = {
        'display_p1': 2,
        'display_p2': 3,
        'audio_device_p1': 5,
        'audio_device_p2': 6
    }

    dm.configure(config)

    assert dm.display_p1 == 2
    assert dm.display_p2 == 3
    assert dm.audio_device_p1 == 5
    assert dm.audio_device_p2 == 6


@pytest.mark.unit
def test_device_manager_configure_partial():
    """Test configure() with partial configuration keeps defaults."""
    dm = DeviceManager()

    original_audio_p1 = dm.audio_device_p1

    config = {
        'display_p1': 2,
        'display_p2': 3
        # audio devices not specified
    }

    dm.configure(config)

    assert dm.display_p1 == 2
    assert dm.display_p2 == 3
    assert dm.audio_device_p1 == original_audio_p1  # Should keep default


# ==================== WINDOW INITIALIZATION TESTS ====================

@pytest.mark.unit
@patch('pyglet.window.Window')
@patch('pyglet.display.get_display')
def test_device_manager_initialize_creates_windows(mock_get_display, mock_window_class,
                                                   mock_device_scanner):
    """Test that initialize() creates two windows."""
    # Mock pyglet display
    mock_screens = [MagicMock(), MagicMock(), MagicMock()]
    mock_get_display.return_value.get_screens.return_value = mock_screens

    # Create device manager and inject mock scanner
    dm = DeviceManager()
    dm._scanner = mock_device_scanner

    # Configure to use audio devices that exist in mock (indices 0-3)
    dm.audio_device_p1 = 1
    dm.audio_device_p2 = 2

    # Initialize
    dm.initialize()

    # Verify windows were created
    assert mock_window_class.call_count == 2

    # Verify windows are stored
    assert dm.window1 is not None
    assert dm.window2 is not None


@pytest.mark.unit
@patch('pyglet.window.Window')
@patch('pyglet.display.get_display')
def test_device_manager_initialize_uses_correct_screens(mock_get_display, mock_window_class,
                                                         mock_device_scanner):
    """Test that windows are created on correct screen indices."""
    # Mock pyglet display
    mock_screens = [MagicMock(), MagicMock(), MagicMock()]
    mock_get_display.return_value.get_screens.return_value = mock_screens

    dm = DeviceManager()
    dm._scanner = mock_device_scanner
    dm.display_p1 = 1
    dm.display_p2 = 2
    # Configure valid audio devices
    dm.audio_device_p1 = 1
    dm.audio_device_p2 = 2

    dm.initialize()

    # Check window creation calls
    calls = mock_window_class.call_args_list

    # First window should use screen at index 1
    assert calls[0][1]['screen'] == mock_screens[1]
    assert calls[0][1]['fullscreen'] == True

    # Second window should use screen at index 2
    assert calls[1][1]['screen'] == mock_screens[2]
    assert calls[1][1]['fullscreen'] == True


@pytest.mark.unit
def test_device_manager_initialize_fails_with_invalid_config(mock_device_scanner):
    """Test that initialize() raises error with invalid configuration."""
    dm = DeviceManager()
    dm._scanner = mock_device_scanner

    # Set invalid display indices
    dm.display_p1 = 99
    dm.display_p2 = 100

    # Should raise RuntimeError during validation
    with pytest.raises(RuntimeError, match="Device validation failed"):
        dm.initialize()


# ==================== VALIDATION TESTS ====================

@pytest.mark.unit
def test_device_manager_validate_valid_configuration(mock_device_scanner):
    """Test validation passes with valid configuration."""
    dm = DeviceManager()
    dm._scanner = mock_device_scanner

    # Populate displays and audio devices from scanner
    dm.displays = mock_device_scanner.scan_displays()
    dm.audio_devices = mock_device_scanner.scan_audio_devices()['all']

    # Set valid configuration
    dm.display_p1 = 1
    dm.display_p2 = 2
    dm.audio_device_p1 = 1  # Headphones (P1)
    dm.audio_device_p2 = 2  # Headphones (P2)

    errors = dm.validate()

    assert len(errors) == 0


@pytest.mark.unit
def test_device_manager_validate_invalid_display():
    """Test validation fails with invalid display index."""
    dm = DeviceManager()

    # Set displays manually (only 2 displays)
    from core.device_scanner import DisplayInfo
    dm.displays = [
        DisplayInfo(0, "D0", 1920, 1080, 0, 0, True),
        DisplayInfo(1, "D1", 1920, 1080, 1920, 0, False),
    ]

    # Request display index 5 (doesn't exist)
    dm.display_p1 = 1
    dm.display_p2 = 5

    errors = dm.validate()

    assert len(errors) > 0
    assert any("Display 5 not found" in e for e in errors)


@pytest.mark.unit
def test_device_manager_validate_invalid_audio():
    """Test validation fails with invalid audio device index."""
    dm = DeviceManager()

    # Set displays (valid)
    from core.device_scanner import DisplayInfo
    dm.displays = [
        DisplayInfo(0, "D0", 1920, 1080, 0, 0, True),
        DisplayInfo(1, "D1", 1920, 1080, 1920, 0, False),
        DisplayInfo(2, "D2", 1920, 1080, 3840, 0, False),
    ]

    # Set audio devices (indices 0, 1, 2)
    from core.device_scanner import AudioDeviceInfo
    dm.audio_devices = [
        AudioDeviceInfo(0, "Dev0", 0, 2, 44100, False, True, False, False, "WASAPI"),
        AudioDeviceInfo(1, "Dev1", 0, 2, 44100, False, True, False, False, "WASAPI"),
    ]

    # Request audio device index 99 (doesn't exist)
    dm.display_p1 = 1
    dm.display_p2 = 2
    dm.audio_device_p1 = 0
    dm.audio_device_p2 = 99

    errors = dm.validate()

    assert len(errors) > 0
    assert any("Audio device 99 not found" in e for e in errors)


# ==================== CLEANUP TESTS ====================

@pytest.mark.unit
@patch('sounddevice.stop')
def test_device_manager_cleanup_closes_windows(mock_sd_stop):
    """Test cleanup() closes windows and stops audio."""
    dm = DeviceManager()

    # Create mock windows
    mock_window1 = MagicMock()
    mock_window2 = MagicMock()
    dm.window1 = mock_window1
    dm.window2 = mock_window2

    # Cleanup
    dm.cleanup()

    # Verify windows were closed (check mocks before they were set to None)
    mock_window1.close.assert_called_once()
    mock_window2.close.assert_called_once()

    # Verify windows are set to None
    assert dm.window1 is None
    assert dm.window2 is None

    # Verify sounddevice.stop() was called
    mock_sd_stop.assert_called_once()


@pytest.mark.unit
@patch('sounddevice.stop')
def test_device_manager_cleanup_handles_no_windows(mock_sd_stop):
    """Test cleanup() handles case when windows don't exist."""
    dm = DeviceManager()

    # No windows created
    assert dm.window1 is None
    assert dm.window2 is None

    # Should not raise error
    dm.cleanup()

    # Should still call sd.stop()
    mock_sd_stop.assert_called_once()


# ==================== FACTORY METHOD TESTS ====================

@pytest.mark.unit
@patch('playback.synchronized_player.SynchronizedPlayer')
def test_create_video_player_for_participant_1(mock_player_class):
    """Test create_video_player() creates player for participant 1."""
    dm = DeviceManager()
    dm.window1 = MagicMock()
    dm.window2 = MagicMock()

    player = dm.create_video_player("/video.mp4", display_id=0, audio_device_id=5)

    # Verify SynchronizedPlayer was created
    mock_player_class.assert_called_once_with("/video.mp4", 5, dm.window1)


@pytest.mark.unit
@patch('playback.synchronized_player.SynchronizedPlayer')
def test_create_video_player_for_participant_2(mock_player_class):
    """Test create_video_player() creates player for participant 2."""
    dm = DeviceManager()
    dm.window1 = MagicMock()
    dm.window2 = MagicMock()

    player = dm.create_video_player("/video.mp4", display_id=1, audio_device_id=7)

    # Verify SynchronizedPlayer was created with window2
    mock_player_class.assert_called_once_with("/video.mp4", 7, dm.window2)


# ==================== TEST SUMMARY ====================

"""
Test Coverage Summary:
- Initialization: 4 tests
- Window creation: 3 tests
- Validation: 3 tests
- Cleanup: 2 tests
- Factory methods: 2 tests
Total: 14 tests

All tests use mocks and do not require actual hardware.
"""
