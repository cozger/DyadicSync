"""
Unit tests for constraint classes.

Tests all constraint types and their integration with trial list randomization.
"""

import pytest
from core.execution.constraints import (
    Constraint,
    MaxConsecutiveConstraint,
    BalanceConstraint,
    NoRepeatConstraint,
    create_constraint
)
from core.execution.trial import Trial
from core.execution.trial_list import TrialList
from core.execution.block import RandomizationConfig
import tempfile
import os


class TestMaxConsecutiveConstraint:
    """Tests for MaxConsecutiveConstraint."""

    def test_max_consecutive_specific_value(self):
        """Test limiting consecutive trials with specific attribute value."""
        # Create constraint: max 2 consecutive "happy" trials
        constraint = MaxConsecutiveConstraint(attribute='emotion', value='happy', limit=2)

        # Valid sequence (2 happy, then break)
        trials_valid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'happy'}),
            Trial(2, {'emotion': 'sad'}),
            Trial(3, {'emotion': 'happy'}),
        ]
        assert constraint.check(trials_valid) is True

        # Invalid sequence (3 consecutive happy)
        trials_invalid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'happy'}),
            Trial(2, {'emotion': 'happy'}),  # Exceeds limit
            Trial(3, {'emotion': 'sad'}),
        ]
        assert constraint.check(trials_invalid) is False

    def test_max_consecutive_any_value(self):
        """Test limiting consecutive trials with any same value."""
        # Create constraint: max 2 consecutive of any emotion
        constraint = MaxConsecutiveConstraint(attribute='emotion', limit=2)

        # Valid sequence (max 2 consecutive of any value)
        trials_valid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'happy'}),
            Trial(2, {'emotion': 'sad'}),
            Trial(3, {'emotion': 'sad'}),
            Trial(4, {'emotion': 'neutral'}),
        ]
        assert constraint.check(trials_valid) is True

        # Invalid sequence (3 consecutive sad)
        trials_invalid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'sad'}),
            Trial(2, {'emotion': 'sad'}),
            Trial(3, {'emotion': 'sad'}),  # Exceeds limit
        ]
        assert constraint.check(trials_invalid) is False

    def test_max_consecutive_empty_list(self):
        """Test constraint with empty trial list."""
        constraint = MaxConsecutiveConstraint(attribute='emotion', value='happy', limit=2)
        assert constraint.check([]) is True

    def test_max_consecutive_serialization(self):
        """Test constraint serialization/deserialization."""
        constraint = MaxConsecutiveConstraint(attribute='emotion', value='happy', limit=2)

        # Serialize
        data = constraint.to_dict()
        assert data['type'] == 'max_consecutive'
        assert data['attribute'] == 'emotion'
        assert data['value'] == 'happy'
        assert data['limit'] == 2

        # Deserialize
        restored = Constraint.from_dict(data)
        assert isinstance(restored, MaxConsecutiveConstraint)
        assert restored.attribute == 'emotion'
        assert restored.value == 'happy'
        assert restored.limit == 2


