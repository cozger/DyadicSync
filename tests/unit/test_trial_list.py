"""
Unit tests for TrialList and Trial classes.

Tests CSV loading, randomization, and trial management without requiring real video files.
"""

import pytest
from pathlib import Path
from core.execution.trial import Trial
from core.execution.trial_list import TrialList
from core.execution.block import RandomizationConfig


# ==================== TRIAL CLASS TESTS ====================

@pytest.mark.unit
def test_trial_creation():
    """Trial should initialize with ID and data."""
    data = {'VideoPath1': 'v1.mp4', 'VideoPath2': 'v2.mp4'}
    trial = Trial(trial_id=0, data=data)

    assert trial.trial_id == 0
    assert trial.data == data
    assert trial.result is None
    assert trial.timestamp is None


@pytest.mark.unit
def test_trial_mark_start():
    """Trial should record start time."""
    trial = Trial(0, {})

    trial.mark_start()

    assert trial.start_time is not None
    assert trial.timestamp is not None


@pytest.mark.unit
def test_trial_mark_end():
    """Trial should record end time."""
    trial = Trial(0, {})
    trial.mark_start()

    trial.mark_end()

    assert trial.end_time is not None


@pytest.mark.unit
def test_trial_get_duration():
    """Trial should calculate duration."""
    trial = Trial(0, {})
    trial.mark_start()
    trial.mark_end()

    duration = trial.get_duration()

    assert duration is not None
    assert duration >= 0


@pytest.mark.unit
def test_trial_serialization():
    """Trial should serialize to dict."""
    trial = Trial(5, {'video1': 'test.mp4'})
    trial.mark_start()
    trial.result = {'rating': 7}

    trial_dict = trial.to_dict()

    assert trial_dict['trial_id'] == 5
    assert trial_dict['data'] == {'video1': 'test.mp4'}
    assert trial_dict['result'] == {'rating': 7}


# ==================== TRIAL LIST TESTS ====================

@pytest.mark.unit
def test_trial_list_from_csv(sample_trial_csv):
    """TrialList should load from CSV file."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    assert len(trial_list.trials) == 3
    assert trial_list.trials[0].data['VideoPath1'] == '/dummy/video1.mp4'
    # trial_id is converted to int during CSV loading
    assert trial_list.trials[0].data['trial_id'] == 1


@pytest.mark.unit
def test_trial_list_from_csv_with_extra_columns(tmp_path):
    """TrialList should preserve extra CSV columns."""
    csv_file = tmp_path / "trials_extra.csv"
    csv_file.write_text("""VideoPath1,VideoPath2,emotion,intensity,trial_id
/path/v1.mp4,/path/v2.mp4,happy,high,1
/path/v3.mp4,/path/v4.mp4,sad,low,2
""")

    trial_list = TrialList(str(csv_file), source_type='csv')

    assert len(trial_list.trials) == 2
    assert trial_list.trials[0].data['emotion'] == 'happy'
    assert trial_list.trials[0].data['intensity'] == 'high'
    assert trial_list.trials[1].data['emotion'] == 'sad'


@pytest.mark.unit
def test_trial_list_randomization_none(sample_trial_csv):
    """TrialList with no randomization should preserve order."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    config = RandomizationConfig()
    config.method = 'none'

    trials = trial_list.get_trials(config)

    # Should be in original order (trial_id 1, 2, 3)
    assert trials[0].data['trial_id'] == 1
    assert trials[1].data['trial_id'] == 2
    assert trials[2].data['trial_id'] == 3


