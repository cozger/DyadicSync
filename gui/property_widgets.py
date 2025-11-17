"""
Property editing widgets for trial parameters, timing, and questions.
"""

import tkinter as tk
from tkinter import ttk, filedialog, Text
from typing import Optional, Callable
import sys
from pathlib import Path
import time

sys.path.append(str(Path(__file__).parent.parent))

from config.trial import Trial
from config.question import Question, ScaleType


class TimingEditor(ttk.LabelFrame):
    """Widget for editing timing parameters."""

    def __init__(self, parent, on_change: Optional[Callable] = None):
        """
        Initialize timing editor.

        Args:
            parent: Parent widget
            on_change: Callback when values change
        """
        super().__init__(parent, text="Timing Parameters", padding=10)

        self.on_change = on_change
        self._suppress_callbacks = False

        # Fixation duration
        ttk.Label(self, text="Fixation Duration (seconds):").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )

        self.fixation_var = tk.DoubleVar(value=3.0)
        self.fixation_spinbox = ttk.Spinbox(
            self,
            from_=0.0,
            to=60.0,
            increment=0.5,
            textvariable=self.fixation_var,
            width=10
        )
        self.fixation_spinbox.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(0, 10))
        self.fixation_var.trace_add("write", self._on_value_change)

        # Rating timeout
        ttk.Label(self, text="Rating Timeout (seconds):").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )

        self.timeout_var = tk.StringVar(value="Unlimited")
        self.timeout_spinbox = ttk.Spinbox(
            self,
            from_=0.0,
            to=300.0,
            increment=5.0,
            textvariable=self.timeout_var,
            width=10
        )
        self.timeout_spinbox.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(0, 10))
        self.timeout_var.trace_add("write", self._on_value_change)

        self.timeout_unlimited_btn = ttk.Button(
            self,
            text="Unlimited",
            command=self._set_timeout_unlimited,
            width=12
        )
        self.timeout_unlimited_btn.grid(row=1, column=2, sticky=tk.W, pady=5)

    def _on_value_change(self, *args):
        """Handle value change."""
        if not self._suppress_callbacks and self.on_change:
            self.on_change()

    def _set_timeout_unlimited(self):
        """Set rating timeout to unlimited."""
        self.timeout_var.set("Unlimited")

    def load_from_trial(self, trial: Trial):
        """Load values from trial object."""
        self._suppress_callbacks = True

        self.fixation_var.set(trial.fixation_duration)

        if trial.rating_timeout is None:
            self.timeout_var.set("Unlimited")
        else:
            self.timeout_var.set(str(trial.rating_timeout))

        self._suppress_callbacks = False

    def apply_to_trial(self, trial: Trial):
        """Apply current values to trial object."""
        trial.fixation_duration = self.fixation_var.get()

        timeout_str = self.timeout_var.get()
        if timeout_str == "Unlimited" or timeout_str == "":
            trial.rating_timeout = None
        else:
            try:
                trial.rating_timeout = float(timeout_str)
            except ValueError:
                trial.rating_timeout = None


