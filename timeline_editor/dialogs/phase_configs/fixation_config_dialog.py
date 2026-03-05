"""
Fixation Phase Configuration Dialog.

Configures FixationPhase parameters:
- Duration (seconds)
- Cross size/color (optional)
- LSL markers (start/end)
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from timeline_editor.dialogs.widgets import DurationPicker
from core.execution.phases.fixation_phase import FixationPhase
from gui.marker_widgets import MarkerBindingListWidget


class FixationConfigDialog(FormDialog):
    """Dialog for configuring FixationPhase."""

    def __init__(self, parent, phase: FixationPhase):
        """
        Initialize fixation config dialog.

        Args:
            parent: Parent window
            phase: FixationPhase to configure
        """
        self.phase = phase
        super().__init__(parent, "Configure Fixation Phase", width=500, height=400)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Duration
        self.duration_picker = DurationPicker(
            content_frame,
            label="Duration:",
            default_seconds=self.phase.duration,
            min_seconds=0.1,
            max_seconds=60.0,
            show_formatted=True
        )
        self.duration_picker.pack(fill=tk.X, pady=10)

        # Observer text (shown to non-viewer in turn-taking)
        observer_frame = ttk.LabelFrame(content_frame, text="Observer Text", padding=10)
        observer_frame.pack(fill=tk.X, pady=10)

        self.observer_text_var = tk.StringVar(value=self.phase.observer_text or "")
        ttk.Entry(observer_frame, textvariable=self.observer_text_var, width=40).pack(fill=tk.X, pady=2)

        ttk.Label(
            observer_frame,
            text="Text shown to the non-viewer (leave empty for cross on both screens)",
            font=("Arial", 8),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(5, 0))

        # LSL Event Markers (new MarkerBinding system)
        lsl_frame = ttk.LabelFrame(content_frame, text="LSL Event Markers", padding=10)
        lsl_frame.pack(fill=tk.X, pady=10)

        self.marker_bindings_widget = MarkerBindingListWidget(
            lsl_frame,
            bindings=self.phase.marker_bindings,
            available_events=['phase_start', 'phase_end'],
            on_change=None,  # Dialog handles via OK button
            label=""  # No label since it's in a frame already
        )
        self.marker_bindings_widget.pack(fill=tk.BOTH, expand=True)

    def _validate(self) -> List[str]:
        """Validate fixation config."""
        errors = []

        # Validate duration
        duration = self.duration_picker.get()
        if duration <= 0:
            errors.append("Duration must be greater than 0")

        # Marker validation is handled by MarkerBindingListWidget

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect fixation config."""
        # Update phase object directly with marker bindings
        self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()

        observer_text = self.observer_text_var.get().strip()

        return {
            'duration': self.duration_picker.get(),
            'observer_text': observer_text if observer_text else None
        }
