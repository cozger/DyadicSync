"""
Trial configuration data structure for individual experiment trials.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from .question import Question


@dataclass
class Trial:
    """
    Configuration for a single experiment trial.

    A trial consists of:
    1. Fixation cross display (pre-stimulus)
    2. Synchronized video playback for both participants
    3. Rating/question response collection

    Attributes:
        index: Trial number (0-indexed)
        video_path_1: Path to video file for Participant 1
        video_path_2: Path to video file for Participant 2
        fixation_duration: Duration of pre-trial fixation cross in seconds
        rating_timeout: Optional timeout for rating screen in seconds (None = unlimited)
        question_override: Optional Question object to override global question for this trial
        enabled: Whether this trial is active in the sequence
        notes: Optional notes/description for this trial
    """
    index: int
    video_path_1: str
    video_path_2: str
    fixation_duration: float = 3.0  # seconds
    rating_timeout: Optional[float] = None  # seconds, None = unlimited
    question_override: Optional[Question] = None
    enabled: bool = True
    notes: str = ""

    def __post_init__(self):
        """Validate trial parameters."""
        if self.fixation_duration < 0:
            raise ValueError("fixation_duration must be non-negative")

        if self.rating_timeout is not None and self.rating_timeout <= 0:
            raise ValueError("rating_timeout must be positive or None")

    def validate_video_paths(self) -> tuple[bool, str]:
        """
        Check if video files exist at specified paths.

        Returns:
            Tuple of (valid: bool, message: str)
        """
        try:
            path1 = Path(self.video_path_1)
            path2 = Path(self.video_path_2)
        except (ValueError, OSError, TypeError) as e:
            return False, f"Invalid path format: {str(e)}"

        try:
            if not path1.exists():
                return False, f"Video 1 not found: {self.video_path_1}"

            if not path2.exists():
                return False, f"Video 2 not found: {self.video_path_2}"

            # Check file extensions
            valid_extensions = {'.mp4', '.mpeg', '.avi', '.mov', '.mkv', '.webm'}
            if path1.suffix.lower() not in valid_extensions:
                return False, f"Invalid video format for Video 1: {path1.suffix}"

            if path2.suffix.lower() not in valid_extensions:
                return False, f"Invalid video format for Video 2: {path2.suffix}"

            return True, "Video paths valid"

        except Exception as e:
            return False, f"Error validating paths: {str(e)}"

    def get_estimated_duration(self, video_durations: Optional[tuple[float, float]] = None) -> float:
        """
        Calculate estimated total duration of this trial in seconds.

        Args:
            video_durations: Optional tuple of (video1_duration, video2_duration) in seconds
                            If not provided, returns fixation + rating only

        Returns:
            Total estimated duration in seconds
        """
        duration = self.fixation_duration

        if video_durations:
            # Use the longer of the two videos
            duration += max(video_durations[0], video_durations[1])

        # Rating screen has no fixed duration unless timeout is set
        if self.rating_timeout:
            duration += self.rating_timeout

        return duration

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'index': self.index,
            'video_path_1': self.video_path_1,
            'video_path_2': self.video_path_2,
            'fixation_duration': self.fixation_duration,
            'rating_timeout': self.rating_timeout,
            'question_override': self.question_override.to_dict() if self.question_override else None,
            'enabled': self.enabled,
            'notes': self.notes
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Trial':
        """Create Trial instance from dictionary."""
        # Handle question_override conversion
        if data.get('question_override'):
            data['question_override'] = Question.from_dict(data['question_override'])
        return cls(**data)

    def copy(self, new_index: Optional[int] = None) -> 'Trial':
        """
        Create a deep copy of this trial, optionally with a new index.

        Args:
            new_index: New index for the copied trial (None = keep same index)

        Returns:
            New Trial instance with same parameters (deep copied)
        """
        # Deep copy the question_override if it exists
        question_copy = None
        if self.question_override:
            question_copy = Question(
                text=self.question_override.text,
                scale_type=self.question_override.scale_type,
                scale_points=self.question_override.scale_points,
                labels=self.question_override.labels.copy(),  # Copy dict
                p1_keys=self.question_override.p1_keys.copy(),  # Copy list
                p2_keys=self.question_override.p2_keys.copy(),  # Copy list
                timeout_seconds=self.question_override.timeout_seconds
            )

        return Trial(
            index=new_index if new_index is not None else self.index,
            video_path_1=self.video_path_1,
            video_path_2=self.video_path_2,
            fixation_duration=self.fixation_duration,
            rating_timeout=self.rating_timeout,
            question_override=question_copy,  # Use deep copy
            enabled=self.enabled,
            notes=self.notes
        )
