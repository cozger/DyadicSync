"""
Concrete phase implementations for DyadicSync Framework.

Available phases:
- FixationPhase: Display fixation cross
- VideoPhase: Play synchronized videos
- RatingPhase: Collect participant ratings
- InstructionPhase: Display text instructions
- BaselinePhase: Baseline recording period
"""

from .fixation_phase import FixationPhase
from .video_phase import VideoPhase
from .rating_phase import RatingPhase
from .instruction_phase import InstructionPhase
from .baseline_phase import BaselinePhase

# Phase registry for deserialization
PHASE_TYPES = {
    'FixationPhase': FixationPhase,
    'VideoPhase': VideoPhase,
    'RatingPhase': RatingPhase,
    'InstructionPhase': InstructionPhase,
    'BaselinePhase': BaselinePhase,
}


def phase_from_dict(data: dict):
    """
    Create phase instance from dictionary.

    Args:
        data: Dictionary with 'type' key and phase-specific data

    Returns:
        Phase instance
    """
    phase_type = data.get('type')
    if phase_type not in PHASE_TYPES:
        raise ValueError(f"Unknown phase type: {phase_type}")

    phase_class = PHASE_TYPES[phase_type]
    return phase_class.from_dict(data)


__all__ = [
    'FixationPhase',
    'VideoPhase',
    'RatingPhase',
    'InstructionPhase',
    'BaselinePhase',
    'phase_from_dict',
]
