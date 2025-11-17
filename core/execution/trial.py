"""
Trial class for DyadicSync Framework.

Represents a single trial execution.
"""

from typing import Dict, Any, Optional
import time


class Trial:
    """
    Represents a single trial execution.

    Contains:
    - trial_id: Unique identifier
    - data: Input data (from trial list)
    - result: Output data (collected during execution)
    - timestamp: When trial was executed
    """

    def __init__(self, trial_id: int, data: Dict[str, Any]):
        """
        Initialize trial.

        Args:
            trial_id: Unique trial identifier
            data: Trial data from trial list (e.g., {'video1': 'path.mp4', 'emotion': 'happy'})
        """
        self.trial_id = trial_id
        self.data = data  # Input data (from CSV)
        self.result: Optional[Dict[str, Any]] = None  # Output data (filled during execution)
        self.timestamp: Optional[float] = None  # Execution time
        self.start_time: Optional[float] = None  # Trial start time
        self.end_time: Optional[float] = None  # Trial end time

    def mark_start(self):
        """Mark the trial as started."""
        self.start_time = time.time()
        self.timestamp = self.start_time

    def mark_end(self):
        """Mark the trial as ended."""
        self.end_time = time.time()

    def get_duration(self) -> Optional[float]:
        """
        Get trial duration in seconds.

        Returns:
            Duration in seconds, or None if not completed
        """
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize trial to dictionary.

        Returns:
            Dictionary with all trial information
        """
        return {
            'trial_id': self.trial_id,
            'data': self.data,
            'result': self.result,
            'timestamp': self.timestamp,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'duration': self.get_duration()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Trial':
        """
        Deserialize trial from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Trial instance
        """
        trial = cls(
            trial_id=data['trial_id'],
            data=data.get('data', {})
        )
        trial.result = data.get('result')
        trial.timestamp = data.get('timestamp')
        trial.start_time = data.get('start_time')
        trial.end_time = data.get('end_time')
        return trial

    def __repr__(self):
        return f"Trial(id={self.trial_id}, data={len(self.data)} fields, completed={self.result is not None})"
