"""
Question and rating scale configuration for participant responses.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ScaleType(Enum):
    """Types of rating scales available for questions."""
    LIKERT_7 = "likert_7"  # 7-point Likert scale (default)
    LIKERT_5 = "likert_5"  # 5-point Likert scale
    BINARY = "binary"       # Yes/No or similar binary choice
    CUSTOM = "custom"       # Custom scale with user-defined points


@dataclass
class Question:
    """
    Configuration for a rating question presented to participants.

    Attributes:
        text: The question text displayed to participants
        scale_type: Type of rating scale (7-point Likert by default)
        scale_points: Number of response options (auto-set based on scale_type)
        labels: Dictionary mapping scale values to text labels
                e.g., {1: "Awful", 4: "Neutral", 7: "Amazing"}
        p1_keys: List of keyboard keys for Participant 1 responses
        p2_keys: List of keyboard keys for Participant 2 responses
        timeout_seconds: Optional timeout for responses (None = unlimited)
    """
    text: str = "How did the video make you feel?"
    scale_type: ScaleType = ScaleType.LIKERT_7
    scale_points: int = 7
    labels: Dict[int, str] = field(default_factory=lambda: {
        1: "Awful",
        4: "Neutral",
        7: "Amazing"
    })
    p1_keys: List[str] = field(default_factory=lambda: ['1', '2', '3', '4', '5', '6', '7'])
    p2_keys: List[str] = field(default_factory=lambda: ['Q', 'W', 'E', 'R', 'T', 'Y', 'U'])
    timeout_seconds: Optional[float] = None

    def __post_init__(self):
        """Validate and auto-configure based on scale_type."""
        # Auto-set scale_points based on type if not manually specified
        if self.scale_type == ScaleType.LIKERT_7:
            self.scale_points = 7
        elif self.scale_type == ScaleType.LIKERT_5:
            self.scale_points = 5
        elif self.scale_type == ScaleType.BINARY:
            self.scale_points = 2

        # Validate that key lists match scale_points
        if len(self.p1_keys) != self.scale_points:
            raise ValueError(
                f"p1_keys length ({len(self.p1_keys)}) must match "
                f"scale_points ({self.scale_points})"
            )
        if len(self.p2_keys) != self.scale_points:
            raise ValueError(
                f"p2_keys length ({len(self.p2_keys)}) must match "
                f"scale_points ({self.scale_points})"
            )

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'text': self.text,
            'scale_type': self.scale_type.value,
            'scale_points': self.scale_points,
            'labels': self.labels,
            'p1_keys': self.p1_keys,
            'p2_keys': self.p2_keys,
            'timeout_seconds': self.timeout_seconds
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'Question':
        """Create Question instance from dictionary."""
        # Convert scale_type string back to enum with error handling
        if 'scale_type' in data:
            try:
                data['scale_type'] = ScaleType(data['scale_type'])
            except (ValueError, KeyError):
                # Default to LIKERT_7 if invalid scale type
                print(f"Warning: Invalid scale_type '{data['scale_type']}', defaulting to LIKERT_7")
                data['scale_type'] = ScaleType.LIKERT_7
        return cls(**data)

    def get_instruction_text(self, participant: int) -> str:
        """
        Generate instruction text for a specific participant.

        Args:
            participant: 1 or 2 for Participant 1 or 2

        Returns:
            Formatted instruction string with key mappings
        """
        keys = self.p1_keys if participant == 1 else self.p2_keys

        instruction = f"{self.text}\n\nParticipant {participant}: "

        if self.scale_type == ScaleType.BINARY:
            instruction += f"Press {keys[0]} or {keys[1]}"
        else:
            key_range = f"{keys[0]}-{keys[-1]}"
            instruction += f"Use keys {key_range}\n"

            # Add endpoint labels if they exist
            if 1 in self.labels and self.scale_points in self.labels:
                instruction += f"{1} = {self.labels[1]}, "
                if self.scale_points // 2 + 1 in self.labels:
                    midpoint = self.scale_points // 2 + 1
                    instruction += f"{midpoint} = {self.labels[midpoint]}, "
                instruction += f"{self.scale_points} = {self.labels[self.scale_points]}"

        return instruction
