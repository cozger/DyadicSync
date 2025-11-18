"""
Message protocol for inter-process communication.

Defines message types and structures for communication between
GUI process (Tkinter) and experiment subprocess (Pyglet).
"""

from dataclasses import dataclass, asdict
from typing import Optional, Any, Dict
from enum import Enum


class MessageType(Enum):
    """Message types for IPC communication."""

    # GUI → Experiment commands
    PAUSE = "pause"
    RESUME = "resume"
    ABORT = "abort"

    # Experiment → GUI updates
    PROGRESS = "progress"
    ERROR = "error"
    COMPLETE = "complete"
    LOG = "log"
    LSL_READY = "lsl_ready"  # Subprocess LSL outlet created and ready


@dataclass
class IPCMessage:
    """
    Base message for inter-process communication.

    All messages can be serialized to dict for Queue transport.
    """
    type: MessageType
    data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize message to dictionary."""
        return {
            'type': self.type.value,
            'data': self.data
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> 'IPCMessage':
        """Deserialize message from dictionary."""
        return cls(
            type=MessageType(d['type']),
            data=d.get('data')
        )


@dataclass
class ProgressMessage(IPCMessage):
    """
    Progress update from experiment to GUI.

    Sent periodically to update progress dialog.
    """

    def __init__(self, current_block: int, total_blocks: int,
                 block_name: str, trial: Optional[int] = None,
                 total_trials: Optional[int] = None):
        """
        Create progress message.

        Args:
            current_block: Current block index (1-based)
            total_blocks: Total number of blocks
            block_name: Name of current block
            trial: Current trial within block (optional)
            total_trials: Total trials in current block (optional)
        """
        super().__init__(
            type=MessageType.PROGRESS,
            data={
                'current_block': current_block,
                'total_blocks': total_blocks,
                'block_name': block_name,
                'trial': trial,
                'total_trials': total_trials
            }
        )


@dataclass
class ErrorMessage(IPCMessage):
    """
    Error message from experiment to GUI.

    Sent when experiment encounters an error.
    """

    def __init__(self, error: str, traceback: str):
        """
        Create error message.

        Args:
            error: Error message string
            traceback: Full traceback string
        """
        super().__init__(
            type=MessageType.ERROR,
            data={
                'error': error,
                'traceback': traceback
            }
        )


@dataclass
class CompleteMessage(IPCMessage):
    """
    Completion signal with experiment summary.

    Sent when experiment completes successfully.
    """

    def __init__(self, trial_count: int, response_count: int,
                 output_dir: Optional[str], duration_seconds: float):
        """
        Create completion message.

        Args:
            trial_count: Number of trials completed
            response_count: Number of responses collected
            output_dir: Directory where data was saved (None if disabled)
            duration_seconds: Total experiment duration
        """
        super().__init__(
            type=MessageType.COMPLETE,
            data={
                'trial_count': trial_count,
                'response_count': response_count,
                'output_dir': output_dir,
                'duration_seconds': duration_seconds
            }
        )


@dataclass
class LogMessage(IPCMessage):
    """
    Log message from experiment to GUI.

    Allows experiment to send log messages to GUI console.
    """

    def __init__(self, message: str, level: str = "INFO"):
        """
        Create log message.

        Args:
            message: Log message text
            level: Log level (INFO, WARNING, ERROR)
        """
        super().__init__(
            type=MessageType.LOG,
            data={
                'message': message,
                'level': level
            }
        )


# Command message constructors (GUI → Experiment)

def pause_command() -> Dict[str, Any]:
    """Create a pause command message."""
    return IPCMessage(type=MessageType.PAUSE).to_dict()


def resume_command() -> Dict[str, Any]:
    """Create a resume command message."""
    return IPCMessage(type=MessageType.RESUME).to_dict()


def abort_command() -> Dict[str, Any]:
    """Create an abort command message."""
    return IPCMessage(type=MessageType.ABORT).to_dict()
