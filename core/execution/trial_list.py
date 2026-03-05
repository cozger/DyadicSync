"""
TrialList class for DyadicSync Framework.

Manages a list of trials loaded from CSV or created manually.
"""

from typing import List, Dict, Any, Optional
import os
import re
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
    - Viewer assignment for turn-taking conditions
    - Trial generation
    - Validation
    """

    def __init__(self, source: str, source_type: str = 'csv',
                 viewer_randomization_enabled: bool = True,
                 viewer_seed: Optional[int] = None,
                 video_id_regex: str = r'^[A-Za-z]+'):
        """
        Initialize trial list.

        Args:
            source: Path to CSV file or JSON string
            source_type: 'csv' or 'json'
            viewer_randomization_enabled: Whether to auto-assign viewers for turn_taking trials
            viewer_seed: Random seed for viewer assignment (None = random)
            video_id_regex: Regex pattern to strip from filename for video ID extraction
        """
        self.source = source
        self.source_type = source_type
        self.viewer_randomization_enabled = viewer_randomization_enabled
        self.viewer_seed = viewer_seed
        self.video_id_regex = video_id_regex
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
            # Video path aliases
            'VideoPath1': 'video1',
            'VideoPath2': 'video2',
            'Video1': 'video1',
            'Video2': 'video2',
            'video_1': 'video1',
            'video_2': 'video2',
            'videopath1': 'video1',
            'videopath2': 'video2',
            'video1_name': 'video1',
            'video2_name': 'video2',
            # Turn-taking condition aliases
            'Condition': 'condition',
            'CONDITION': 'condition',
            'trial_type': 'condition',
            'TrialType': 'condition',
            # Viewer assignment aliases
            'Viewer': 'viewer',
            'VIEWER': 'viewer',
            'viewer_id': 'viewer',
            'ViewerID': 'viewer',
            # Single video path aliases (lowercase convenience)
            'videopath': 'VideoPath',
            'VIDEOPATH': 'VideoPath',
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

        # Extract video IDs from filenames using configurable regex pattern
        # Example: C:\...\ACCEDE06283.mp4 with pattern ^[A-Za-z]+ → video_id = "06283"
        regex_pattern = self.video_id_regex
        def _extract_video_id(path):
            if not isinstance(path, str) or not path:
                return None
            name = os.path.splitext(os.path.basename(path))[0]
            video_id = re.sub(regex_pattern, '', name)
            return video_id if video_id else name

        # Single video path → video_id
        for key in ['VideoPath', 'videopath', 'VIDEOPATH']:
            if key in normalized and 'video_id' not in normalized:
                vid = _extract_video_id(normalized[key])
                if vid:
                    normalized['video_id'] = vid
                    print(f"[TrialList] Extracted video_id: {vid}")
                break

        # Dual video paths → video1_id, video2_id
        for key in ['video1', 'VideoPath1', 'Video1']:
            if key in normalized and 'video1_id' not in normalized:
                vid = _extract_video_id(normalized[key])
                if vid:
                    normalized['video1_id'] = vid
                break

        for key in ['video2', 'VideoPath2', 'Video2']:
            if key in normalized and 'video2_id' not in normalized:
                vid = _extract_video_id(normalized[key])
                if vid:
                    normalized['video2_id'] = vid
                break

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

            # Turn-taking support: Assign viewers for turn_taking trials if not pre-assigned
            self._assign_viewers_if_needed()

        elif self.source_type == 'json':
            # JSON loading not implemented yet
            raise NotImplementedError("JSON trial list loading not yet implemented")

        elif self.source_type == 'manual':
            # Manual trial list - no loading required, trials will be added programmatically
            print(f"[TrialList] Created empty manual trial list (trials can be added via UI)")

    def _assign_viewers_if_needed(self):
        """
        Assign viewer roles to turn_taking trials that don't have them assigned.

        Only runs when the CSV has a 'condition' column with turn_taking trials.
        For single-video CSVs (no condition column), this is a no-op — role
        information is derived from the BranchBlock variant at execution time.
        """
        # Check if any trial has a condition column
        has_condition = any(
            'condition' in trial.data and
            str(trial.data['condition']).lower().strip() in ('turn_taking', 'joint')
            for trial in self.trials
        )

        if not has_condition:
            print("[TrialList] No 'condition' column found - skipping viewer/mode assignment")
            return

        # Import here to avoid circular imports
        from utilities.viewer_randomizer import assign_viewers, compute_participant_modes

        # Extract trial data dictionaries
        trial_dicts = [trial.data for trial in self.trials]

        # Assign viewers to unassigned turn_taking trials (if enabled)
        if self.viewer_randomization_enabled:
            assign_viewers(trial_dicts, seed=self.viewer_seed)
        else:
            print("[TrialList] Viewer randomization disabled - skipping auto-assignment")

        # Compute participant modes (p1_mode, p2_mode, role_p1, role_p2)
        for i, trial in enumerate(self.trials):
            enriched = compute_participant_modes(trial.data)
            trial.data.update(enriched)

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

        # Create random instance — uses OS entropy when seed is None,
        # ensuring a different order each session
        rng = random.Random(randomization_config.seed)

        if randomization_config.method == 'full':
            # Full randomization
            rng.shuffle(trials_copy)
            print(f"[TrialList] Trials randomized (method: full, seed: {randomization_config.seed})")

        elif randomization_config.method == 'constrained':
            # Constrained randomization with constraint checking
            max_attempts = 1000

            if not randomization_config.constraints:
                rng.shuffle(trials_copy)
            else:
                # Try to find order that satisfies all constraints
                for attempt in range(max_attempts):
                    rng.shuffle(trials_copy)

                    # Check all constraints
                    all_satisfied = all(
                        constraint.check(trials_copy)
                        for constraint in randomization_config.constraints
                    )

                    if all_satisfied:
                        print(f"[TrialList] Constraints satisfied on attempt {attempt + 1}")
                        break
                else:
                    print(f"[TrialList] Warning: Could not satisfy constraints after {max_attempts} attempts")
                    print(f"[TrialList] Using best-effort randomization")

            print(f"[TrialList] Trials randomized (method: constrained, seed: {randomization_config.seed})")

        elif randomization_config.method == 'block':
            # Block randomization: shuffle within groups
            blocks = {}
            for trial in trials_copy:
                block_id = trial.data.get('block', 0)
                if block_id not in blocks:
                    blocks[block_id] = []
                blocks[block_id].append(trial)

            # Shuffle within each block
            for block_trials in blocks.values():
                rng.shuffle(block_trials)

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

        # Check if CSV has recognizable video path columns
        if self.trials:
            first_trial = self.trials[0]
            has_video1 = 'video1' in first_trial.data
            has_video2 = 'video2' in first_trial.data
            has_video_path = 'VideoPath' in first_trial.data

            if not has_video_path and (not has_video1 or not has_video2):
                available_columns = list(first_trial.data.keys())
                errors.append(
                    f"Warning: CSV columns may not be recognized. "
                    f"Expected 'VideoPath' column (single video) or 'video1'/'video2' columns, "
                    f"but found: {available_columns}. "
                    f"Video path templates may not resolve correctly."
                )

        # Check each trial
        for i, trial in enumerate(self.trials):
            # Check video files exist (common column names)
            for key in ['VideoPath', 'video1', 'video2', 'VideoPath1', 'VideoPath2']:
                if key in trial.data:
                    video_path = trial.data[key]
                    if isinstance(video_path, str) and video_path:
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
            'columns': self.get_columns(),
            'viewer_randomization_enabled': self.viewer_randomization_enabled,
            'viewer_seed': self.viewer_seed,
            'video_id_regex': self.video_id_regex
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
            source_type=data.get('source_type', 'csv'),
            viewer_randomization_enabled=data.get('viewer_randomization_enabled', True),
            viewer_seed=data.get('viewer_seed'),
            video_id_regex=data.get('video_id_regex', r'^[A-Za-z]+')
        )

    def __repr__(self):
        return f"TrialList(source='{self.source}', trials={len(self.trials)}, columns={len(self.get_columns())})"