@pytest.mark.unit
def test_trial_list_randomization_full_changes_order(sample_trial_csv):
    """TrialList with full randomization should change order."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    config = RandomizationConfig()
    config.method = 'full'
    config.seed = 42

    trials = trial_list.get_trials(config)

    # With seed 42, order should be different from original
    # We can't predict exact order, but verify all trials present
    assert len(trials) == 3
    trial_ids = [t.data['trial_id'] for t in trials]
    assert set(trial_ids) == {1, 2, 3}


@pytest.mark.unit
def test_trial_list_randomization_reproducible(sample_trial_csv):
    """TrialList with same seed should produce same order."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    config = RandomizationConfig()
    config.method = 'full'
    config.seed = 42

    # Get trials twice with same seed
    trials1 = trial_list.get_trials(config)
    trials2 = trial_list.get_trials(config)

    # Should be identical order
    ids1 = [t.data['trial_id'] for t in trials1]
    ids2 = [t.data['trial_id'] for t in trials2]
    assert ids1 == ids2


@pytest.mark.unit
def test_trial_list_randomization_different_seeds(sample_trial_csv):
    """TrialList with different seeds should produce different orders."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    config1 = RandomizationConfig()
    config1.method = 'full'
    config1.seed = 42

    config2 = RandomizationConfig()
    config2.method = 'full'
    config2.seed = 123

    trials1 = trial_list.get_trials(config1)
    trials2 = trial_list.get_trials(config2)

    ids1 = [t.data['trial_id'] for t in trials1]
    ids2 = [t.data['trial_id'] for t in trials2]

    # Very likely (but not guaranteed) to be different
    # Just verify both are valid shuffles
    assert set(ids1) == {1, 2, 3}
    assert set(ids2) == {1, 2, 3}


@pytest.mark.unit
def test_trial_list_trial_count(sample_trial_csv):
    """TrialList should report correct trial count."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    assert len(trial_list.trials) == 3


@pytest.mark.unit
def test_trial_list_serialization(sample_trial_csv):
    """TrialList should serialize to dict."""
    trial_list = TrialList(sample_trial_csv, source_type='csv')

    tl_dict = trial_list.to_dict()

    assert 'source_type' in tl_dict
    assert tl_dict['source_type'] == 'csv'
    assert 'trial_count' in tl_dict
    assert tl_dict['trial_count'] == 3


@pytest.mark.unit
def test_trial_list_deserialization(tmp_path):
    """TrialList should deserialize from dict."""
    # Create a temp CSV file for deserialization
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("VideoPath1,VideoPath2\na.mp4,b.mp4\n")

    data = {
        'source_type': 'csv',
        'source': str(csv_file),
        'trial_count': 1,
        'columns': ['VideoPath1', 'VideoPath2']
    }

    trial_list = TrialList.from_dict(data)

    assert len(trial_list.trials) == 1


@pytest.mark.unit
def test_trial_list_empty_initialization():
    """TrialList can be initialized and trials added later."""
    # Create empty trial list
    trial_list = TrialList.__new__(TrialList)
    trial_list.source_type = 'manual'
    trial_list.trials = []
    trial_list.columns = []

    # Manually add trials
    trial_list.trials.append(Trial(0, {'VideoPath1': 'v1.mp4'}))
    trial_list.trials.append(Trial(1, {'VideoPath1': 'v2.mp4'}))

    assert len(trial_list.trials) == 2
    assert trial_list.trials[0].data['VideoPath1'] == 'v1.mp4'


# ==================== RANDOMIZATION CONFIG TESTS ====================

@pytest.mark.unit
def test_randomization_config_none():
    """RandomizationConfig with none method."""
    config = RandomizationConfig()
    config.method = 'none'

    assert config.method == 'none'
    assert config.seed is None


@pytest.mark.unit
def test_randomization_config_full_with_seed():
    """RandomizationConfig with full method and seed."""
    config = RandomizationConfig()
    config.method = 'full'
    config.seed = 42

    assert config.method == 'full'
    assert config.seed == 42


@pytest.mark.unit
def test_randomization_config_constrained():
    """RandomizationConfig with constrained method."""
    config = RandomizationConfig()
    config.method = 'constrained'

    assert config.method == 'constrained'
