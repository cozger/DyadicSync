"""
Unit tests for DeviceScanner.

Tests device detection, validation, and serialization without requiring actual hardware.
Uses mocked pyglet and sounddevice libraries to simulate hardware enumeration.
"""

import pytest
from unittest.mock import patch, MagicMock
from core.device_scanner import DeviceScanner, DisplayInfo, AudioDeviceInfo


# ==================== DISPLAY SCANNING TESTS ====================

@pytest.mark.unit
@patch('pyglet.canvas.get_display')
def test_scan_displays_returns_display_info_objects(mock_get_display, mock_pyglet_screens):
    """Test that scan_displays returns correct DisplayInfo objects."""
    # Mock pyglet to return fake screens
    mock_get_display.return_value.get_screens.return_value = mock_pyglet_screens

    scanner = DeviceScanner()
    displays = scanner.scan_displays()

    # Verify we got DisplayInfo objects
    assert len(displays) == 3
    assert all(isinstance(d, DisplayInfo) for d in displays)

    # Verify indices
    assert displays[0].index == 0
    assert displays[1].index == 1
    assert displays[2].index == 2

    # Verify first screen is primary
    assert displays[0].is_primary == True
    assert displays[1].is_primary == False
    assert displays[2].is_primary == False


@pytest.mark.unit
@patch('pyglet.canvas.get_display')
def test_scan_displays_caches_results(mock_get_display, mock_pyglet_screens):
    """Test that scan_displays caches results and doesn't re-scan."""
    mock_get_display.return_value.get_screens.return_value = mock_pyglet_screens

    scanner = DeviceScanner()

    # First scan
    displays1 = scanner.scan_displays()

    # Second scan should use cache
    displays2 = scanner.scan_displays()

    # Should return same objects
    assert displays1 is displays2

    # Pyglet should only be called once
    assert mock_get_display.call_count == 1


@pytest.mark.unit
@patch('pyglet.canvas.get_display')
def test_scan_displays_force_refresh(mock_get_display, mock_pyglet_screens):
    """Test that force_refresh bypasses cache."""
    mock_get_display.return_value.get_screens.return_value = mock_pyglet_screens

    scanner = DeviceScanner()

    # First scan
    displays1 = scanner.scan_displays()

    # Force refresh
    displays2 = scanner.scan_displays(force_refresh=True)

    # Should return different objects
    assert displays1 is not displays2

    # Pyglet should be called twice
    assert mock_get_display.call_count == 2


@pytest.mark.unit
@patch('pyglet.canvas.get_display')
def test_scan_displays_handles_no_pyglet(mock_get_display):
    """Test graceful handling when pyglet is not available."""
    # Simulate pyglet not available
    with patch('core.device_scanner.PYGLET_AVAILABLE', False):
        scanner = DeviceScanner()
        displays = scanner.scan_displays()

        # Should return empty list
        assert displays == []

        # Should not call pyglet
        mock_get_display.assert_not_called()


# ==================== AUDIO SCANNING TESTS ====================

@pytest.mark.unit
def test_scan_audio_devices_returns_correct_structure(mock_sounddevice_query):
    """Test that scan_audio_devices returns correct dictionary structure."""
    with patch('sounddevice.query_devices') as mock_query, \
         patch('sounddevice.default.device', [0, 1]), \
         patch('sounddevice.query_hostapis') as mock_hostapis:

        mock_query.return_value = mock_sounddevice_query
        mock_hostapis.return_value = {'name': 'WASAPI'}

        scanner = DeviceScanner()
        devices = scanner.scan_audio_devices()

        # Verify structure
        assert 'input' in devices
        assert 'output' in devices
        assert 'all' in devices

        # Verify all contains AudioDeviceInfo objects
        assert all(isinstance(d, AudioDeviceInfo) for d in devices['all'])

        # Verify categorization
        assert len(devices['output']) >= 2  # At least 2 output devices
        assert len(devices['input']) >= 1   # At least 1 input device


@pytest.mark.unit
def test_scan_audio_devices_sets_correct_properties(mock_sounddevice_query):
    """Test that AudioDeviceInfo objects have correct properties."""
    with patch('sounddevice.query_devices') as mock_query, \
         patch('sounddevice.default.device', [0, 1]), \
         patch('sounddevice.query_hostapis') as mock_hostapis:

        mock_query.return_value = mock_sounddevice_query
        mock_hostapis.return_value = {'name': 'WASAPI'}

        scanner = DeviceScanner()
        devices = scanner.scan_audio_devices()

        # Check first device (Built-in Audio)
        built_in = devices['all'][0]
        assert built_in.name == 'Built-in Audio'
        assert built_in.is_input == True
        assert built_in.is_output == True
        assert built_in.is_default_input == True
        assert built_in.is_default_output == False

        # Check output-only device
        headphones = devices['all'][1]
        assert headphones.is_input == False
        assert headphones.is_output == True