class VideoPathEditor(ttk.LabelFrame):
    """Widget for editing video file paths."""

    def __init__(self, parent, on_change: Optional[Callable] = None):
        """
        Initialize video path editor.

        Args:
            parent: Parent widget
            on_change: Callback when paths change
        """
        super().__init__(parent, text="Video Files", padding=10)

        self.on_change = on_change
        self._suppress_callbacks = False

        # Video 1
        ttk.Label(self, text="Participant 1 Video:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )

        self.video1_var = tk.StringVar()
        self.video1_entry = ttk.Entry(self, textvariable=self.video1_var, width=50)
        self.video1_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=5)
        self.video1_var.trace_add("write", self._on_value_change)

        self.video1_browse_btn = ttk.Button(
            self,
            text="Browse...",
            command=lambda: self._browse_video(1)
        )
        self.video1_browse_btn.grid(row=0, column=2, pady=5)

        # Video 2
        ttk.Label(self, text="Participant 2 Video:").grid(
            row=1, column=0, sticky=tk.W, pady=5
        )

        self.video2_var = tk.StringVar()
        self.video2_entry = ttk.Entry(self, textvariable=self.video2_var, width=50)
        self.video2_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.video2_var.trace_add("write", self._on_value_change)

        self.video2_browse_btn = ttk.Button(
            self,
            text="Browse...",
            command=lambda: self._browse_video(2)
        )
        self.video2_browse_btn.grid(row=1, column=2, pady=5)

    def _on_value_change(self, *args):
        """Handle value change."""
        if not self._suppress_callbacks and self.on_change:
            self.on_change()

    def _browse_video(self, participant_num: int):
        """Open file browser for video selection."""
        filetypes = [
            ("Video files", "*.mp4 *.mpeg *.avi *.mov *.mkv *.webm"),
            ("All files", "*.*")
        ]

        filename = filedialog.askopenfilename(
            title=f"Select Video for Participant {participant_num}",
            filetypes=filetypes
        )

        if filename:
            if participant_num == 1:
                self.video1_var.set(filename)
            else:
                self.video2_var.set(filename)

    def load_from_trial(self, trial: Trial):
        """Load values from trial object."""
        self._suppress_callbacks = True

        self.video1_var.set(trial.video_path_1)
        self.video2_var.set(trial.video_path_2)

        self._suppress_callbacks = False

    def apply_to_trial(self, trial: Trial):
        """Apply current values to trial object."""
        trial.video_path_1 = self.video1_var.get()
        trial.video_path_2 = self.video2_var.get()


class QuestionEditor(ttk.LabelFrame):
    """Widget for editing question and rating scale configuration."""

    def __init__(self, parent, on_change: Optional[Callable] = None):
        """
        Initialize question editor.

        Args:
            parent: Parent widget
            on_change: Callback when values change
        """
        super().__init__(parent, text="Rating Question", padding=10)

        self.on_change = on_change
        self._suppress_callbacks = False

        # Override checkbox
        self.override_var = tk.BooleanVar(value=False)
        self.override_check = ttk.Checkbutton(
            self,
            text="Use custom question for this trial",
            variable=self.override_var,
            command=self._on_override_toggle
        )
        self.override_check.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)

        # Question text
        ttk.Label(self, text="Question Text:").grid(
            row=1, column=0, sticky=tk.NW, pady=5
        )

        self.question_text = Text(self, height=3, width=50, wrap=tk.WORD)
        self.question_text.grid(row=1, column=1, sticky=tk.W, pady=5, padx=5)
        self.question_text.bind("<<Modified>>", self._on_text_modified)

        # Scale type
        ttk.Label(self, text="Scale Type:").grid(
            row=2, column=0, sticky=tk.W, pady=5
        )

        self.scale_type_var = tk.StringVar(value="likert_7")
        self.scale_type_combo = ttk.Combobox(
            self,
            textvariable=self.scale_type_var,
            values=["likert_7", "likert_5", "binary", "custom"],
            state="readonly",
            width=20
        )
        self.scale_type_combo.grid(row=2, column=1, sticky=tk.W, pady=5, padx=5)
        self.scale_type_combo.bind("<<ComboboxSelected>>", self._on_value_change)

        # Initial state (disabled)
        self._set_widgets_state(tk.DISABLED)

    def _on_override_toggle(self):
        """Handle override checkbox toggle."""
        if self.override_var.get():
            self._set_widgets_state(tk.NORMAL)
        else:
            self._set_widgets_state(tk.DISABLED)

        if self.on_change:
            self.on_change()

    def _set_widgets_state(self, state):
        """Enable or disable editing widgets."""
        self.question_text.config(state=state)
        self.scale_type_combo.config(state="readonly" if state == tk.NORMAL else tk.DISABLED)

    def _on_value_change(self, *args):
        """Handle value change."""
        if not self._suppress_callbacks and self.on_change:
            self.on_change()

    def _on_text_modified(self, event):
        """Handle text widget modification."""
        if not self._suppress_callbacks and self.question_text.edit_modified():
            if self.on_change:
                self.on_change()
            self.question_text.edit_modified(False)

    def load_from_trial(self, trial: Trial):
        """Load values from trial object."""
        self._suppress_callbacks = True

        has_override = trial.question_override is not None
        self.override_var.set(has_override)

        if has_override:
            self._set_widgets_state(tk.NORMAL)
            self.question_text.delete("1.0", tk.END)
            self.question_text.insert("1.0", trial.question_override.text)
            self.question_text.edit_modified(False)  # Clear modified flag
            self.scale_type_var.set(trial.question_override.scale_type.value)
        else:
            self._set_widgets_state(tk.DISABLED)
            self.question_text.delete("1.0", tk.END)
            self.question_text.edit_modified(False)  # Clear modified flag

        self._suppress_callbacks = False

    def apply_to_trial(self, trial: Trial, default_question: Question):
        """Apply current values to trial object."""
        if self.override_var.get():
            # Create custom question
            question_text = self.question_text.get("1.0", tk.END).strip()
            scale_type = ScaleType(self.scale_type_var.get())

            trial.question_override = Question(
                text=question_text,
                scale_type=scale_type
            )
        else:
            # Use default
            trial.question_override = None


