"""
Rating Phase Configuration Dialog.

Configures RatingPhase parameters:
- P1 question text
- P2 question text
- P1 rating keys
- P2 rating keys
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
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
        super().__init__(parent, "Configure Rating Phase", width=500, height=400)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # P1 Question
        questions_frame = ttk.LabelFrame(content_frame, text="Questions", padding=10)
        questions_frame.pack(fill=tk.X, pady=10)

        p1_frame = ttk.Frame(questions_frame)
        p1_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p1_frame, text="P1 Question:", width=12).pack(side=tk.LEFT)
        self.p1_question_text = tk.Text(p1_frame, height=2, width=45)
        self.p1_question_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        p1_q = self.phase.participant_1_question or self.phase.question or ""
        if p1_q:
            self.p1_question_text.insert('1.0', p1_q)

        p2_frame = ttk.Frame(questions_frame)
        p2_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p2_frame, text="P2 Question:", width=12).pack(side=tk.LEFT)
        self.p2_question_text = tk.Text(p2_frame, height=2, width=45)
        self.p2_question_text.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        p2_q = self.phase.participant_2_question or self.phase.question or ""
        if p2_q:
            self.p2_question_text.insert('1.0', p2_q)

        # Key bindings
        keys_frame = ttk.LabelFrame(content_frame, text="Rating Keys", padding=10)
        keys_frame.pack(fill=tk.X, pady=10)

        p1_keys_frame = ttk.Frame(keys_frame)
        p1_keys_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p1_keys_frame, text="P1 Keys:", width=12).pack(side=tk.LEFT)
        self.p1_keys_var = tk.StringVar(value=self.phase.p1_keys)
        ttk.Entry(p1_keys_frame, textvariable=self.p1_keys_var, width=20).pack(side=tk.LEFT, padx=5)

        p2_keys_frame = ttk.Frame(keys_frame)
        p2_keys_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p2_keys_frame, text="P2 Keys:", width=12).pack(side=tk.LEFT)
        self.p2_keys_var = tk.StringVar(value=self.phase.p2_keys)
        ttk.Entry(p2_keys_frame, textvariable=self.p2_keys_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            keys_frame,
            text="One key per scale point, maps to values 1, 2, 3...\n"
                 "Phase ends when both participants have pressed a key.",
            font=("Arial", 8),
            justify=tk.LEFT,
            foreground="gray"
        ).pack(anchor=tk.W, pady=(5, 0))

        # Observer beep
        beep_frame = ttk.LabelFrame(content_frame, text="Observer Beep", padding=10)
        beep_frame.pack(fill=tk.X, pady=10)

        self.observer_beep_var = tk.BooleanVar(value=self.phase.observer_beep)
        ttk.Checkbutton(
            beep_frame,
            text="Play audio beep for observer at rating start",
            variable=self.observer_beep_var
        ).pack(anchor=tk.W)

        ttk.Label(
            beep_frame,
            text="In turn-taking conditions, plays a 0.5s tone on the\n"
                 "observer's audio device when the rating screen appears.",
            font=("Arial", 8),
            justify=tk.LEFT,
            foreground="gray"
        ).pack(anchor=tk.W, pady=(5, 0))

        # LSL Markers
        lsl_frame = ttk.LabelFrame(content_frame, text="LSL Event Markers", padding=10)
        lsl_frame.pack(fill=tk.X, pady=10)

        self.marker_bindings_widget = MarkerBindingListWidget(
            lsl_frame,
            bindings=self.phase.marker_bindings,
            available_events=['p1_response', 'p2_response'],
            on_change=None,
            label=""
        )
        self.marker_bindings_widget.pack(fill=tk.BOTH, expand=True)

    def _validate(self) -> List[str]:
        """Validate rating config."""
        errors = []

        p1_q = self.p1_question_text.get("1.0", tk.END).strip()
        p2_q = self.p2_question_text.get("1.0", tk.END).strip()
        if not p1_q and not p2_q:
            errors.append("At least one question is required")

        p1_keys = self.p1_keys_var.get().strip()
        p2_keys = self.p2_keys_var.get().strip()
        if not p1_keys:
            errors.append("P1 rating keys are required")
        if not p2_keys:
            errors.append("P2 rating keys are required")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect rating config."""
        p1_q = self.p1_question_text.get("1.0", tk.END).strip()
        p2_q = self.p2_question_text.get("1.0", tk.END).strip()
        p1_keys = self.p1_keys_var.get().strip() or '1234567'
        p2_keys = self.p2_keys_var.get().strip() or 'QWERTYU'

        self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()

        return {
            'participant_1_question': p1_q if p1_q else None,
            'participant_2_question': p2_q if p2_q else None,
            'question': p1_q or p2_q,
            'p1_keys': p1_keys,
            'p2_keys': p2_keys,
            'scale_min': 1,
            'scale_max': max(len(p1_keys), len(p2_keys)),
            'display_target': 'both',
            'timeout': None,
            'observer_beep': self.observer_beep_var.get()
        }
