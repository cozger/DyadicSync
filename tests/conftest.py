"""
Pytest configuration and fixtures for DyadicSync tests.

Provides common test fixtures and configuration for unit and integration tests.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Add project root to Python path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ==================== PYTEST CONFIGURATION ====================

def pytest_configure(config):
    """Add custom markers for test categorization."""
    config.addinivalue_line("markers", "unit: unit test (fast, no I/O)")
    config.addinivalue_line("markers", "integration: integration test (with mocks)")
    config.addinivalue_line("markers", "slow: slow test (real file I/O)")
    config.addinivalue_line("markers", "gui: GUI tests (visual)")
    config.addinivalue_line("markers", "hardware: requires real hardware (displays, audio)")


# ==================== MOCK FIXTURES ====================

@pytest.fixture
def mock_device_manager():
    """
    Mock DeviceManager for tests without hardware.

    Simulates 3 displays and 4 audio devices without requiring real hardware.
    """
    from unittest.mock import MagicMock

    mock_dm = MagicMock()
    mock_dm.window1 = MagicMock()
    mock_dm.window2 = MagicMock()
    mock_dm.display_p1 = 1
    mock_dm.display_p2 = 2
    mock_dm.audio_device_p1 = 9
    mock_dm.audio_device_p2 = 7

    # Mock displays
    mock_dm.displays = [
        MagicMock(index=0, name="Control", width=1920, height=1080),
        MagicMock(index=1, name="P1", width=1920, height=1080),
        MagicMock(index=2, name="P2", width=1920, height=1080),
    ]

    # Mock audio devices
    mock_dm.audio_devices = [
        MagicMock(index=i, name=f"Device {i}") for i in range(10)
    ]

    mock_dm.initialize = MagicMock()
    mock_dm.cleanup = MagicMock()
    mock_dm.validate = MagicMock(return_value=[])

    return mock_dm


@pytest.fixture
def mock_lsl_outlet():
    """
    Mock LSL StreamOutlet for marker testing.

    Captures all markers sent for verification.
    """
    class MockLSLOutlet:
        def __init__(self):
            self.markers_sent = []

        def push_sample(self, marker):
            """Record marker for later verification."""
            if isinstance(marker, list):
                self.markers_sent.extend(marker)
            else:
                self.markers_sent.append(marker)

        def get_markers(self):
            """Get all markers sent."""
            return self.markers_sent

    return MockLSLOutlet()


@pytest.fixture
def mock_data_collector(tmp_path):
    """
    Mock DataCollector that saves to temp directory.

    Args:
        tmp_path: pytest's temporary directory fixture
    """
    from core.data_collector import DataCollector

    return DataCollector(str(tmp_path), "test_experiment")


# ==================== TEST DATA FIXTURES ====================

@pytest.fixture
def sample_trial_csv(tmp_path):
    """
    Create sample trial CSV for testing.

    Returns:
        str: Path to CSV file
    """
    csv_file = tmp_path / "sample_trials.csv"
    csv_file.write_text("""VideoPath1,VideoPath2,trial_id