class TestBalanceConstraint:
    """Tests for BalanceConstraint."""

    def test_balance_specific_values(self):
        """Test balancing specific attribute values."""
        # Create constraint: balance happy, sad, neutral
        constraint = BalanceConstraint(attribute='emotion', values=['happy', 'sad', 'neutral'])

        # Valid sequence (2 of each)
        trials_valid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'happy'}),
            Trial(2, {'emotion': 'sad'}),
            Trial(3, {'emotion': 'sad'}),
            Trial(4, {'emotion': 'neutral'}),
            Trial(5, {'emotion': 'neutral'}),
        ]
        assert constraint.check(trials_valid) is True

        # Invalid sequence (unbalanced counts)
        trials_invalid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'happy'}),
            Trial(2, {'emotion': 'happy'}),  # 3 happy
            Trial(3, {'emotion': 'sad'}),    # 1 sad
            Trial(4, {'emotion': 'neutral'}),
            Trial(5, {'emotion': 'neutral'}),
        ]
        assert constraint.check(trials_invalid) is False

    def test_balance_auto_detect_values(self):
        """Test balancing with auto-detected values."""
        # Create constraint: balance all emotions (auto-detect)
        constraint = BalanceConstraint(attribute='emotion')

        # Valid sequence (2 of each type present)
        trials_valid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'happy'}),
            Trial(2, {'emotion': 'sad'}),
            Trial(3, {'emotion': 'sad'}),
        ]
        assert constraint.check(trials_valid) is True

        # Invalid sequence (unbalanced)
        trials_invalid = [
            Trial(0, {'emotion': 'happy'}),
            Trial(1, {'emotion': 'sad'}),
            Trial(2, {'emotion': 'sad'}),
        ]
        assert constraint.check(trials_invalid) is False

    def test_balance_empty_list(self):
        """Test constraint with empty trial list."""
        constraint = BalanceConstraint(attribute='emotion')
        assert constraint.check([]) is True

    def test_balance_serialization(self):
        """Test constraint serialization/deserialization."""
        constraint = BalanceConstraint(attribute='emotion', values=['happy', 'sad'])

        # Serialize
        data = constraint.to_dict()
        assert data['type'] == 'balance'
        assert data['attribute'] == 'emotion'
        assert data['values'] == ['happy', 'sad']

        # Deserialize
        restored = Constraint.from_dict(data)
        assert isinstance(restored, BalanceConstraint)
        assert restored.attribute == 'emotion'
        assert restored.values == ['happy', 'sad']


class TestNoRepeatConstraint:
    """Tests for NoRepeatConstraint."""

    def test_no_repeat_within_window(self):
        """Test preventing repeats within specified window."""
        # Create constraint: no repeat within 3 trials
        constraint = NoRepeatConstraint(attribute='video1', within_trials=3)

        # Valid sequence (video1 repeats after 3+ trials)
        trials_valid = [
            Trial(0, {'video1': 'happy_01.mp4'}),
            Trial(1, {'video1': 'sad_01.mp4'}),
            Trial(2, {'video1': 'neutral_01.mp4'}),
            Trial(3, {'video1': 'happy_01.mp4'}),  # OK - 3 trials later
        ]
        assert constraint.check(trials_valid) is True

        # Invalid sequence (video1 repeats within 3 trials)
        trials_invalid = [
            Trial(0, {'video1': 'happy_01.mp4'}),
            Trial(1, {'video1': 'sad_01.mp4'}),
            Trial(2, {'video1': 'happy_01.mp4'}),  # Too soon!
        ]
        assert constraint.check(trials_invalid) is False

    def test_no_repeat_larger_window(self):
        """Test with larger window size."""
        constraint = NoRepeatConstraint(attribute='video1', within_trials=5)

        # Valid sequence
        trials_valid = [
            Trial(0, {'video1': 'A'}),
            Trial(1, {'video1': 'B'}),
            Trial(2, {'video1': 'C'}),
            Trial(3, {'video1': 'D'}),
            Trial(4, {'video1': 'E'}),
            Trial(5, {'video1': 'A'}),  # OK - 5 trials later
        ]
        assert constraint.check(trials_valid) is True

        # Invalid sequence
        trials_invalid = [
            Trial(0, {'video1': 'A'}),
            Trial(1, {'video1': 'B'}),
            Trial(2, {'video1': 'C'}),
            Trial(3, {'video1': 'A'}),  # Within window
        ]
        assert constraint.check(trials_invalid) is False

    def test_no_repeat_empty_list(self):
        """Test constraint with empty trial list."""
        constraint = NoRepeatConstraint(attribute='video1', within_trials=3)
        assert constraint.check([]) is True

    def test_no_repeat_serialization(self):
        """Test constraint serialization/deserialization."""
        constraint = NoRepeatConstraint(attribute='video1', within_trials=3)

        # Serialize
        data = constraint.to_dict()
        assert data['type'] == 'no_repeat'
        assert data['attribute'] == 'video1'
        assert data['within_trials'] == 3

        # Deserialize
        restored = Constraint.from_dict(data)
        assert isinstance(restored, NoRepeatConstraint)
        assert restored.attribute == 'video1'
        assert restored.within_trials == 3


