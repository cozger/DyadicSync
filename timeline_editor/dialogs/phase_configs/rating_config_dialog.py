"""
Rating Phase Configuration Dialog.

Configures RatingPhase parameters:
- Question text
- Rating scale type (Likert-7, Likert-5, Binary, Custom)
- Participant 1 keys (default: 1-7)
- Participant 2 keys (default: Q-U)
- Timeout (optional)
- LSL markers
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from timeline_editor.dialogs.widgets import ScaleTypeSelector, DurationPicker
from core.execution.phases.rating_phase import RatingPhase
from gui.marker_widgets import MarkerBindingListWidget


class RatingConfigDialog(FormDialog):
    """Dialog for configuring RatingPhase."""

    def __init__(self, parent, phase: RatingPhase):
        """
        Initialize rating config dialog.

        Args:
            parent: Parent window
            phase: RatingPhase to configure
        """
        self.phase = phase
        super().__init__(parent, "Configure Rating Phase", width=550, height=550)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Question text
        self.add_text_area(
            content_frame,
            "Rating Question:",
            "question",
            default=self.phase.question,
            height=3
        )

        # Scale configuration
        scale_frame = ttk.LabelFrame(content_frame, text="Rating Scale", padding=10)
        scale_frame.pack(fill=tk.X, pady=10)

        # Detect current scale type from min/max
        current_scale_type = 'likert7'
        if self.phase.scale_min == 1 and self.phase.scale_max == 7:
            current_scale_type = 'likert7'
        elif self.phase.scale_min == 1 and self.phase.scale_max == 5:
            current_scale_type = 'likert5'
        elif self.phase.scale_min == 0 and self.phase.scale_max == 1:
            current_scale_type = 'binary'

        self.scale_selector = ScaleTypeSelector(
            scale_frame,
            label="Scale Type:",
            default=current_scale_type
        )
        self.scale_selector.pack(fill=tk.X)

        # Key bindings (informational only - hardcoded in RatingPhase)
        keys_frame = ttk.LabelFrame(content_frame, text="Key Bindings (Read-Only)", padding=10)
        keys_frame.pack(fill=tk.X, pady=10)

        info_text = (
            "Key bindings are currently hardcoded in the system:\n\n"
            "  Participant 1: 1, 2, 3, 4, 5, 6, 7\n"
            "  Participant 2: Q, W, E, R, T, Y, U\n\n"
            "These keys map to ratings 1-7 respectively."
        )

        ttk.Label(
            keys_frame,
            text=info_text,
            font=("Arial", 9),
            justify=tk.LEFT,
            foreground="gray"
        ).pack()

        # Timeout
        timeout_frame = ttk.LabelFrame(content_frame, text="Timeout (Optional)", padding=10)
        timeout_frame.pack(fill=tk.X, pady=10)

        self.add_checkbox(
            timeout_frame,
            "Enable timeout",
            "timeout_enabled",
            default=self.phase.timeout is not None
        )

        self.timeout_picker = DurationPicker(
            timeout_frame,
            label="Timeout:",
            default_seconds=self.phase.timeout if self.phase.timeout else 10.0,
            min_seconds=1.0,
            max_seconds=60.0,
            show_formatted=True
        )
        self.timeout_picker.pack(fill=tk.X, pady=5)

        # LSL Event Markers (new MarkerBinding system)
        lsl_frame = ttk.LabelFrame(content_frame, text="LSL Event Markers", padding=10)
        lsl_frame.pack(fill=tk.X, pady=10)

        self.marker_bindings_widget = MarkerBindingListWidget(
            lsl_frame,
            bindings=self.phase.marker_bindings,
            available_events=['p1_response', 'p2_response'],
            on_change=None,  # Dialog handles via OK button
            label=""  # No label since it's in a frame already
        )
        self.marker_bindings_widget.pack(fill=tk.BOTH, expand=True)

        # Helpful info about marker templates
        info_text = (
            "Tip: Use templates like 300#0$ for response markers:\n"
            "  • # = trial number   • $ = rating value (1-9)"
        )
        ttk.Label(
            lsl_frame,
            text=info_text,
            font=("Arial", 8),
            foreground="gray",
            justify=tk.LEFT
        ).pack(pady=(5, 0))

    def _validate(self) -> List[str]:
        """Validate rating config."""
        errors = []

        # Validate question
        question = self.form_widgets['question'].get("1.0", tk.END).strip()
        if not question:
            errors.append("Rating question is required")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect rating config."""
        timeout_enabled = self.form_vars['timeout_enabled'].get()

        # Map scale type to min/max
        scale_type = self.scale_selector.get()
        if scale_type == 'likert7':
            scale_min, scale_max = 1, 7
        elif scale_type == 'likert5':
            scale_min, scale_max = 1, 5
        elif scale_type == 'binary':
            scale_min, scale_max = 0, 1
        else:  # custom
            scale_min, scale_max = 1, 7

        # Update phase object directly with marker bindings
        self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()

        return {
            'question': self.form_widgets['question'].get("1.0", tk.END).strip(),
            'scale_min': scale_min,
            'scale_max': scale_max,
            'timeout': self.timeout_picker.get() if timeout_enabled else None
        }
