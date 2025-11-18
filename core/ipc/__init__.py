"""
Inter-process communication for experiment execution.

This module provides message protocols and serialization helpers
for communicating between the GUI process (Tkinter) and the
experiment subprocess (Pyglet).
"""

from .messages import (
    MessageType,
    IPCMessage,
    ProgressMessage,
    ErrorMessage,
    CompleteMessage,
    LogMessage
)

from .serialization import ExperimentConfig

__all__ = [
    'MessageType',
    'IPCMessage',
    'ProgressMessage',
    'ErrorMessage',
    'CompleteMessage',
    'LogMessage',
    'ExperimentConfig'
]
