"""
Experiment-level configuration that includes all trials, global settings, and metadata.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from .trial import Trial
from .question import Question


@dataclass
class ExperimentConfig:
    """
    Complete experiment configuration including all trials and global settings.

    This is the top-level configuration object that contains all parameters
    needed to run a DyadicSync experiment.

    Attributes:
        name: Experiment name/identifier
        description: Optional description of the experiment
        baseline_duration: Duration of initial baseline recording in seconds
        audio_device_p1: Audio device index for Participant 1
        audio_device_p2: Audio device index for Participant 2
        global_defaults: Default Question configuration used unless overridden per-trial
        trials: List of Trial objects defining the experiment sequence
        metadata: Additional metadata (creation date, version, etc.)
    """
    name: str = "DyadicSync Experiment"
    description: str = ""
    baseline_duration: float = 240.0  # seconds
    audio_device_p1: int = 9
    audio_device_p2: int = 7
    global_defaults: Question = field(default_factory=Question)
    trials: List[Trial] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Set creation timestamp if not already in metadata."""
        if 'created' not in self.metadata:
            self.metadata['created'] = datetime.now().isoformat()
        if 'version' not in self.metadata:
            self.metadata['version'] = '1.0'

    def add_trial(self, trial: Trial) -> None:
        """
        Add a trial to the experiment sequence.

        Args:
            trial: Trial object to add
        """
        # Auto-assign index if not set
        if trial.index is None or trial.index < 0:
            trial.index = len(self.trials)
        self.trials.append(trial)

    def remove_trial(self, index: int) -> None:
        """
        Remove a trial at the specified index and reindex remaining trials.

        Args:
            index: Index of trial to remove
        """
        if 0 <= index < len(self.trials):
            self.trials.pop(index)
            self._reindex_trials()

    def reorder_trial(self, from_index: int, to_index: int) -> None:
        """
        Move a trial from one position to another.

        Args:
            from_index: Current index of trial to move
            to_index: Target index for trial
        """
        if 0 <= from_index < len(self.trials) and 0 <= to_index < len(self.trials):
            trial = self.trials.pop(from_index)
            self.trials.insert(to_index, trial)
            self._reindex_trials()

    def duplicate_trial(self, index: int) -> Optional[Trial]:
        """
        Create a duplicate of the trial at specified index.

        Args:
            index: Index of trial to duplicate

        Returns:
            New Trial object or None if index invalid
        """
        if 0 <= index < len(self.trials):
            original = self.trials[index]
            duplicate = original.copy(new_index=len(self.trials))
            self.trials.append(duplicate)
            return duplicate
        return None

    def _reindex_trials(self) -> None:
        """Update trial indices to match their position in the list."""
        for i, trial in enumerate(self.trials):
            trial.index = i

    def get_enabled_trials(self) -> List[Trial]:
        """
        Get list of enabled trials only.

        Returns:
            List of trials where enabled=True
        """
        return [t for t in self.trials if t.enabled]

    def get_total_duration_estimate(self) -> float:
        """
        Calculate estimated total experiment duration in seconds.
        This is approximate as it doesn't include actual video durations.

        Returns:
            Estimated duration in seconds
        """
        duration = self.baseline_duration

        for trial in self.get_enabled_trials():
            duration += trial.get_estimated_duration()

        return duration

    def validate(self) -> tuple[bool, List[str]]:
        """
        Validate entire experiment configuration.

        Returns:
            Tuple of (valid: bool, error_messages: List[str])
        """
        errors = []

        # Check audio devices
        if self.audio_device_p1 < 0:
            errors.append("Invalid audio device for Participant 1")
        if self.audio_device_p2 < 0:
            errors.append("Invalid audio device for Participant 2")

        # Check baseline duration
        if self.baseline_duration < 0:
            errors.append("Baseline duration must be non-negative")

        # Check if we have trials
        enabled_trials = self.get_enabled_trials()
        if not enabled_trials:
            errors.append("No enabled trials in experiment")

        # Validate each trial
        for trial in self.trials:
            try:
                valid, msg = trial.validate_video_paths()
                if not valid:
                    errors.append(f"Trial {trial.index}: {msg}")
            except Exception as e:
                errors.append(f"Trial {trial.index}: {str(e)}")

        return (len(errors) == 0, errors)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'experiment_info': {
                'name': self.name,
                'description': self.description,
                'baseline_duration': self.baseline_duration,
                'audio_devices': {
                    'p1': self.audio_device_p1,
                    'p2': self.audio_device_p2
                },
                'metadata': self.metadata
            },
            'global_defaults': self.global_defaults.to_dict(),
            'trials': [trial.to_dict() for trial in self.trials]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ExperimentConfig':
        """Create ExperimentConfig instance from dictionary."""
        exp_info = data.get('experiment_info', {})

        # Extract audio devices
        audio_devices = exp_info.get('audio_devices', {'p1': 9, 'p2': 7})

        # Convert global_defaults
        global_defaults = Question.from_dict(data.get('global_defaults', {}))

        # Convert trials
        trials = [Trial.from_dict(t) for t in data.get('trials', [])]

        return cls(
            name=exp_info.get('name', 'DyadicSync Experiment'),
            description=exp_info.get('description', ''),
            baseline_duration=exp_info.get('baseline_duration', 240.0),
            audio_device_p1=audio_devices.get('p1', 9),
            audio_device_p2=audio_devices.get('p2', 7),
            global_defaults=global_defaults,
            trials=trials,
            metadata=exp_info.get('metadata', {})
        )

    @classmethod
    def create_from_csv(cls, csv_path: str, **kwargs) -> 'ExperimentConfig':
        """
        Create experiment configuration from legacy CSV file.

        Args:
            csv_path: Path to CSV file with VideoPath1 and VideoPath2 columns
            **kwargs: Additional parameters for ExperimentConfig

        Returns:
            ExperimentConfig instance populated from CSV
        """
        import pandas as pd

        # Read CSV
        df = pd.read_csv(csv_path)

        if 'VideoPath1' not in df.columns or 'VideoPath2' not in df.columns:
            raise ValueError("CSV must contain 'VideoPath1' and 'VideoPath2' columns")

        # Create trials from CSV rows
        trials = []
        for idx, row in df.iterrows():
            trial = Trial(
                index=idx,
                video_path_1=row['VideoPath1'],
                video_path_2=row['VideoPath2']
            )
            trials.append(trial)

        # Create config with trials
        config = cls(trials=trials, **kwargs)
        config.metadata['source_csv'] = csv_path
        config.metadata['imported'] = datetime.now().isoformat()

        return config
