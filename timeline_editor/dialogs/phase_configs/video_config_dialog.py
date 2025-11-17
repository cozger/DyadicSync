"""
Video Phase Configuration Dialog.

Configures VideoPhase parameters:
- P1 video source (template variable or fixed path)
- P2 video source (template variable or fixed path)
- LSL markers (start, P1 end, P2 end)

Most complex dialog - handles template variables like {video1}, {video2}.
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from timeline_editor.dialogs.widgets import TemplateVariableWidget
from core.execution.phases.video_phase import VideoPhase
from gui.marker_widgets import MarkerBindingListWidget


class VideoConfigDialog(FormDialog):
    """Dialog for configuring VideoPhase."""

    def __init__(self, parent, phase: VideoPhase):
        """
        Initialize video config dialog.

        Args:
            parent: Parent window
            phase: VideoPhase to configure
        """
        self.phase = phase
        super().__init__(parent, "Configure Video Phase", width=600, height=600)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Info about template variables
        info_frame = ttk.LabelFrame(content_frame, text="Template Variables", padding=10)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        info_text = (
            "Template variables (like {video1}, {video2}) are populated from the TrialList CSV.\n"
            "Each trial in the CSV provides values for these variables.\n\n"
            "Use template variables for trial-based blocks, or fixed paths for simple blocks."
        )

        ttk.Label(
            info_frame,
            text=info_text,
            font=("Arial", 9),
            justify=tk.LEFT,
            wraplength=550
        ).pack()

        # P1 Video
        self.p1_video_widget = TemplateVariableWidget(
            content_frame,
            label="Participant 1 Video:",
            available_variables=['video1', 'video2', 'p1_video', 'p2_video'],
            default_mode='template' if self.phase.participant_1_video.startswith('{') else 'fixed',
            default_value=self.phase.participant_1_video
        )
        self.p1_video_widget.pack(fill=tk.X, pady=10)

        # P2 Video
        self.p2_video_widget = TemplateVariableWidget(
            content_frame,
            label="Participant 2 Video:",
            available_variables=['video1', 'video2', 'p1_video', 'p2_video'],
            default_mode='template' if self.phase.participant_2_video.startswith('{') else 'fixed',
            default_value=self.phase.participant_2_video
        )
        self.p2_video_widget.pack(fill=tk.X, pady=10)

        # LSL Markers (new MarkerBinding system)
        lsl_frame = ttk.LabelFrame(content_frame, text="LSL Event Markers", padding=10)
        lsl_frame.pack(fill=tk.X, pady=10)

        self.marker_bindings_widget = MarkerBindingListWidget(
            lsl_frame,
            bindings=self.phase.marker_bindings,
            available_events=['video_start', 'video_p1_end', 'video_p2_end', 'video_both_complete'],
            on_change=None,  # Dialog handles via OK button
            label=""  # No label since it's in a frame already
        )
        self.marker_bindings_widget.pack(fill=tk.BOTH, expand=True)

        # Playback Info
        playback_frame = ttk.LabelFrame(content_frame, text="Playback Info", padding=10)
        playback_frame.pack(fill=tk.X, pady=10)

        info_text = (
            "• Videos play simultaneously on both participant screens\n"
            "• Audio is routed to separate headphones (configured in Experiment Settings)\n"
            "• Videos must be compatible formats (H.264, VP9, etc.)\n"
            "• Duration is auto-detected from video files"
        )

        ttk.Label(
            playback_frame,
            text=info_text,
            font=("Arial", 9),
            justify=tk.LEFT
        ).pack()

    def _validate(self) -> List[str]:
        """Validate video config."""
        errors = []

        # Validate P1 video
        p1_video = self.p1_video_widget.get()
        if not p1_video:
            errors.append("Participant 1 video is required")

        # Validate P2 video
        p2_video = self.p2_video_widget.get()
        if not p2_video:
            errors.append("Participant 2 video is required")

        # If using fixed paths, check files exist
        if not p1_video.startswith('{'):
            if not Path(p1_video).is_file():
                errors.append(f"Participant 1 video file not found: {p1_video}")

        if not p2_video.startswith('{'):
            if not Path(p2_video).is_file():
                errors.append(f"Participant 2 video file not found: {p2_video}")

        # Marker validation is handled by MarkerBindingListWidget

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect video config."""
        # Update phase object directly with marker bindings
        self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()

        return {
            'participant_1_video': self.p1_video_widget.get(),
            'participant_2_video': self.p2_video_widget.get()
        }
