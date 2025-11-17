"""
Dialog framework for Timeline Editor.

Provides base classes and reusable widgets for creating consistent dialogs.
"""

from .base_dialog import BaseDialog
from .widgets import (
    DurationPicker,
    FilePathWidget,
    TemplateVariableWidget,
    ScaleTypeSelector,
    KeyBindingWidget,
    ValidationLabel
)

__all__ = [
    'BaseDialog',
    'DurationPicker',
    'FilePathWidget',
    'TemplateVariableWidget',
    'ScaleTypeSelector',
    'KeyBindingWidget',
    'ValidationLabel'
]
