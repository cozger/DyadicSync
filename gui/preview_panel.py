"""
Preview panel for displaying participant monitor previews.
"""

import tkinter as tk
from tkinter import ttk, Canvas
from typing import Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from config.trial import Trial


class MonitorPreview(ttk.LabelFrame):
    """
    Preview widget showing what a participant will see.
    """

    def __init__(self, parent, participant_num: int):
        """
        Initialize monitor preview.

        Args:
            parent: Parent widget
            participant_num: Participant number (1 or 2)
        """
        super().__init__(
            parent,
            text=f"Participant {participant_num} Monitor Preview",
            padding=10
        )

        self.participant_num = participant_num
        self.current_trial: Optional[Trial] = None

        # Preview canvas (16:9 aspect ratio)
        self.canvas = Canvas(self, bg="#000000", width=320, height=180)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Info label
        self.info_label = ttk.Label(
            self,
            text="No trial selected",
            font=("Arial", 9, "italic"),
            anchor=tk.CENTER
        )
        self.info_label.pack(fill=tk.X, pady=5)

        self._draw_placeholder()

    def _draw_placeholder(self):
        """Draw placeholder content."""
        self.canvas.delete("all")

        # Draw placeholder text
        self.canvas.create_text(
            160, 90,
            text=f"Participant {self.participant_num}\nMonitor Preview",
            fill="#FFFFFF",
            font=("Arial", 12),
            justify=tk.CENTER
        )

    def load_trial(self, trial: Trial):
        """
        Load a trial for preview.

        Args:
            trial: Trial object to preview
        """
        self.current_trial = trial
        self.canvas.delete("all")

        # Get video path for this participant
        video_path = trial.video_path_1 if self.participant_num == 1 else trial.video_path_2

        if video_path:
            # Show video path
            filename = Path(video_path).name
            self.canvas.create_text(
                160, 90,
                text=f"Video: {filename}",
                fill="#FFFFFF",
                font=("Arial", 10),
                justify=tk.CENTER
            )

            self.info_label.config(text=f"Trial {trial.index + 1}: {filename}")
        else:
            self.canvas.create_text(
                160, 90,
                text="No video selected",
                fill="#888888",
                font=("Arial", 10, "italic")
            )

            self.info_label.config(text=f"Trial {trial.index + 1}: No video")

    def clear(self):
        """Clear the preview."""
        self.current_trial = None
        self._draw_placeholder()
        self.info_label.config(text="No trial selected")


class PreviewPanel(ttk.Frame):
    """
    Panel containing previews for both participant monitors.
    """

    def __init__(self, parent):
        """
        Initialize preview panel with dual monitor previews.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)

        # Title
        title_label = ttk.Label(
            self,
            text="Monitor Previews",
            font=("Arial", 12, "bold")
        )
        title_label.pack(pady=5)

        # Container for both previews
        preview_container = ttk.Frame(self)
        preview_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Participant 1 preview
        self.preview1 = MonitorPreview(preview_container, participant_num=1)
        self.preview1.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

        # Participant 2 preview
        self.preview2 = MonitorPreview(preview_container, participant_num=2)
        self.preview2.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)

    def load_trial(self, trial: Trial):
        """
        Load a trial for preview on both monitors.

        Args:
            trial: Trial object to preview
        """
        self.preview1.load_trial(trial)
        self.preview2.load_trial(trial)

    def clear(self):
        """Clear both previews."""
        self.preview1.clear()
        self.preview2.clear()