class PropertyEditor(ttk.Frame):
    """
    Combined property editor with all trial parameters.
    """

    def __init__(self, parent, default_question: Question, on_change: Optional[Callable] = None):
        """
        Initialize property editor.

        Args:
            parent: Parent widget
            default_question: Default question configuration
            on_change: Callback when any value changes
        """
        print(f"[DEBUG {time.time():.3f}] PropertyEditor.__init__ START")
        super().__init__(parent)

        self.default_question = default_question
        self.on_change = on_change
        self.current_trial: Optional[Trial] = None
        self._suppress_callbacks = True  # Suppress during initialization to prevent loops

        # Create sub-editors
        print(f"[DEBUG {time.time():.3f}] PropertyEditor creating TimingEditor...")
        self.timing_editor = TimingEditor(self, on_change=self._handle_change)
        self.timing_editor.pack(fill=tk.X, pady=5)

        print(f"[DEBUG {time.time():.3f}] PropertyEditor creating VideoPathEditor...")
        self.video_editor = VideoPathEditor(self, on_change=self._handle_change)
        self.video_editor.pack(fill=tk.X, pady=5)

        print(f"[DEBUG {time.time():.3f}] PropertyEditor creating QuestionEditor...")
        self.question_editor = QuestionEditor(self, on_change=self._handle_change)
        self.question_editor.pack(fill=tk.X, pady=5)

        # Apply button
        print(f"[DEBUG {time.time():.3f}] PropertyEditor creating apply button...")
        self.apply_btn = ttk.Button(
            self,
            text="Apply Changes",
            command=self._apply_changes
        )
        self.apply_btn.pack(pady=10)

        # Re-enable callbacks after init completes and layout settles
        self.after(100, self._enable_callbacks)
        print(f"[DEBUG {time.time():.3f}] PropertyEditor.__init__ COMPLETE (callbacks will enable in 100ms)")

    def _enable_callbacks(self):
        """Enable callbacks after initialization completes."""
        self._suppress_callbacks = False
        print(f"[DEBUG {time.time():.3f}] PropertyEditor callbacks ENABLED")

    def _handle_change(self):
        """Handle change from any sub-editor - AUTO-APPLIES to trial."""
        if self._suppress_callbacks:
            return

        # Auto-apply changes to current trial
        if self.current_trial:
            self.timing_editor.apply_to_trial(self.current_trial)
            self.video_editor.apply_to_trial(self.current_trial)
            self.question_editor.apply_to_trial(self.current_trial, self.default_question)

        # Notify parent of change
        if self.on_change:
            self.on_change()

    def _apply_changes(self):
        """Apply all changes to current trial (manual button click)."""
        if self.current_trial:
            self.timing_editor.apply_to_trial(self.current_trial)
            self.video_editor.apply_to_trial(self.current_trial)
            self.question_editor.apply_to_trial(self.current_trial, self.default_question)

            if self.on_change:
                self.on_change()

    def load_trial(self, trial: Trial):
        """Load a trial for editing."""
        # Suppress callbacks while loading to prevent triggering changes
        self._suppress_callbacks = True

        self.current_trial = trial
        self.timing_editor.load_from_trial(trial)
        self.video_editor.load_from_trial(trial)
        self.question_editor.load_from_trial(trial)

        self._suppress_callbacks = False

    def clear(self):
        """Clear the editor."""
        self.current_trial = None
