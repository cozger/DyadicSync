"""
Instruction Phase Configuration Dialog.

Configures InstructionPhase parameters:
- Instruction text (multiline)
- Wait for key press (yes/no)
- Continue key
- Display duration (if not waiting for key)
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from timeline_editor.dialogs.widgets import KeyBindingWidget, DurationPicker
from core.execution.phases.instruction_phase import InstructionPhase
from gui.marker_widgets import MarkerBindingListWidget


class InstructionConfigDialog(FormDialog):
    """Dialog for configuring InstructionPhase."""

    def __init__(self, parent, phase: InstructionPhase):
        """
        Initialize instruction config dialog.

        Args:
            parent: Parent window
            phase: InstructionPhase to configure
        """
        self.phase = phase
        super().__init__(parent, "Configure Instruction Phase", width=500, height=450)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Instruction text
        self.add_text_area(
            content_frame,
            "Instruction Text:",
            "text",
            default=self.phase.text,
            height=8
        )

        # Wait for key option
        wait_frame = ttk.LabelFrame(content_frame, text="Display Mode", padding=10)
        wait_frame.pack(fill=tk.X, pady=10)

        self.add_checkbox(
            wait_frame,
            "Wait for key press to continue",
            "wait_for_key",
            default=self.phase.wait_for_key
        )

        # Continue key info (hardcoded to SPACE)
        key_info_frame = ttk.Frame(wait_frame)
        key_info_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            key_info_frame,
            text="Continue Key: SPACE (hardcoded)",
            font=("Arial", 9),
            foreground="gray"
        ).pack(anchor=tk.W, padx=5)

        # Display duration (if not waiting)
        duration_frame = ttk.Frame(wait_frame)
        duration_frame.pack(fill=tk.X, pady=5)

        ttk.Label(duration_frame, text="If not waiting, auto-advance after:", font=("Arial", 9)).pack(anchor=tk.W, pady=2)

        self.duration_picker = DurationPicker(
            duration_frame,
            label="Duration:",
            default_seconds=self.phase.duration if self.phase.duration else 5.0,
            min_seconds=0.5,
            max_seconds=60.0,
            show_formatted=True
        )
        self.duration_picker.pack(fill=tk.X)

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

        # Info
        info_label = ttk.Label(
            content_frame,
            text="Note: Instructions are shown on both participant screens",
            font=("Arial", 8),
            foreground="gray"
        )
        info_label.pack(pady=5)

    def _validate(self) -> List[str]:
        """Validate instruction config."""
        errors = []

        # Validate text
        text = self.form_widgets['text'].get("1.0", tk.END).strip()
        if not text:
            errors.append("Instruction text is required")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect instruction config."""
        wait_for_key = self.form_vars['wait_for_key'].get()

        # Update phase object directly with marker bindings
        self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()

        return {
            'text': self.form_widgets['text'].get("1.0", tk.END).strip(),
            'wait_for_key': wait_for_key,
            'duration': self.duration_picker.get() if not wait_for_key else None
        }
