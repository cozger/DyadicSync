"""
Unit tests for DataCollector class.

Tests data collection and CSV output without requiring full experiment execution.
"""

import pytest
import pandas as pd
from pathlib import Path
from core.data_collector import DataCollector
from core.execution.trial import Trial


# ==================== INITIALIZATION TESTS ====================

@pytest.mark.unit
def test_data_collector_initialization(tmp_path):
    """DataCollector should create output directory."""
    output_dir = tmp_path / "output"

    collector = DataCollector(str(output_dir), "test_exp")

    assert output_dir.exists()
    assert collector.experiment_name == "test_exp"
    assert len(collector.trials_data) == 0
    assert len(collector.participant_data) == 0


@pytest.mark.unit
def test_data_collector_existing_directory(tmp_path):
    """DataCollector should work with existing directory."""
    output_dir = tmp_path / "existing"
    output_dir.mkdir()

    collector = DataCollector(str(output_dir), "test")

    assert output_dir.exists()


# ==================== PARTICIPANT RESPONSE TESTS ====================

@pytest.mark.unit
def test_add_participant_response(tmp_path):
    """DataCollector should record participant responses."""
    collector = DataCollector(str(tmp_path), "test")

    collector.add_participant_response(
        participant='P1',
        trial_id=1,
        response=7,
        rt=1.234,
        video1='v1.mp4',
        video2='v2.mp4'
    )

    assert len(collector.participant_data) == 1
    assert collector.participant_data[0]['participant'] == 'P1'
    assert collector.participant_data[0]['trial_id'] == 1
    assert collector.participant_data[0]['response'] == 7
    assert collector.participant_data[0]['rt'] == 1.234


@pytest.mark.unit
def test_add_multiple_participant_responses(tmp_path):
    """DataCollector should handle multiple responses per trial."""
    collector = DataCollector(str(tmp_path), "test")

    # P1 response
    collector.add_participant_response('P1', 1, 5, 1.0, video1='v1.mp4')

    # P2 response
    collector.add_participant_response('P2', 1, 6, 1.5, video1='v1.mp4')

    assert len(collector.participant_data) == 2
    assert collector.participant_data[0]['participant'] == 'P1'
    assert collector.participant_data[1]['participant'] == 'P2'


@pytest.mark.unit
def test_participant_response_with_metadata(tmp_path):
    """DataCollector should preserve extra metadata in responses."""
    collector = DataCollector(str(tmp_path), "test")

    collector.add_participant_response(
        'P1', 1, 7, 2.0,
        video1='v1.mp4',
        emotion='happy',
        condition='experimental'
    )

    record = collector.participant_data[0]
    assert record['video1'] == 'v1.mp4'
    assert record['emotion'] == 'happy'
    assert record['condition'] == 'experimental'


# ==================== TRIAL SAVING TESTS ====================

@pytest.mark.unit
def test_save_trial(tmp_path):
    """DataCollector should save trial data."""
    collector = DataCollector(str(tmp_path), "test")

    trial = Trial(0, {'video1': 'v1.mp4', 'video2': 'v2.mp4'})
    trial.mark_start()
    trial.mark_end()
    trial.result = {'p1_rating': 5, 'p2_rating': 6}

    collector.save_trial(trial)

    assert len(collector.trials_data) == 1
    assert collector.trials_data[0]['trial_id'] == 0
    assert collector.trials_data[0]['p1_rating'] == 5


@pytest.mark.unit
def test_save_multiple_trials(tmp_path):
    """DataCollector should accumulate trial data."""
    collector = DataCollector(str(tmp_path), "test")

    for i in range(3):
        trial = Trial(i, {'video': f'v{i}.mp4'})
        trial.mark_start()
        trial.mark_end()
        trial.result = {'rating': i + 1}
        collector.save_trial(trial)

    assert len(collector.trials_data) == 3
    assert collector.trials_data[2]['rating'] == 3


