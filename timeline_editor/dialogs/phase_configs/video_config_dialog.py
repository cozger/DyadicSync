"""
Video Phase Configuration Dialog.

Configures VideoPhase parameters:
- Auto-advance toggle
- LSL markers (start, P1 end, P2 end)

Video is selected automatically from the trial list CSV.
Display target is set per variant (P1 Viewer, P2 Viewer, Joint).
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from core.execution.phases.video_phase import VideoPhase
from gui.marker_widgets import MarkerBindingListWidget


class VideoConfigDialog(FormDialog):
    """Dialog for configuring VideoPhase."""

    def __init__(self, parent, phase: VideoPhase):
        self.phase = phase
        super().__init__(parent, "Configure Video Phase", width=600, height=400)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Info
        info_frame = ttk.LabelFrame(content_frame, text="Video Selection", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(
            info_frame,
            text=(
                "A random video is selected from the trial list CSV for each trial.\n"
                "Videos are played without replacement (each video shown once per session).\n"
                "Display target is set automatically per variant:\n"
                "  P1 Viewer → P1 monitor, P2 Viewer → P2 monitor, Joint → both."
            ),
            font=("Arial", 9),
            justify=tk.LEFT,
            wraplength=520
        ).pack()

        # Auto Advance
        options_frame = ttk.LabelFrame(content_frame, text="Options", padding=10)
        options_frame.pack(fill=tk.X, pady=5)

        self.auto_advance_var = tk.BooleanVar(value=self.phase.auto_advance)
        ttk.Checkbutton(
            options_frame,
            text="Auto-advance when video finishes",
            variable=self.auto_advance_var
        ).pack(anchor=tk.W)

        # LSL Markers
        lsl_frame = ttk.LabelFrame(content_frame, text="LSL Event Markers", padding=10)
        lsl_frame.pack(fill=tk.X, pady=10)

        self.marker_bindings_widget = MarkerBindingListWidget(
            lsl_frame,
            bindings=self.phase.marker_bindings,
            available_events=['video_start', 'video_p1_end', 'video_p2_end', 'video_both_complete'],
            on_change=None,
            label=""
        )
        self.marker_bindings_widget.pack(fill=tk.BOTH, expand=True)

    def _validate(self) -> List[str]:
        return []

    def _collect_result(self) -> Dict[str, Any]:
        self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()
        return {
            'auto_advance': self.auto_advance_var.get()
        }