@pytest.mark.unit
def test_scan_audio_devices_caches_results(mock_sounddevice_query):
    """Test that audio device scanning caches results."""
    with patch('sounddevice.query_devices') as mock_query, \
         patch('sounddevice.default.device', [0, 1]), \
         patch('sounddevice.query_hostapis') as mock_hostapis:

        mock_query.return_value = mock_sounddevice_query
        mock_hostapis.return_value = {'name': 'WASAPI'}

        scanner = DeviceScanner()

        # First scan
        devices1 = scanner.scan_audio_devices()

        # Second scan should use cache
        devices2 = scanner.scan_audio_devices()

        # Should return same object
        assert devices1 is devices2

        # Should only query sounddevice once
        assert mock_query.call_count == 1


@pytest.mark.unit
@patch('sounddevice.query_devices')
def test_scan_audio_devices_handles_errors(mock_query):
    """Test graceful error handling when sounddevice fails."""
    mock_query.side_effect = Exception("sounddevice error")

    scanner = DeviceScanner()
    devices = scanner.scan_audio_devices()

    # Should return empty structure
    assert devices == {'input': [], 'output': [], 'all': []}


# ==================== DEVICE LOOKUP TESTS ====================

@pytest.mark.unit
def test_get_display_by_index_finds_display(mock_device_scanner):
    """Test getting display by index."""
    display = mock_device_scanner.get_display_by_index(1)

    assert display is not None
    assert display.index == 1
    assert display.name == "P1 Display"


@pytest.mark.unit
def test_get_display_by_index_returns_none_for_invalid(mock_device_scanner):
    """Test get_display_by_index returns None for invalid index."""
    display = mock_device_scanner.get_display_by_index(99)

    assert display is None


@pytest.mark.unit
def test_get_audio_device_by_index_finds_device(mock_device_scanner):
    """Test getting audio device by index."""
    device = mock_device_scanner.get_audio_device_by_index(1)

    assert device is not None
    assert device.index == 1
    assert device.name == "Headphones (P1)"


@pytest.mark.unit
def test_get_audio_device_by_index_returns_none_for_invalid(mock_device_scanner):
    """Test get_audio_device_by_index returns None for invalid index."""
    device = mock_device_scanner.get_audio_device_by_index(99)

    assert device is None


# ==================== SERIALIZATION TESTS ====================

@pytest.mark.unit
def test_display_info_to_dict():
    """Test DisplayInfo serialization to dictionary."""
    display = DisplayInfo(
        index=1,
        name="Test Display",
        width=1920,
        height=1080,
        x=0,
        y=0,
        is_primary=True
    )

    data = display.to_dict()

    assert data['index'] == 1
    assert data['name'] == "Test Display"
    assert data['width'] == 1920
    assert data['height'] == 1080
    assert data['is_primary'] == True


@pytest.mark.unit
def test_audio_device_info_to_dict():
    """Test AudioDeviceInfo serialization to dictionary."""
    device = AudioDeviceInfo(
        index=5,
        name="Test Device",
        max_input_channels=0,
        max_output_channels=2,
        default_samplerate=44100.0,
        is_input=False,
        is_output=True,
        is_default_input=False,
        is_default_output=True,
        hostapi="WASAPI"
    )

    data = device.to_dict()

    assert data['index'] == 5
    assert data['name'] == "Test Device"
    assert data['is_output'] == True
    assert data['is_input'] == False
    assert data['is_default_output'] == True
    assert data['hostapi'] == "WASAPI"


# ==================== STRING REPRESENTATION TESTS ====================

@pytest.mark.unit
def test_display_info_str_representation():
    """Test DisplayInfo string representation."""
    display = DisplayInfo(
        index=2,
        name="Monitor",
        width=2560,
        height=1440,
        x=1920,
        y=0,
        is_primary=False
    )

    str_repr = str(display)

    assert "Display 2" in str_repr
    assert "Monitor" in str_repr
    assert "2560x1440" in str_repr


@pytest.mark.unit
def test_audio_device_info_str_representation():
    """Test AudioDeviceInfo string representation."""
    device = AudioDeviceInfo(
        index=3,
        name="Speakers",
        max_input_channels=0,
        max_output_channels=2,
        default_samplerate=48000.0,
        is_input=False,
        is_output=True,
        is_default_input=False,
        is_default_output=True,
        hostapi="MME"
    )

    str_repr = str(device)

    assert "3" in str_repr
    assert "Speakers" in str_repr
    assert "Output" in str_repr
    assert "[Default Output]" in str_repr or "Default" in str_repr


# ==================== TEST SUMMARY ====================

"""
Test Coverage Summary:
- Display scanning: 4 tests
- Audio scanning: 4 tests
- Device lookup: 4 tests
- Serialization: 2 tests
- String representation: 2 tests
Total: 16 tests

All tests use mocks and do not require actual hardware.
"""