@pytest.mark.unit
def test_save_trial_creates_intermediate(tmp_path):
    """DataCollector should create intermediate save file."""
    collector = DataCollector(str(tmp_path), "test")

    trial = Trial(0, {'video': 'v.mp4'})
    trial.mark_start()
    trial.mark_end()
    trial.result = {'rating': 7}  # Must have result for save to proceed

    collector.save_trial(trial)

    # Check intermediate file was created
    intermediate_file = tmp_path / "test_intermediate.csv"
    assert intermediate_file.exists()


# ==================== CSV OUTPUT TESTS ====================

@pytest.mark.unit
def test_save_all_creates_files(tmp_path):
    """DataCollector should create CSV files on save_all()."""
    collector = DataCollector(str(tmp_path), "test")

    # Add some data
    collector.add_participant_response('P1', 1, 7, 1.0)

    trial = Trial(0, {'video': 'v.mp4'})
    trial.mark_start()
    trial.mark_end()
    trial.result = {'rating': 7}  # Must have result
    collector.save_trial(trial)

    collector.save_all()

    # Check files were created
    assert (tmp_path / "test_trials.csv").exists()
    assert (tmp_path / "test_responses.csv").exists()
    assert (tmp_path / "test_data.csv").exists()  # Legacy format


@pytest.mark.unit
def test_save_all_responses_format(tmp_path):
    """DataCollector should write responses in correct CSV format."""
    collector = DataCollector(str(tmp_path), "test")

    collector.add_participant_response('P1', 1, 7, 1.234, video1='v1.mp4', video2='v2.mp4')
    collector.add_participant_response('P2', 1, 5, 1.567, video1='v1.mp4', video2='v2.mp4')

    collector.save_all()

    # Read and verify CSV
    df = pd.read_csv(tmp_path / "test_responses.csv")

    assert len(df) == 2
    assert 'participant' in df.columns
    assert 'response' in df.columns
    assert 'rt' in df.columns
    assert df.iloc[0]['participant'] == 'P1'
    assert df.iloc[0]['response'] == 7
    assert df.iloc[1]['participant'] == 'P2'


@pytest.mark.unit
def test_save_all_legacy_format(tmp_path):
    """DataCollector should write legacy format matching WithBaseline.py."""
    collector = DataCollector(str(tmp_path), "test")

    collector.add_participant_response(
        'P1', 1, 7, 1.0,
        VideoPath1='v1.mp4',
        VideoPath2='v2.mp4'
    )

    collector.save_all()

    # Read legacy format CSV
    df = pd.read_csv(tmp_path / "test_data.csv")

    assert 'Participant' in df.columns
    assert 'Rating' in df.columns
    assert 'VideoPair' in df.columns
    assert 'Video1' in df.columns
    assert 'Video2' in df.columns
    assert df.iloc[0]['Participant'] == 'P1'
    assert df.iloc[0]['Rating'] == 7


@pytest.mark.unit
def test_save_all_trials_format(tmp_path):
    """DataCollector should write trial data correctly."""
    collector = DataCollector(str(tmp_path), "test")

    trial = Trial(0, {'video1': 'v1.mp4'})
    trial.mark_start()
    trial.mark_end()
    trial.result = {'rating': 7}

    collector.save_trial(trial)
    collector.save_all()

    # Read trials CSV
    df = pd.read_csv(tmp_path / "test_trials.csv")

    assert len(df) == 1
    assert 'trial_id' in df.columns
    assert 'rating' in df.columns
    assert df.iloc[0]['trial_id'] == 0
    assert df.iloc[0]['rating'] == 7


# ==================== EDGE CASES ====================

@pytest.mark.unit
def test_save_all_empty_data(tmp_path):
    """DataCollector should handle empty data gracefully."""
    collector = DataCollector(str(tmp_path), "test")

    # Save with no data
    collector.save_all()

    # Should not create files or should create empty files
    # (implementation dependent)


@pytest.mark.unit
def test_save_trial_without_result(tmp_path):
    """DataCollector should warn when trial has no result."""
    collector = DataCollector(str(tmp_path), "test")

    trial = Trial(0, {})
    trial.mark_start()
    trial.mark_end()
    # No result set

    collector.save_trial(trial)

    # Should warn but not crash
    # Data may or may not be saved depending on implementation