class TestConstraintFactory:
    """Tests for constraint factory function."""

    def test_create_max_consecutive(self):
        """Test factory creates MaxConsecutiveConstraint."""
        constraint = create_constraint(
            'max_consecutive',
            attribute='emotion',
            value='happy',
            limit=2
        )
        assert isinstance(constraint, MaxConsecutiveConstraint)
        assert constraint.attribute == 'emotion'
        assert constraint.value == 'happy'
        assert constraint.limit == 2

    def test_create_balance(self):
        """Test factory creates BalanceConstraint."""
        constraint = create_constraint(
            'balance',
            attribute='emotion',
            values=['happy', 'sad']
        )
        assert isinstance(constraint, BalanceConstraint)
        assert constraint.attribute == 'emotion'
        assert constraint.values == ['happy', 'sad']

    def test_create_no_repeat(self):
        """Test factory creates NoRepeatConstraint."""
        constraint = create_constraint(
            'no_repeat',
            attribute='video1',
            within_trials=3
        )
        assert isinstance(constraint, NoRepeatConstraint)
        assert constraint.attribute == 'video1'
        assert constraint.within_trials == 3

    def test_create_unknown_type(self):
        """Test factory raises error for unknown type."""
        with pytest.raises(ValueError, match="Unknown constraint type"):
            create_constraint('invalid_type')


class TestConstrainedRandomization:
    """Integration tests for constrained randomization."""

    def create_test_csv(self, filename, data):
        """Helper to create temporary CSV file."""
        import pandas as pd
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)

    def test_constrained_randomization_max_consecutive(self):
        """Test constrained randomization with MaxConsecutive."""
        # Create temporary CSV with emotions
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            data = {
                'emotion': ['happy', 'happy', 'happy', 'sad', 'sad', 'sad', 'neutral', 'neutral']
            }
            self.create_test_csv(csv_path, data)

            # Load trial list
            trial_list = TrialList(csv_path)

            # Create randomization config with constraint
            config = RandomizationConfig()
            config.method = 'constrained'
            config.seed = 42
            config.constraints = [
                MaxConsecutiveConstraint(attribute='emotion', limit=2)
            ]

            # Get randomized trials
            randomized = trial_list.get_trials(config)

            # Check constraint is satisfied
            consecutive_count = 1
            prev_emotion = randomized[0].data['emotion']

            for i in range(1, len(randomized)):
                current_emotion = randomized[i].data['emotion']
                if current_emotion == prev_emotion:
                    consecutive_count += 1
                else:
                    consecutive_count = 1

                assert consecutive_count <= 2, f"Found {consecutive_count} consecutive {current_emotion}"
                prev_emotion = current_emotion

        finally:
            os.unlink(csv_path)

    def test_constrained_randomization_multiple_constraints(self):
        """Test constrained randomization with multiple constraints."""
        # Create temporary CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            data = {
                'emotion': ['happy', 'happy', 'sad', 'sad', 'neutral', 'neutral'],
                'video1': ['A', 'B', 'C', 'D', 'E', 'F']
            }
            self.create_test_csv(csv_path, data)

            # Load trial list
            trial_list = TrialList(csv_path)

            # Create config with multiple constraints
            config = RandomizationConfig()
            config.method = 'constrained'
            config.seed = 42
            config.constraints = [
                MaxConsecutiveConstraint(attribute='emotion', limit=1),
                BalanceConstraint(attribute='emotion', values=['happy', 'sad', 'neutral'])
            ]

            # Get randomized trials
            randomized = trial_list.get_trials(config)

            # Check max consecutive constraint
            for i in range(len(randomized) - 1):
                assert randomized[i].data['emotion'] != randomized[i + 1].data['emotion'], \
                    "Found consecutive same emotion"

            # Check balance constraint
            from collections import Counter
            emotion_counts = Counter(trial.data['emotion'] for trial in randomized)
            assert len(set(emotion_counts.values())) == 1, \
                f"Emotions not balanced: {emotion_counts}"

        finally:
            os.unlink(csv_path)

    def test_constrained_randomization_no_constraints(self):
        """Test constrained method without constraints (should just shuffle)."""
        # Create temporary CSV
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            data = {'value': [1, 2, 3, 4, 5]}
            self.create_test_csv(csv_path, data)

            # Load trial list
            trial_list = TrialList(csv_path)

            # Create config without constraints
            config = RandomizationConfig()
            config.method = 'constrained'
            config.seed = 42

            # Get randomized trials
            randomized = trial_list.get_trials(config)

            # Should be randomized (different from original order)
            original_values = [t.data['value'] for t in trial_list.trials]
            randomized_values = [t.data['value'] for t in randomized]

            # With seed 42, should be different order
            assert original_values != randomized_values

        finally:
            os.unlink(csv_path)


