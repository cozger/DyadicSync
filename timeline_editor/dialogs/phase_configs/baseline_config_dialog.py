"""
Baseline Phase Configuration Dialog.

Configures BaselinePhase parameters:
- Duration (seconds)
- LSL markers (8888 start, 9999 end per CodeBook)
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from timeline_editor.dialogs.widgets import DurationPicker
from core.execution.phases.baseline_phase import BaselinePhase


class BaselineConfigDialog(FormDialog):
    """Dialog for configuring BaselinePhase."""

    def __init__(self, parent, phase: BaselinePhase):
        """
        Initialize baseline config dialog.

        Args:
            parent: Parent window
            phase: BaselinePhase to configure
        """
        self.phase = phase
        super().__init__(parent, "Configure Baseline Phase", width=450, height=250)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Duration
        self.duration_picker = DurationPicker(
            content_frame,
            label="Duration:",
            default_seconds=self.phase.duration,
            min_seconds=10,
            max_seconds=600,
            show_formatted=True
        )
        self.duration_picker.pack(fill=tk.X, pady=10)

        # Info about baseline
        info_frame = ttk.LabelFrame(content_frame, text="Baseline Recording Info", padding=10)
        info_frame.pack(fill=tk.X, pady=10)

        info_text = (
            "Baseline phase displays a fixation cross for the specified duration.\n\n"
            "LSL Markers:\n"
            "  • Start: 8888 (per CodeBook.txt)\n"
            "  • End: 9999\n\n"
            "Used for pre-experiment baseline EEG recording."
        )

        ttk.Label(
            info_frame,
            text=info_text,
            font=("Arial", 9),
            justify=tk.LEFT,
            wraplength=400
        ).pack()

    def _validate(self) -> List[str]:
        """Validate baseline config."""
        errors = []

        # Validate duration
        duration = self.duration_picker.get()
        if duration < 10:
            errors.append("Baseline duration should be at least 10 seconds")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect baseline config."""
        return {
            'duration': self.duration_picker.get()
        }
