"""
Phase Configuration Dialogs.

Provides dialogs for configuring each phase type:
- FixationPhase
- VideoPhase
- RatingPhase
- InstructionPhase
- BaselinePhase
"""

from .fixation_config_dialog import FixationConfigDialog
from .video_config_dialog import VideoConfigDialog
from .rating_config_dialog import RatingConfigDialog
from .instruction_config_dialog import InstructionConfigDialog
from .baseline_config_dialog import BaselineConfigDialog


def get_phase_config_dialog(phase_type_name: str):
    """
    Get the appropriate configuration dialog for a phase type.

    Args:
        phase_type_name: Phase class name (e.g., 'FixationPhase')

    Returns:
        Dialog class or None if not found
    """
    dialogs = {
        'FixationPhase': FixationConfigDialog,
        'VideoPhase': VideoConfigDialog,
        'RatingPhase': RatingConfigDialog,
        'InstructionPhase': InstructionConfigDialog,
        'BaselinePhase': BaselineConfigDialog
    }

    return dialogs.get(phase_type_name)


__all__ = [
    'FixationConfigDialog',
    'VideoConfigDialog',
    'RatingConfigDialog',
    'InstructionConfigDialog',
    'BaselineConfigDialog',
    'get_phase_config_dialog'
]