class TestBlockRandomization:
    """Tests for block randomization method."""

    def create_test_csv(self, filename, data):
        """Helper to create temporary CSV file."""
        import pandas as pd
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)

    def test_block_randomization(self):
        """Test block randomization preserves group structure."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            # Create CSV with block assignments
            data = {
                'block': [0, 0, 0, 1, 1, 1, 2, 2, 2],
                'value': ['A1', 'A2', 'A3', 'B1', 'B2', 'B3', 'C1', 'C2', 'C3']
            }
            self.create_test_csv(csv_path, data)

            # Load trial list
            trial_list = TrialList(csv_path)

            # Create randomization config
            config = RandomizationConfig()
            config.method = 'block'
            config.seed = 42

            # Get randomized trials
            randomized = trial_list.get_trials(config)

            # Extract blocks
            blocks = {0: [], 1: [], 2: []}
            for trial in randomized:
                block_id = trial.data['block']
                blocks[block_id].append(trial.data['value'])

            # Check blocks appear in order (0, then 1, then 2)
            current_block = -1
            for trial in randomized:
                assert trial.data['block'] >= current_block, "Blocks out of order"
                current_block = trial.data['block']

            # Check within-block randomization occurred (values shuffled within blocks)
            # Block 0 should contain A1, A2, A3 (possibly in different order)
            assert set(blocks[0]) == {'A1', 'A2', 'A3'}
            assert set(blocks[1]) == {'B1', 'B2', 'B3'}
            assert set(blocks[2]) == {'C1', 'C2', 'C3'}

        finally:
            os.unlink(csv_path)


class TestLatinSquareRandomization:
    """Tests for Latin square randomization method."""

    def create_test_csv(self, filename, data):
        """Helper to create temporary CSV file."""
        import pandas as pd
        df = pd.DataFrame(data)
        df.to_csv(filename, index=False)

    def test_latin_square_rotation(self):
        """Test Latin square produces rotated condition orders."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name

        try:
            # Create CSV with conditions
            data = {
                'condition': ['A', 'A', 'B', 'B', 'C', 'C'],
                'value': [1, 2, 3, 4, 5, 6]
            }
            self.create_test_csv(csv_path, data)

            # Load trial list
            trial_list = TrialList(csv_path)

            # Test different participant numbers (rotations)
            for participant_num in range(3):
                config = RandomizationConfig()
                config.method = 'latin_square'
                config.seed = participant_num

                randomized = trial_list.get_trials(config)

                # Extract condition order
                conditions_seen = []
                prev_condition = None
                for trial in randomized:
                    condition = trial.data['condition']
                    if condition != prev_condition:
                        conditions_seen.append(condition)
                        prev_condition = condition

                # Each participant should see different rotation
                if participant_num == 0:
                    assert conditions_seen == ['A', 'B', 'C']
                elif participant_num == 1:
                    assert conditions_seen == ['B', 'C', 'A']
                elif participant_num == 2:
                    assert conditions_seen == ['C', 'A', 'B']

        finally:
            os.unlink(csv_path)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