/dummy/video1.mp4,/dummy/video2.mp4,1
/dummy/video3.mp4,/dummy/video4.mp4,2
/dummy/video5.mp4,/dummy/video6.mp4,3
""")
    return str(csv_file)


@pytest.fixture
def sample_trial_data():
    """
    Sample trial data dictionary.

    Returns:
        dict: Trial data with video paths
    """
    return {
        'trial_id': 1,
        'trial_index': 1,
        'VideoPath1': '/path/to/video1.mp4',
        'VideoPath2': '/path/to/video2.mp4',
        'emotion': 'happy',
        'intensity': 'high'
    }


@pytest.fixture
def sample_timeline():
    """
    Create minimal valid Timeline for testing.

    Returns:
        Timeline: Timeline with one simple block
    """
    from core.execution.timeline import Timeline
    from core.execution.block import Block
    from core.execution.procedure import Procedure
    from core.execution.phases.fixation_phase import FixationPhase

    timeline = Timeline()

    block = Block("Test Block", block_type='simple')
    procedure = Procedure("Test Procedure")
    procedure.add_phase(FixationPhase(duration=1.0))

    block.procedure = procedure
    timeline.add_block(block)

    return timeline


# ==================== HELPER FUNCTIONS ====================

def assert_dict_subset(subset, full_dict):
    """
    Assert that all keys in subset exist in full_dict with matching values.

    Args:
        subset: Dictionary with expected key-value pairs
        full_dict: Dictionary to check against
    """
    for key, value in subset.items():
        assert key in full_dict, f"Key '{key}' not found in dict"
        assert full_dict[key] == value, f"Value mismatch for '{key}': expected {value}, got {full_dict[key]}"


def create_minimal_video_phase():
    """Create minimal VideoPhase for testing."""
    from core.execution.phases.video_phase import VideoPhase
    return VideoPhase(
        participant_1_video="{VideoPath1}",
        participant_2_video="{VideoPath2}"
    )


def create_minimal_rating_phase():
    """Create minimal RatingPhase for testing."""
    from core.execution.phases.rating_phase import RatingPhase
    return RatingPhase(
        question="How did you feel?",
        scale_min=1,
        scale_max=7
    )


# ==================== DEVICE TESTING FIXTURES ====================

@pytest.fixture
def mock_pyglet_screens():
    """
    Mock pyglet screen enumeration for display testing.

    Returns 3 fake screens simulating a typical experimental setup:
    - Screen 0: Control monitor (Primary)
    - Screen 1: Participant 1 display
    - Screen 2: Participant 2 display
    """
    mock_screens = [
        MagicMock(width=1920, height=1080, x=0, y=0),       # Screen 0 (Control)
        MagicMock(width=1920, height=1080, x=1920, y=0),    # Screen 1 (P1)
        MagicMock(width=1920, height=1080, x=3840, y=0),    # Screen 2 (P2)
    ]
    return mock_screens


@pytest.fixture
def mock_sounddevice_query():
    """
    Mock sounddevice.query_devices() for audio testing.

    Returns a list of fake audio devices matching the sounddevice format.
    """
    return [
        {
            'name': 'Built-in Audio',
            'max_input_channels': 2,
            'max_output_channels': 2,
            'default_samplerate': 48000.0,
            'hostapi': 0
        },
        {
            'name': 'Headphones (P1)',
            'max_input_channels': 0,
            'max_output_channels': 2,
            'default_samplerate': 44100.0,
            'hostapi': 0
        },
        {
            'name': 'Headphones (P2)',
            'max_input_channels': 0,
            'max_output_channels': 2,
            'default_samplerate': 44100.0,
            'hostapi': 0
        },
        {
            'name': 'Microphone',
            'max_input_channels': 1,
            'max_output_channels': 0,
            'default_samplerate': 44100.0,
            'hostapi': 0
        },
    ]


@pytest.fixture
def mock_display_info_list():
    """
    Create list of DisplayInfo objects for testing.

    Returns:
        list: List of DisplayInfo objects
    """
    from core.device_scanner import DisplayInfo

    return [
        DisplayInfo(
            index=0,
            name="Control Monitor",
            width=1920,
            height=1080,
            x=0,
            y=0,
            is_primary=True
        ),
        DisplayInfo(
            index=1,
            name="P1 Display",
            width=1920,
            height=1080,
            x=1920,
            y=0,
            is_primary=False
        ),
        DisplayInfo(
            index=2,
            name="P2 Display",
            width=1920,
            height=1080,
            x=3840,
            y=0,
            is_primary=False
        ),
    ]


@pytest.fixture
def mock_audio_device_info_list():
    """
    Create list of AudioDeviceInfo objects for testing.

    Returns:
        dict: Dictionary with 'input', 'output', 'all' lists
    """
    from core.device_scanner import AudioDeviceInfo

    all_devices = [
        AudioDeviceInfo(
            index=0,
            name="Built-in Audio",
            max_input_channels=2,
            max_output_channels=2,
            default_samplerate=48000.0,
            is_input=True,
            is_output=True,
            is_default_input=True,
            is_default_output=True,
            hostapi="WASAPI"
        ),
        AudioDeviceInfo(
            index=1,
            name="Headphones (P1)",
            max_input_channels=0,
            max_output_channels=2,
            default_samplerate=44100.0,
            is_input=False,
            is_output=True,
            is_default_input=False,
            is_default_output=False,
            hostapi="WASAPI"
        ),
        AudioDeviceInfo(
            index=2,
            name="Headphones (P2)",
            max_input_channels=0,
            max_output_channels=2,
            default_samplerate=44100.0,
            is_input=False,
            is_output=True,
            is_default_input=False,
            is_default_output=False,
            hostapi="WASAPI"
        ),
        AudioDeviceInfo(
            index=3,
            name="Microphone",
            max_input_channels=1,
            max_output_channels=0,
            default_samplerate=44100.0,
            is_input=True,
            is_output=False,
            is_default_input=False,
            is_default_output=False,
            hostapi="WASAPI"
        ),
    ]

    return {
        'input': [d for d in all_devices if d.is_input],
        'output': [d for d in all_devices if d.is_output],
        'all': all_devices
    }


@pytest.fixture
def mock_device_scanner(mock_display_info_list, mock_audio_device_info_list):
    """
    Create DeviceScanner with pre-populated mock data.

    This fixture creates a real DeviceScanner instance but overrides
    its cache with mock data, avoiding actual hardware detection.
    """
    from core.device_scanner import DeviceScanner

    scanner = DeviceScanner()

    # Inject mock data into cache
    scanner._displays_cache = mock_display_info_list
    scanner._audio_devices_cache = mock_audio_device_info_list

    return scanner
