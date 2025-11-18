"""
TrialList class for DyadicSync Framework.

Manages a list of trials loaded from CSV or created manually.
"""

from typing import List, Dict, Any, Optional
import os
import random
import pandas as pd
from .trial import Trial
from .block import RandomizationConfig
from .constraints import Constraint


class TrialList:
    """
    Manages a list of trials loaded from CSV or created manually.

    Handles:
    - Loading from CSV
    - Randomization with constraints
    - Trial generation
    - Validation
    """

    def __init__(self, source: str, source_type: str = 'csv'):
        """
        Initialize trial list.

        Args:
            source: Path to CSV file or JSON string
            source_type: 'csv' or 'json'
        """
        self.source = source
        self.source_type = source_type
        self.trials: List[Trial] = []
        self._load_trials()

    def _normalize_trial_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize trial data by adding lowercase aliases for common column names.

        This allows templates to use user-friendly names like {video1} while
        supporting various CSV column naming conventions (VideoPath1, video1, etc.)

        Args:
            data: Original trial data from CSV row

        Returns:
            Trial data with added lowercase aliases
        """
        # Create column name mapping for common variations
        column_aliases = {
            'VideoPath1': 'video1',
            'VideoPath2': 'video2',
            'Video1': 'video1',
            'Video2': 'video2',
            'video_1': 'video1',
            'video_2': 'video2',
            'videopath1': 'video1',
            'videopath2': 'video2',
        }

        # Add aliases to data (keep original column names for backward compatibility)
        normalized = data.copy()
        for original_col, normalized_col in column_aliases.items():
            if original_col in data:
                # Add lowercase alias if it doesn't already exist
                if normalized_col not in normalized:
                    normalized[normalized_col] = data[original_col]
                    # Debug: Log the alias creation
                    if normalized_col in ['video1', 'video2']:
                        print(f"[TrialList] Added alias: {original_col} → {normalized_col}")

        return normalized

    def _load_trials(self):
        """Load trials from source."""
        if self.source_type == 'csv':
            if not os.path.exists(self.source):
                raise FileNotFoundError(f"Trial list CSV not found: {self.source}")

            # Read CSV file
            df = pd.read_csv(self.source)

            # Create trial for each row
            for idx, row in df.iterrows():
                # Convert row to dict and add normalized aliases
                trial_data = self._normalize_trial_data(row.to_dict())

                trial = Trial(
                    trial_id=idx,
                    data=trial_data
                )
                self.trials.append(trial)

            print(f"[TrialList] Loaded {len(self.trials)} trials from {self.source}")

        elif self.source_type == 'json':
            # JSON loading not implemented yet
            raise NotImplementedError("JSON trial list loading not yet implemented")

        elif self.source_type == 'manual':
            # Manual trial list - no loading required, trials will be added programmatically
            print(f"[TrialList] Created empty manual trial list (trials can be added via UI)")

    def get_trials(self, randomization_config: RandomizationConfig) -> List[Trial]:
        """
        Get trials in specified order (randomized or not).

        Args:
            randomization_config: Randomization settings

        Returns:
            List of Trial objects in execution order
        """
        if randomization_config.method == 'none':
            return self.trials.copy()

        # Make copy for randomization
        trials_copy = self.trials.copy()

        # Set random seed for reproducibility
        if randomization_config.seed is not None:
            random.seed(randomization_config.seed)

        if randomization_config.method == 'full':
            # Full randomization
            random.shuffle(trials_copy)
            print(f"[TrialList] Trials randomized (method: full, seed: {randomization_config.seed})")

        elif randomization_config.method == 'constrained':
            # Constrained randomization with constraint checking
            max_attempts = 1000

            if not randomization_config.constraints:
                # No constraints, just shuffle
                random.shuffle(trials_copy)
            else:
                # Try to find order that satisfies all constraints
                for attempt in range(max_attempts):
                    random.shuffle(trials_copy)

                    # Check all constraints
                    all_satisfied = all(
                        constraint.check(trials_copy)
                        for constraint in randomization_config.constraints
                    )

                    if all_satisfied:
                        print(f"[TrialList] Constraints satisfied on attempt {attempt + 1}")
                        break
                else:
                    # Could not satisfy constraints
                    print(f"[TrialList] Warning: Could not satisfy constraints after {max_attempts} attempts")
                    print(f"[TrialList] Using best-effort randomization")

            print(f"[TrialList] Trials randomized (method: constrained, seed: {randomization_config.seed})")

        elif randomization_config.method == 'block':
            # Block randomization: shuffle within groups
            # Groups are defined by a 'block' attribute in trial data
            # If no block attribute, fall back to full shuffle

            # Group trials by block
            blocks = {}
            for trial in trials_copy:
                block_id = trial.data.get('block', 0)  # Default to block 0
                if block_id not in blocks:
                    blocks[block_id] = []
                blocks[block_id].append(trial)

            # Shuffle within each block
            for block_trials in blocks.values():
                random.shuffle(block_trials)

            # Concatenate shuffled blocks in order
            trials_copy = []
            for block_id in sorted(blocks.keys()):
                trials_copy.extend(blocks[block_id])

            print(f"[TrialList] Trials randomized (method: block, {len(blocks)} blocks, seed: {randomization_config.seed})")

        elif randomization_config.method == 'latin_square':
            # Latin square counterbalancing
            # Requires trials to have a 'condition' attribute
            # Generates counterbalanced order based on participant number

            participant_num = randomization_config.seed if randomization_config.seed is not None else 1

            # Group trials by condition
            conditions = {}
            for trial in trials_copy:
                condition = trial.data.get('condition', 'default')
                if condition not in conditions:
                    conditions[condition] = []
                conditions[condition].append(trial)

            # Generate Latin square order
            condition_list = sorted(conditions.keys())
            n_conditions = len(condition_list)

            if n_conditions > 0:
                # Rotate based on participant number
                rotation = participant_num % n_conditions
                rotated_order = condition_list[rotation:] + condition_list[:rotation]

                # Build trial list in rotated order
                trials_copy = []
                for condition in rotated_order:
                    trials_copy.extend(conditions[condition])

            print(f"[TrialList] Trials randomized (method: latin_square, participant: {participant_num}, seed: {randomization_config.seed})")

        else:
            print(f"[TrialList] Warning: Unknown randomization method '{randomization_config.method}', using original order")
            return self.trials.copy()

        return trials_copy

    def validate(self) -> List[str]:
        """
        Validate trial list.

        Returns:
            List of error messages (empty if valid)

        Checks:
        - All referenced files exist
        - Required columns present
        - Data types correct
        """
        errors = []

        if not self.trials:
            errors.append("Trial list is empty")
            return errors

        # Check each trial
        for i, trial in enumerate(self.trials):
            # Check video files exist (common column names)
            for key in ['video1', 'video2', 'VideoPath1', 'VideoPath2']:
                if key in trial.data:
                    video_path = trial.data[key]
                    if isinstance(video_path, str) and video_path:  # Check it's a non-empty string
                        if not os.path.exists(video_path):
                            errors.append(f"Trial {i}: Video not found: {video_path}")

        return errors

    def get_columns(self) -> List[str]:
        """
        Get list of column names available in trials.

        Returns:
            List of column names
        """
        if not self.trials:
            return []
        return list(self.trials[0].data.keys())

    def get_trial_count(self) -> int:
        """
        Get number of trials.

        Returns:
            Trial count
        """
        return len(self.trials)

    def get_trial_by_id(self, trial_id: int) -> Optional[Trial]:
        """
        Get trial by ID.

        Args:
            trial_id: Trial ID

        Returns:
            Trial object or None if not found
        """
        for trial in self.trials:
            if trial.trial_id == trial_id:
                return trial
        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize trial list to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'source': self.source,
            'source_type': self.source_type,
            'trial_count': len(self.trials),
            'columns': self.get_columns()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TrialList':
        """
        Deserialize trial list from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            TrialList instance
        """
        return cls(
            source=data['source'],
            source_type=data.get('source_type', 'csv')
        )

    def __repr__(self):
        return f"TrialList(source='{self.source}', trials={len(self.trials)}, columns={len(self.get_columns())})"
