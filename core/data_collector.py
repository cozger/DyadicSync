"""
DataCollector class for DyadicSync Framework.

Handles data collection and CSV output.
"""

from typing import List, Dict, Any, Optional
import os
import pandas as pd
from datetime import datetime
from .execution.trial import Trial


class DataCollector:
    """
    Manages data collection and output for experiments.

    Responsibilities:
    - Collect trial data during execution
    - Save intermediate data (crash recovery)
    - Write final CSV output
    - Match output format from WithBaseline.py
    """

    def __init__(self, output_dir: str = ".", experiment_name: str = "experiment"):
        """
        Initialize data collector.

        Args:
            output_dir: Directory to save data files
            experiment_name: Experiment name for filename
        """
        self.output_directory = output_dir  # Use consistent name with timeline metadata
        self.output_dir = output_dir  # Keep for backward compatibility
        self.experiment_name = experiment_name
        self.trials_data: List[Dict[str, Any]] = []
        self.participant_data: List[Dict[str, Any]] = []

        # Subject/session info for filename generation
        self.subject_id: Optional[int] = None
        self.session: Optional[int] = None
        self.data_saving_enabled: bool = True

        # Create output directory if needed
        os.makedirs(output_dir, exist_ok=True)

        print(f"[DataCollector] Initialized (output: {output_dir}/{experiment_name})")

    def set_subject_info(self, subject_id: int, session: int):
        """
        Set subject and session information for filename generation.

        Args:
            subject_id: Subject identifier (0 to disable data saving)
            session: Session number (0 to disable data saving)
        """
        self.subject_id = subject_id
        self.session = session

        # Disable data saving if either is 0
        if subject_id == 0 or session == 0:
            self.data_saving_enabled = False
            print("[DataCollector] Data saving DISABLED (subject_id or session = 0)")
        else:
            self.data_saving_enabled = True
            print(f"[DataCollector] Subject: {subject_id}, Session: {session}")

    def _get_output_filename(self, suffix: str) -> str:
        """
        Generate output filename with subject/session info.

        Args:
            suffix: File suffix (e.g., 'trials', 'responses', 'data')

        Returns:
            Full path to output file
        """
        if self.subject_id is not None and self.session is not None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"sub-{self.subject_id:03d}_ses-{self.session:02d}_{timestamp}_{suffix}.csv"
        else:
            filename = f"{self.experiment_name}_{suffix}.csv"

        return os.path.join(self.output_directory, filename)

    def save_trial(self, trial: Trial):
        """
        Save individual trial data incrementally.

        Args:
            trial: Trial object with completed data
        """
        if not trial.result:
            print(f"[DataCollector] Warning: Trial {trial.trial_id} has no result data")
            return

        # Extract trial information
        trial_record = {
            'trial_id': trial.trial_id,
            'timestamp': trial.timestamp,
            'start_time': trial.start_time,
            'end_time': trial.end_time,
            'duration': trial.get_duration()
        }

        # Add input data (from trial list)
        trial_record.update(trial.data)

        # Add result data (from execution)
        if trial.result:
            trial_record.update(trial.result)

        self.trials_data.append(trial_record)

        # Save intermediate data for crash recovery
        self._save_intermediate()

        print(f"[DataCollector] Saved trial {trial.trial_id}")

    def add_participant_response(self, participant: str, trial_id: int, response: int, rt: float, **kwargs):
        """
        Add a participant response record.

        Args:
            participant: Participant identifier ('P1' or 'P2')
            trial_id: Trial ID
            response: Response value (e.g., rating 1-7)
            rt: Reaction time in seconds
            **kwargs: Additional data (video paths, metadata, etc.)
        """
        record = {
            'participant': participant,
            'trial_id': trial_id,
            'response': response,
            'rt': rt,
            'timestamp': datetime.now().isoformat()
        }
        record.update(kwargs)

        self.participant_data.append(record)

    def save_all(self):
        """
        Write complete dataset to CSV.

        Creates two files:
        - experiment_name_trials.csv: Trial-level data
        - experiment_name_responses.csv: Response-level data (one row per participant per trial)
        """
        # Check if data saving is enabled
        if not self.data_saving_enabled:
            print("[DataCollector] Data saving disabled - no files will be written")
            return

        # Save trial-level data
        if self.trials_data:
            trials_file = self._get_output_filename("trials")
            df_trials = pd.DataFrame(self.trials_data)
            df_trials.to_csv(trials_file, index=False)
            print(f"[DataCollector] Saved {len(self.trials_data)} trials to {trials_file}")

        # Save participant response data
        if self.participant_data:
            responses_file = self._get_output_filename("responses")
            df_responses = pd.DataFrame(self.participant_data)
            df_responses.to_csv(responses_file, index=False)
            print(f"[DataCollector] Saved {len(self.participant_data)} responses to {responses_file}")

        # Also save in legacy format matching WithBaseline.py if possible
        self._save_legacy_format()

    def _save_intermediate(self):
        """Save intermediate data for crash recovery."""
        if not self.data_saving_enabled:
            return

        if self.trials_data:
            intermediate_file = self._get_output_filename("intermediate")
            df = pd.DataFrame(self.trials_data)
            df.to_csv(intermediate_file, index=False)

    def _save_legacy_format(self):
        """
        Save in legacy format matching WithBaseline.py output.

        Format: participant, rating, trial_id, video1, video2, timestamp
        """
        if not self.data_saving_enabled or not self.participant_data:
            return

        legacy_file = self._get_output_filename("data")

        # Convert to legacy format
        legacy_data = []
        for record in self.participant_data:
            legacy_record = {
                'Participant': record.get('participant'),
                'Rating': record.get('response'),
                'VideoPair': record.get('trial_id'),
                'Video1': record.get('video1', record.get('VideoPath1', '')),
                'Video2': record.get('video2', record.get('VideoPath2', '')),
                'Timestamp': record.get('timestamp')
            }
            legacy_data.append(legacy_record)

        df_legacy = pd.DataFrame(legacy_data)
        df_legacy.to_csv(legacy_file, index=False)
        print(f"[DataCollector] Saved legacy format to {legacy_file}")

    def get_trial_count(self) -> int:
        """
        Get number of trials collected.

        Returns:
            Trial count
        """
        return len(self.trials_data)

    def get_response_count(self) -> int:
        """
        Get number of responses collected.

        Returns:
            Response count
        """
        return len(self.participant_data)

    def clear(self):
        """Clear all collected data."""
        self.trials_data.clear()
        self.participant_data.clear()
        print("[DataCollector] Data cleared")

    def __repr__(self):
        return (
            f"DataCollector("
            f"experiment='{self.experiment_name}', "
            f"trials={len(self.trials_data)}, "
            f"responses={len(self.participant_data)})"
        )
