"""
Phase-specific property editors for DyadicSync Timeline Editor.

Provides widgets for editing properties of different phase types.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext
from typing import Optional, Callable, Any
import logging
import traceback
from core.execution.phase import Phase
from core.execution.phases.fixation_phase import FixationPhase
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.phases.instruction_phase import InstructionPhase
from core.execution.phases.baseline_phase import BaselinePhase
from gui.marker_widgets import MarkerBindingListWidget

logger = logging.getLogger(__name__)


class PhasePropertyEditor(ttk.Frame):
    """
    Factory-based phase property editor.

    Creates the appropriate editor widget based on the phase type.
    """

    def __init__(self, parent, on_change: Optional[Callable] = None):
        """
        Initialize phase property editor.

        Args:
            parent: Parent widget
            on_change: Callback when properties change
        """
        super().__init__(parent)

        self.on_change = on_change
        self._current_phase: Optional[Phase] = None
        self._current_editor: Optional[ttk.Frame] = None
        self._suppress_callbacks = False

        # Dialog tracking (prevents widget destruction while dialogs are open)
        self._dialog_open_count = 0  # Counter for nested dialogs
        self._pending_phase_load: Optional[Phase] = None  # Deferred phase load

        # Container for phase-specific editor
        self.editor_container = ttk.Frame(self)
        self.editor_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # No selection message
        self.no_selection_label = ttk.Label(
            self.editor_container,
            text="Select a phase to edit its properties",
            font=('Arial', 10, 'italic')
        )
        self.no_selection_label.pack(pady=20)

    def load_phase(self, phase: Optional[Phase]):
        """
        Load a phase for editing.

        Args:
            phase: Phase object to edit (None to clear)
        """
        # Log stack trace for diagnostic purposes
        logger.debug("PhasePropertyEditor.load_phase called")
        logger.debug("Stack trace:")
        for line in traceback.format_stack()[:-1]:  # Exclude this frame
            logger.debug(f"  {line.strip()}")

        # Check if dialogs are open
        if self._dialog_open_count > 0:
            logger.warning(f"Dialog open (count={self._dialog_open_count}), deferring phase load")
            self._pending_phase_load = phase
            return

        # Clear any pending load since we're executing now
        self._pending_phase_load = None

        self._suppress_callbacks = True
        try:
            self._current_phase = phase

            # Clear existing editor
            if self._current_editor:
                self._current_editor.destroy()
                self._current_editor = None

            # Clear container
            for widget in self.editor_container.winfo_children():
                widget.destroy()

            if phase is None:
                # Show no selection message
                self.no_selection_label = ttk.Label(
                    self.editor_container,
                    text="Select a phase to edit its properties",
                    font=('Arial', 10, 'italic')
                )
                self.no_selection_label.pack(pady=20)
            else:
                # Create appropriate editor based on phase type
                if isinstance(phase, BaselinePhase):
                    self._current_editor = BaselinePhaseEditor(
                        self.editor_container, phase, self._on_property_changed
                    )
                elif isinstance(phase, FixationPhase):
                    self._current_editor = FixationPhaseEditor(
                        self.editor_container, phase, self._on_property_changed
                    )
                elif isinstance(phase, VideoPhase):
                    self._current_editor = VideoPhaseEditor(
                        self.editor_container, phase, self._on_property_changed
                    )
                elif isinstance(phase, RatingPhase):
                    self._current_editor = RatingPhaseEditor(
                        self.editor_container, phase, self._on_property_changed
                    )
                elif isinstance(phase, InstructionPhase):
                    self._current_editor = InstructionPhaseEditor(
                        self.editor_container, phase, self._on_property_changed
                    )
                else:
                    # Unknown phase type
                    error_label = ttk.Label(
                        self.editor_container,
                        text=f"Unknown phase type: {type(phase).__name__}",
                        foreground='red'
                    )
                    error_label.pack(pady=20)

                if self._current_editor:
                    self._current_editor.pack(fill=tk.BOTH, expand=True)
        finally:
            self._suppress_callbacks = False

    def _on_property_changed(self):
        """Handle property change from sub-editor."""
        if not self._suppress_callbacks and self.on_change:
            self.on_change()

    def get_phase(self) -> Optional[Phase]:
        """Get the current phase being edited."""
        return self._current_phase


class FixationPhaseEditor(ttk.LabelFrame):
    """Editor for FixationPhase properties."""

    def __init__(self, parent, phase: FixationPhase, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Fixation Phase Properties", padding=10)

        self.phase = phase
        self.on_change = on_change
        self._suppress_callbacks = False

        # Duration
        ttk.Label(self, text="Duration (seconds):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.DoubleVar(value=phase.duration)
        duration_spinbox = ttk.Spinbox(
            self, from_=0.1, to=3600.0, increment=0.5,
            textvariable=self.duration_var, width=15
        )
        duration_spinbox.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.duration_var.trace_add('write', lambda *args: self._on_property_change())

        # Event Markers (new MarkerBinding system)
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['phase_start', 'phase_end'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=1, column=0, columnspan=3, sticky='ew', pady=10)

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def apply_changes(self):
        """Apply changes to the phase object."""
        try:
            self.phase.duration = self.duration_var.get()

            # Update marker bindings from widget
            self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()
        except ValueError:
            pass  # Ignore invalid values during typing


class VideoPhaseEditor(ttk.LabelFrame):
    """Editor for VideoPhase properties."""

    def __init__(self, parent, phase: VideoPhase, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Video Phase Properties", padding=10)

        self.phase = phase
        self.on_change = on_change
        self._suppress_callbacks = False

        # Participant 1 Video (template variable)
        ttk.Label(self, text="P1 Video (template):").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.p1_video_var = tk.StringVar(value=phase.participant_1_video)
        p1_video_entry = ttk.Entry(self, textvariable=self.p1_video_var, width=30)
        p1_video_entry.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p1_video_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(self, text="Example: {video1}", font=('Arial', 8, 'italic')).grid(
            row=0, column=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # Participant 2 Video (template variable)
        ttk.Label(self, text="P2 Video (template):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.p2_video_var = tk.StringVar(value=phase.participant_2_video)
        p2_video_entry = ttk.Entry(self, textvariable=self.p2_video_var, width=30)
        p2_video_entry.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p2_video_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(self, text="Example: {video2}", font=('Arial', 8, 'italic')).grid(
            row=1, column=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # Auto Advance
        self.auto_advance_var = tk.BooleanVar(value=phase.auto_advance)
        auto_advance_check = ttk.Checkbutton(
            self, text="Auto-advance when videos finish",
            variable=self.auto_advance_var,
            command=self._on_property_change
        )
        auto_advance_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Event Markers (new MarkerBinding system)
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['video_start', 'video_p1_end', 'video_p2_end', 'video_both_complete'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=3, column=0, columnspan=3, sticky='ew', pady=10)

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def apply_changes(self):
        """Apply changes to the phase object."""
        try:
            self.phase.participant_1_video = self.p1_video_var.get()
            self.phase.participant_2_video = self.p2_video_var.get()
            self.phase.auto_advance = self.auto_advance_var.get()

            # Update marker bindings from widget
            self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()
        except ValueError:
            pass  # Ignore invalid values during typing


class RatingPhaseEditor(ttk.LabelFrame):
    """Editor for RatingPhase properties."""

    def __init__(self, parent, phase: RatingPhase, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Rating Phase Properties", padding=10)

        self.phase = phase
        self.on_change = on_change
        self._suppress_callbacks = False

        # Question
        ttk.Label(self, text="Question:").grid(row=0, column=0, sticky=tk.NW, pady=5)
        self.question_text = scrolledtext.ScrolledText(self, width=40, height=3)
        self.question_text.insert('1.0', phase.question)
        self.question_text.grid(row=0, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(5, 0))
        self.question_text.bind('<<Modified>>', self._on_text_modified)

        # Scale Min
        ttk.Label(self, text="Scale Min:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.scale_min_var = tk.IntVar(value=phase.scale_min)
        scale_min_spinbox = ttk.Spinbox(
            self, from_=1, to=10, increment=1,
            textvariable=self.scale_min_var, width=10
        )
        scale_min_spinbox.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.scale_min_var.trace_add('write', lambda *args: self._on_property_change())

        # Scale Max
        ttk.Label(self, text="Scale Max:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.scale_max_var = tk.IntVar(value=phase.scale_max)
        scale_max_spinbox = ttk.Spinbox(
            self, from_=2, to=10, increment=1,
            textvariable=self.scale_max_var, width=10
        )
        scale_max_spinbox.grid(row=2, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.scale_max_var.trace_add('write', lambda *args: self._on_property_change())

        # Timeout
        ttk.Label(self, text="Timeout (seconds):").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.timeout_var = tk.StringVar(value=str(phase.timeout) if phase.timeout else "")
        timeout_entry = ttk.Entry(self, textvariable=self.timeout_var, width=10)
        timeout_entry.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.timeout_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(self, text="(empty = wait indefinitely)", font=('Arial', 8, 'italic')).grid(
            row=3, column=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # Scale Labels (simplified - just show info)
        ttk.Label(self, text="Scale Labels:").grid(row=4, column=0, sticky=tk.W, pady=5)
        labels_text = ', '.join(phase.scale_labels) if phase.scale_labels else "None"
        ttk.Label(self, text=labels_text, font=('Arial', 9)).grid(
            row=4, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # Event Markers (new MarkerBinding system)
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['p1_response', 'p2_response'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=5, column=0, columnspan=3, sticky='ew', pady=10)

    def _on_text_modified(self, event=None):
        """Handle text widget modification."""
        if self.question_text.edit_modified():
            self.question_text.edit_modified(False)
            self._on_property_change()

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def apply_changes(self):
        """Apply changes to the phase object."""
        try:
            self.phase.question = self.question_text.get('1.0', 'end-1c')
            self.phase.scale_min = self.scale_min_var.get()
            self.phase.scale_max = self.scale_max_var.get()

            # Parse timeout
            timeout_str = self.timeout_var.get().strip()
            self.phase.timeout = float(timeout_str) if timeout_str else None

            # Update marker bindings from widget
            self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()
        except ValueError:
            pass  # Ignore invalid values during typing


class InstructionPhaseEditor(ttk.LabelFrame):
    """Editor for InstructionPhase properties."""

    def __init__(self, parent, phase: InstructionPhase, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Instruction Phase Properties", padding=10)

        self.phase = phase
        self.on_change = on_change
        self._suppress_callbacks = False

        # Instruction Text
        ttk.Label(self, text="Instruction Text:").grid(row=0, column=0, sticky=tk.NW, pady=5)
        self.text_widget = scrolledtext.ScrolledText(self, width=50, height=6)
        self.text_widget.insert('1.0', phase.text)
        self.text_widget.grid(row=0, column=1, columnspan=2, sticky=tk.W, pady=5, padx=(5, 0))
        self.text_widget.bind('<<Modified>>', self._on_text_modified)

        # Font Size
        ttk.Label(self, text="Font Size:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.font_size_var = tk.IntVar(value=phase.font_size)
        font_size_spinbox = ttk.Spinbox(
            self, from_=10, to=72, increment=2,
            textvariable=self.font_size_var, width=10
        )
        font_size_spinbox.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.font_size_var.trace_add('write', lambda *args: self._on_property_change())

        # Wait for Key
        self.wait_for_key_var = tk.BooleanVar(value=phase.wait_for_key)
        wait_check = ttk.Checkbutton(
            self, text="Wait for key press to continue",
            variable=self.wait_for_key_var,
            command=self._on_property_change
        )
        wait_check.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Continue Key
        ttk.Label(self, text="Continue Key:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.continue_key_var = tk.StringVar(value=phase.continue_key or "")
        continue_key_entry = ttk.Entry(self, textvariable=self.continue_key_var, width=15)
        continue_key_entry.grid(row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.continue_key_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(self, text="(e.g., space, enter)", font=('Arial', 8, 'italic')).grid(
            row=3, column=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # Duration
        ttk.Label(self, text="Duration (seconds):").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.duration_var = tk.StringVar(value=str(phase.duration) if phase.duration else "")
        duration_entry = ttk.Entry(self, textvariable=self.duration_var, width=15)
        duration_entry.grid(row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.duration_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(self, text="(empty = wait for key)", font=('Arial', 8, 'italic')).grid(
            row=4, column=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # Event Markers (new MarkerBinding system)
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['phase_start', 'phase_end'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=5, column=0, columnspan=3, sticky='ew', pady=10)

    def _on_text_modified(self, event=None):
        """Handle text widget modification."""
        if self.text_widget.edit_modified():
            self.text_widget.edit_modified(False)
            self._on_property_change()

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def apply_changes(self):
        """Apply changes to the phase object."""
        try:
            self.phase.text = self.text_widget.get('1.0', 'end-1c')
            self.phase.font_size = self.font_size_var.get()
            self.phase.wait_for_key = self.wait_for_key_var.get()

            # Parse continue key
            continue_key_str = self.continue_key_var.get().strip()
            self.phase.continue_key = continue_key_str if continue_key_str else None

            # Parse duration
            duration_str = self.duration_var.get().strip()
            self.phase.duration = float(duration_str) if duration_str else None

            # Update marker bindings from widget
            self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()
        except ValueError:
            pass  # Ignore invalid values during typing


class BaselinePhaseEditor(FixationPhaseEditor):
    """
    Editor for BaselinePhase properties.

    BaselinePhase extends FixationPhase, so we reuse the same editor.
    """

    def __init__(self, parent, phase: BaselinePhase, on_change: Optional[Callable] = None):
        # BaselinePhase is just a FixationPhase with different defaults
        super().__init__(parent, phase, on_change)

        # Update label to indicate it's a baseline
        self.configure(text="Baseline Phase Properties")
