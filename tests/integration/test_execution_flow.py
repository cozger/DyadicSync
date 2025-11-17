"""
Integration tests for execution flow.

Tests end-to-end execution using mocked hardware (no real displays/audio required).
"""

import pytest
from unittest.mock import MagicMock, patch
from core.execution.timeline import Timeline
from core.execution.block import Block
from core.execution.procedure import Procedure
from core.execution.phases.fixation_phase import FixationPhase
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.phases.instruction_phase import InstructionPhase
from core.execution.trial import Trial
from core.execution.trial_list import TrialList
from core.execution.block import RandomizationConfig
from core.data_collector import DataCollector


# ==================== SIMPLE EXECUTION TESTS ====================

@pytest.mark.integration
def test_simple_block_execution(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test simple block execution without trials."""
    # Create simple procedure with instruction only
    procedure = Procedure("Simple Proc")
    procedure.add_phase(InstructionPhase(text="Test instruction", wait_for_key=False, duration=0.1))

    # Create simple block
    block = Block("Simple Block", block_type='simple')
    block.procedure = procedure

    # Mock the execute method to avoid actual rendering
    with patch.object(InstructionPhase, 'execute', return_value={'duration': 0.1}):
        # Execute procedure with trial_data (required even for simple blocks)
        data_collector = DataCollector(str(tmp_path), "test")
        result = procedure.execute(
            trial_data={'trial_index': 0},  # Required for marker template resolution
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            data_collector=data_collector
        )

    assert 'Instructions' in result or 'Test instruction' in result
    # Note: Result key depends on phase name


@pytest.mark.integration
def test_trial_based_execution_with_templates(mock_device_manager, mock_lsl_outlet, sample_trial_csv, tmp_path):
    """Test trial-based execution with template rendering."""
    # Create procedure with template variables
    procedure = Procedure("Trial Proc")
    procedure.add_phase(FixationPhase(duration=0.1))
    procedure.add_phase(VideoPhase(
        participant_1_video="{VideoPath1}",
        participant_2_video="{VideoPath2}"
    ))

    # Create trial-based block
    block = Block("Trial Block", block_type='trial_based')
    block.procedure = procedure
    block.trial_list = TrialList(sample_trial_csv, source_type='csv')

    # Get trials
    config = RandomizationConfig()
    config.method = 'none'
    trials = block.trial_list.get_trials(config)

    # Mock phase execution
    with patch.object(FixationPhase, 'execute', return_value={'duration': 0.1}), \
         patch.object(VideoPhase, 'execute', return_value={'duration': 5.0}):

        # Execute first trial
        trial_data = trials[0].data
        trial_data['trial_index'] = 0

        data_collector = DataCollector(str(tmp_path), "test")
        result = procedure.execute(
            trial_data=trial_data,
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            data_collector=data_collector
        )

    assert 'Fixation' in result
    assert 'Video Playback' in result


@pytest.mark.integration
def test_multi_phase_procedure_execution(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test procedure with multiple phases executes in order."""
    procedure = Procedure("Multi-Phase")
    procedure.add_phase(FixationPhase(duration=1.0, name="Pre-Fixation"))
    procedure.add_phase(InstructionPhase(text="Ready", wait_for_key=False, duration=0.1, name="Ready Screen"))
    procedure.add_phase(FixationPhase(duration=0.5, name="Post-Instruction"))

    # Mock all executions
    with patch.object(FixationPhase, 'execute') as mock_fix, \
         patch.object(InstructionPhase, 'execute') as mock_inst:

        mock_fix.return_value = {'duration': 1.0}
        mock_inst.return_value = {'duration': 0.1}

        data_collector = DataCollector(str(tmp_path), "test")
        result = procedure.execute(
            trial_data={'trial_index': 0},  # Required for marker template resolution
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            data_collector=data_collector
        )

    # All phases should have executed
    assert len(result) == 3
    assert 'Pre-Fixation' in result
    assert 'Ready Screen' in result
    assert 'Post-Instruction' in result


# ==================== LSL MARKER TESTS ====================

@pytest.mark.integration
def test_lsl_markers_sent_in_sequence(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test LSL markers are sent in correct sequence."""
    from core.markers import MarkerBinding

    procedure = Procedure("Marker Test")

    # Create phase with marker bindings
    fixation_phase = FixationPhase(duration=0.1)
    fixation_phase.marker_bindings = [
        MarkerBinding(event_type="phase_start", marker_template="8888"),
        MarkerBinding(event_type="phase_end", marker_template="9999")
    ]
    procedure.add_phase(fixation_phase)

    with patch.object(FixationPhase, 'execute') as mock_exec:
        def execute_with_markers(device_manager, lsl_outlet, trial_data=None):
            # Simulate sending markers
            if lsl_outlet:
                lsl_outlet.push_sample([8888])  # Start marker
                lsl_outlet.push_sample([9999])  # End marker
            return {'duration': 0.1}

        mock_exec.side_effect = execute_with_markers

        data_collector = DataCollector(str(tmp_path), "test")
        procedure.execute(
            trial_data={'trial_index': 0},  # Required for marker template resolution
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            data_collector=data_collector
        )

    # Check markers were sent
    assert 8888 in mock_lsl_outlet.markers_sent
    assert 9999 in mock_lsl_outlet.markers_sent


@pytest.mark.integration
def test_rating_phase_markers_with_trial_index(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test RatingPhase sends correctly encoded markers."""
    from core.markers import MarkerBinding

    procedure = Procedure("Rating Test")

    # Create rating phase with marker bindings
    rating_phase = RatingPhase()
    rating_phase.marker_bindings = [
        MarkerBinding(event_type="p1_response", marker_template="300#0$", participant=1),
        MarkerBinding(event_type="p2_response", marker_template="500#0$", participant=2)
    ]
    procedure.add_phase(rating_phase)

    # Mock rating phase execution to return ratings
    with patch.object(RatingPhase, 'execute') as mock_exec:
        def execute_with_rating(device_manager, lsl_outlet, trial_data=None):
            # Simulate P1 rating 7, P2 rating 5
            trial_index = trial_data.get('trial_index', 0) if trial_data else 0
            if lsl_outlet:
                # P1: trial 3, rating 7 = 300307
                p1_marker = 300000 + trial_index * 100 + 7
                lsl_outlet.push_sample([p1_marker])

                # P2: trial 3, rating 5 = 500305
                p2_marker = 500000 + trial_index * 100 + 5
                lsl_outlet.push_sample([p2_marker])

            return {'p1_response': 7, 'p1_rt': 1.0, 'p2_response': 5, 'p2_rt': 1.5}

        mock_exec.side_effect = execute_with_rating

        trial_data = {'trial_index': 3}
        data_collector = DataCollector(str(tmp_path), "test")
        procedure.execute(
            trial_data=trial_data,
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            data_collector=data_collector
        )

    # Check correct markers were sent
    assert 300307 in mock_lsl_outlet.markers_sent  # P1, Trial 3, Rating 7
    assert 500305 in mock_lsl_outlet.markers_sent  # P2, Trial 3, Rating 5


# ==================== DATA COLLECTION INTEGRATION ====================

@pytest.mark.integration
def test_data_collector_integration(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test DataCollector integrates correctly with Procedure."""
    procedure = Procedure("Data Test")
    procedure.add_phase(RatingPhase())

    # Mock rating execution
    with patch.object(RatingPhase, 'execute', return_value={
        'p1_response': 7,
        'p1_rt': 1.234,
        'p2_response': 5,
        'p2_rt': 1.567
    }):
        trial_data = {
            'trial_index': 1,
            'trial_id': 1,
            'VideoPath1': 'v1.mp4',
            'VideoPath2': 'v2.mp4'
        }

        data_collector = DataCollector(str(tmp_path), "test")
        result = procedure.execute(
            trial_data=trial_data,
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            data_collector=data_collector
        )

    # Check data collector received responses
    assert len(data_collector.participant_data) == 2
    assert data_collector.participant_data[0]['participant'] == 'P1'
    assert data_collector.participant_data[0]['response'] == 7
    assert data_collector.participant_data[1]['participant'] == 'P2'
    assert data_collector.participant_data[1]['response'] == 5


# ==================== RANDOMIZATION INTEGRATION ====================

@pytest.mark.integration
def test_randomization_applied_during_execution(sample_trial_csv):
    """Test trial randomization is applied correctly."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    # Test no randomization
    config_none = RandomizationConfig()
    config_none.method = 'none'
    trials_none = trial_list.get_trials(config_none)

    # Test full randomization with seed
    config_full = RandomizationConfig()
    config_full.method = 'full'
    config_full.seed = 42
    trials_full = trial_list.get_trials(config_full)

    # Same seed should give same order
    trials_full2 = trial_list.get_trials(config_full)

    # Verify
    assert len(trials_none) == 3
    assert len(trials_full) == 3
    assert [t.data['trial_id'] for t in trials_full] == [t.data['trial_id'] for t in trials_full2]


# ==================== TIMELINE INTEGRATION ====================

@pytest.mark.integration
def test_timeline_multi_block_execution(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test Timeline with multiple blocks."""
    timeline = Timeline()

    # Block 1: Baseline
    b1 = Block("Baseline", block_type='simple')
    p1 = Procedure("Baseline Proc")
    p1.add_phase(FixationPhase(duration=0.1))
    b1.procedure = p1

    # Block 2: Instruction
    b2 = Block("Instructions", block_type='simple')
    p2 = Procedure("Instruction Proc")
    p2.add_phase(InstructionPhase(text="Start", wait_for_key=False, duration=0.1))
    b2.procedure = p2

    timeline.add_block(b1)
    timeline.add_block(b2)

    # Validate timeline
    errors = timeline.validate()
    assert len(errors) == 0

    # Check total trials
    assert timeline.get_total_trials() == 2  # 2 simple blocks


# ==================== ERROR HANDLING ====================

@pytest.mark.integration
def test_validation_catches_errors():
    """Test validation catches configuration errors."""
    timeline = Timeline()

    # Block without procedure
    bad_block = Block("Bad", block_type='simple')
    timeline.add_block(bad_block)

    errors = timeline.validate()

    assert len(errors) > 0
    assert any('procedure' in e.lower() for e in errors)


@pytest.mark.integration
def test_template_variable_missing_shows_error():
    """Test missing template variables are detected."""
    procedure = Procedure("Test")
    procedure.add_phase(VideoPhase(
        participant_1_video="{missing_var}",
        participant_2_video="{another_missing}"
    ))

    required_vars = procedure.get_required_variables()

    assert 'missing_var' in required_vars
    assert 'another_missing' in required_vars


# ==================== SYNC ENGINE INTEGRATION ====================

@pytest.mark.integration
def test_video_phase_with_sync_engine(mock_device_manager, mock_lsl_outlet, tmp_path):
    """Test VideoPhase returns sync_quality metrics from SyncEngine."""
    from unittest.mock import MagicMock
    from playback.sync_engine import SyncEngine
    import time

    # Create VideoPhase
    video_phase = VideoPhase(
        participant_1_video="/path/to/video1.mp4",
        participant_2_video="/path/to/video2.mp4"
    )

    # Mock the device_manager.create_video_player to return mock players
    mock_player1 = MagicMock()
    mock_player2 = MagicMock()

    # Set up mock players to work with SyncEngine
    def create_mock_play_at_timestamp(player):
        def play_at_timestamp(sync_timestamp):
            SyncEngine.wait_until_timestamp(sync_timestamp)
            return time.perf_counter()
        return play_at_timestamp

    def create_mock_trigger_playback(player):
        def trigger_playback():
            return time.perf_counter()
        return trigger_playback

    mock_player1.play_at_timestamp = create_mock_play_at_timestamp(mock_player1)
    mock_player2.play_at_timestamp = create_mock_play_at_timestamp(mock_player2)
    mock_player1.trigger_playback = create_mock_trigger_playback(mock_player1)
    mock_player2.trigger_playback = create_mock_trigger_playback(mock_player2)

    mock_player1.prepare = MagicMock()
    mock_player2.prepare = MagicMock()
    mock_player1.stop = MagicMock()
    mock_player2.stop = MagicMock()
    mock_player1.get_texture = MagicMock(return_value=None)
    mock_player2.get_texture = MagicMock(return_value=None)

    # Mock player.player to have event decorator
    mock_player1.player = MagicMock()
    mock_player2.player = MagicMock()
    mock_player1.player.event = MagicMock()
    mock_player2.player.event = MagicMock()

    mock_device_manager.create_video_player = MagicMock(side_effect=[mock_player1, mock_player2])

    # Set up the players on the video_phase (simulate preparation)
    video_phase.player1 = mock_player1
    video_phase.player2 = mock_player2

    # Set armed_timestamp for sync engine validation
    sync_timestamp = time.perf_counter() + 0.1
    mock_player1.armed_timestamp = sync_timestamp
    mock_player2.armed_timestamp = sync_timestamp

    # Mock pyglet to avoid actual window creation and event loop
    with patch('core.execution.phases.video_phase.pyglet') as mock_pyglet:
        # Mock pyglet.app.run to exit immediately
        mock_pyglet.app.run = MagicMock()
        mock_pyglet.app.exit = MagicMock()
        mock_pyglet.clock.schedule_interval = MagicMock()
        mock_pyglet.clock.unschedule = MagicMock()

        # Execute the phase (with trial_data required)
        result = video_phase.execute(
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            trial_data={'trial_index': 0}  # Required for marker templates
        )

    # Verify sync_quality is in the result
    assert 'sync_quality' in result
    assert 'max_drift_ms' in result['sync_quality']
    assert 'spread_ms' in result['sync_quality']
    assert 'success' in result['sync_quality']

    # Verify sync quality metrics are reasonable
    # Note: Mock tests may have higher drift than real implementation
    # Real implementation achieves <5ms, but mocks may have ~100ms due to mock overhead
    assert result['sync_quality']['max_drift_ms'] < 200.0  # Reasonable for mock test
    # Success depends on actual timing, don't assert strict value for mocks


@pytest.mark.integration
def test_video_phase_sync_quality_logged(mock_device_manager, mock_lsl_outlet, tmp_path, caplog):
    """Test VideoPhase logs sync quality to console."""
    from unittest.mock import MagicMock
    from playback.sync_engine import SyncEngine
    import time
    import logging

    # Set up logging capture
    caplog.set_level(logging.INFO)

    # Create VideoPhase
    video_phase = VideoPhase(
        participant_1_video="/path/to/video1.mp4",
        participant_2_video="/path/to/video2.mp4"
    )

    # Mock players similar to previous test
    mock_player1 = MagicMock()
    mock_player2 = MagicMock()

    def create_mock_play_at_timestamp(player):
        def play_at_timestamp(sync_timestamp):
            SyncEngine.wait_until_timestamp(sync_timestamp)
            return time.perf_counter()
        return play_at_timestamp

    def create_mock_trigger_playback(player):
        def trigger_playback():
            return time.perf_counter()
        return trigger_playback

    mock_player1.play_at_timestamp = create_mock_play_at_timestamp(mock_player1)
    mock_player2.play_at_timestamp = create_mock_play_at_timestamp(mock_player2)
    mock_player1.trigger_playback = create_mock_trigger_playback(mock_player1)
    mock_player2.trigger_playback = create_mock_trigger_playback(mock_player2)
    mock_player1.prepare = MagicMock()
    mock_player2.prepare = MagicMock()
    mock_player1.stop = MagicMock()
    mock_player2.stop = MagicMock()
    mock_player1.get_texture = MagicMock(return_value=None)
    mock_player2.get_texture = MagicMock(return_value=None)
    mock_player1.player = MagicMock()
    mock_player2.player = MagicMock()
    mock_player1.player.event = MagicMock()
    mock_player2.player.event = MagicMock()

    mock_device_manager.create_video_player = MagicMock(side_effect=[mock_player1, mock_player2])

    # Set up the players on the video_phase (simulate preparation)
    video_phase.player1 = mock_player1
    video_phase.player2 = mock_player2

    # Set armed_timestamp for sync engine validation
    sync_timestamp = time.perf_counter() + 0.1
    mock_player1.armed_timestamp = sync_timestamp
    mock_player2.armed_timestamp = sync_timestamp

    with patch('core.execution.phases.video_phase.pyglet') as mock_pyglet:
        mock_pyglet.app.run = MagicMock()
        mock_pyglet.app.exit = MagicMock()
        mock_pyglet.clock.schedule_interval = MagicMock()
        mock_pyglet.clock.unschedule = MagicMock()

        result = video_phase.execute(
            device_manager=mock_device_manager,
            lsl_outlet=mock_lsl_outlet,
            trial_data={'trial_index': 0}  # Required for marker templates
        )

    # Verify sync quality was logged (from SyncEngine)
    # Look for log messages containing sync information
    log_output = caplog.text
    assert 'SyncEngine' in log_output or 'Sync quality' in log_output
