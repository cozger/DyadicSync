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


class DisplayTargetWidget(ttk.Frame):
    """
    Reusable widget for selecting display_target.

    Provides a single dropdown: "Show to:" with options:
    - "Both Participants" (both)
    - "Participant 1 Only" (p1)
    - "Participant 2 Only" (p2)
    """

    # Mapping from display text to value
    OPTIONS = {
        "Both Participants": "both",
        "Participant 1 Only": "p1",
        "Participant 2 Only": "p2"
    }

    # Reverse mapping from value to display text
    VALUE_TO_DISPLAY = {v: k for k, v in OPTIONS.items()}

    def __init__(self, parent, initial_value: str = "both",
                 on_change: Optional[Callable] = None, label: str = "Show to:"):
        """
        Initialize display target widget.

        Args:
            parent: Parent widget
            initial_value: Initial display_target value ("both", "p1", "p2")
            on_change: Callback when selection changes
            label: Label text to show before dropdown
        """
        super().__init__(parent)
        self.on_change = on_change
        self._suppress_callbacks = False

        # Label
        ttk.Label(self, text=label).pack(side=tk.LEFT, padx=(0, 5))

        # Convert initial value to display text
        initial_display = self.VALUE_TO_DISPLAY.get(initial_value, "Both Participants")

        # Dropdown
        self.display_var = tk.StringVar(value=initial_display)
        self.dropdown = ttk.Combobox(
            self,
            textvariable=self.display_var,
            values=list(self.OPTIONS.keys()),
            state='readonly',
            width=20
        )
        self.dropdown.pack(side=tk.LEFT)
        self.dropdown.bind('<<ComboboxSelected>>', self._on_selection_change)

    def _on_selection_change(self, event=None):
        """Handle selection change."""
        if not self._suppress_callbacks and self.on_change:
            self.on_change()

    def get_value(self) -> str:
        """Get the current display_target value ("both", "p1", or "p2")."""
        display_text = self.display_var.get()
        return self.OPTIONS.get(display_text, "both")

    def set_value(self, value: str):
        """Set the display_target value."""
        self._suppress_callbacks = True
        display_text = self.VALUE_TO_DISPLAY.get(value, "Both Participants")
        self.display_var.set(display_text)
        self._suppress_callbacks = False


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

        # Observer text (shown to the non-viewer participant in turn-taking)
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=1, column=0, columnspan=3, sticky='ew', pady=5)

        ttk.Label(self, text="Observer Text:").grid(row=2, column=0, sticky=tk.W, pady=2)
        # Determine current observer text: prefer observer_text field,
        # fall back to per-participant overrides for backward compatibility
        observer_text = phase.observer_text or ""
        self.observer_text_var = tk.StringVar(value=observer_text)
        ttk.Entry(self, textvariable=self.observer_text_var, width=40).grid(
            row=2, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        self.observer_text_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(
            self, text="Text shown to the non-viewer (leave empty for fixation cross on both)",
            font=('Arial', 8, 'italic')
        ).grid(row=3, column=1, sticky=tk.W, pady=(0, 5), padx=(5, 0))

        # Event Markers (new MarkerBinding system)
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['phase_start', 'phase_end'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=4, column=0, columnspan=3, sticky='ew', pady=10)

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

            # Observer text: shown to the non-viewer in turn-taking conditions.
            # FixationPhase.render() resolves display_target from trial data
            # and applies observer_text to the correct participant automatically.
            observer_text = self.observer_text_var.get().strip()
            self.phase.observer_text = observer_text if observer_text else None

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

        # Info label
        ttk.Label(
            self,
            text=(
                "Video is selected automatically from the trial list CSV.\n"
                "Display target is set per variant (P1 Viewer, P2 Viewer, Joint)."
            ),
            font=("Arial", 9, "italic"),
            foreground="gray"
        ).grid(row=0, column=0, columnspan=3, sticky=tk.W, pady=(0, 10))

        # Auto Advance
        self.auto_advance_var = tk.BooleanVar(value=phase.auto_advance)
        auto_advance_check = ttk.Checkbutton(
            self, text="Auto-advance when videos finish",
            variable=self.auto_advance_var,
            command=self._on_property_change
        )
        auto_advance_check.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

        # Event Markers (new MarkerBinding system)
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['video_start', 'video_p1_end', 'video_p2_end', 'video_both_complete'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def apply_changes(self):
        """Apply changes to the phase object."""
        try:
            self.phase.auto_advance = self.auto_advance_var.get()
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

        # P1 Question
        ttk.Label(self, text="P1 Question:").grid(row=0, column=0, sticky=tk.NW, pady=5)
        self.p1_question_text = scrolledtext.ScrolledText(self, width=40, height=3)
        p1_q = phase.participant_1_question or phase.question or ""
        self.p1_question_text.insert('1.0', p1_q)
        self.p1_question_text.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p1_question_text.bind('<<Modified>>', self._on_p1_text_modified)

        # P2 Question
        ttk.Label(self, text="P2 Question:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.p2_question_text = scrolledtext.ScrolledText(self, width=40, height=3)
        p2_q = phase.participant_2_question or phase.question or ""
        self.p2_question_text.insert('1.0', p2_q)
        self.p2_question_text.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p2_question_text.bind('<<Modified>>', self._on_p2_text_modified)

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)

        # P1 Rating Keys
        ttk.Label(self, text="P1 Rating Keys:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.p1_keys_var = tk.StringVar(value=phase.p1_keys)
        ttk.Entry(self, textvariable=self.p1_keys_var, width=20).grid(
            row=3, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p1_keys_var.trace_add('write', lambda *args: self._on_property_change())

        # P2 Rating Keys
        ttk.Label(self, text="P2 Rating Keys:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.p2_keys_var = tk.StringVar(value=phase.p2_keys)
        ttk.Entry(self, textvariable=self.p2_keys_var, width=20).grid(
            row=4, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p2_keys_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(
            self, text="One key per scale point, maps to values 1, 2, 3...",
            font=('Arial', 8, 'italic')
        ).grid(row=5, column=1, sticky=tk.W, pady=(0, 5), padx=(5, 0))

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=6, column=0, columnspan=2, sticky='ew', pady=5)

        # Observer Beep
        self.observer_beep_var = tk.BooleanVar(value=phase.observer_beep)
        ttk.Checkbutton(
            self, text="Play audio beep for observer at rating start",
            variable=self.observer_beep_var,
            command=self._on_property_change
        ).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=2)

        ttk.Label(
            self, text="Turn-taking only: plays a 0.5s tone on the observer's audio device",
            font=('Arial', 8, 'italic')
        ).grid(row=8, column=0, columnspan=2, sticky=tk.W, pady=(0, 5), padx=(5, 0))

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=9, column=0, columnspan=2, sticky='ew', pady=5)

        # Event Markers
        self.marker_bindings_widget = MarkerBindingListWidget(
            self,
            bindings=phase.marker_bindings,
            available_events=['p1_response', 'p2_response'],
            on_change=self._on_property_change,
            label="LSL Event Markers"
        )
        self.marker_bindings_widget.grid(row=10, column=0, columnspan=2, sticky='ew', pady=5)

    def _on_p1_text_modified(self, event=None):
        """Handle P1 question text modification."""
        if self.p1_question_text.edit_modified():
            self.p1_question_text.edit_modified(False)
            self._on_property_change()

    def _on_p2_text_modified(self, event=None):
        """Handle P2 question text modification."""
        if self.p2_question_text.edit_modified():
            self.p2_question_text.edit_modified(False)
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
            # Questions
            p1_q = self.p1_question_text.get('1.0', 'end-1c').strip()
            p2_q = self.p2_question_text.get('1.0', 'end-1c').strip()
            self.phase.participant_1_question = p1_q if p1_q else None
            self.phase.participant_2_question = p2_q if p2_q else None
            self.phase.question = p1_q or p2_q or self.phase.question

            # Key bindings
            p1_keys = self.p1_keys_var.get().strip()
            p2_keys = self.p2_keys_var.get().strip()
            if p1_keys:
                self.phase.p1_keys = p1_keys
            if p2_keys:
                self.phase.p2_keys = p2_keys

            # Auto-derive scale from key length
            self.phase.scale_min = 1
            self.phase.scale_max = max(len(self.phase.p1_keys), len(self.phase.p2_keys))

            # Observer beep
            self.phase.observer_beep = self.observer_beep_var.get()

            # Marker bindings
            self.phase.marker_bindings = self.marker_bindings_widget.get_bindings()

            # Always both participants, no timeout
            self.phase.display_target = "both"
            self.phase.timeout = None
        except ValueError:
            pass  # Ignore invalid values during typing


class InstructionPhaseEditor(ttk.LabelFrame):
    """Editor for InstructionPhase properties."""

    def __init__(self, parent, phase: InstructionPhase, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Instruction Phase Properties", padding=10)

        self.phase = phase
        self.on_change = on_change
        self._suppress_callbacks = False

        # P1 Instructions
        ttk.Label(self, text="P1 Instructions:").grid(row=0, column=0, sticky=tk.NW, pady=5)
        self.p1_text_widget = scrolledtext.ScrolledText(self, width=50, height=4)
        p1_text = phase.participant_1_text or phase.text or ""
        self.p1_text_widget.insert('1.0', p1_text)
        self.p1_text_widget.grid(row=0, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p1_text_widget.bind('<<Modified>>', self._on_p1_text_modified)

        # P2 Instructions
        ttk.Label(self, text="P2 Instructions:").grid(row=1, column=0, sticky=tk.NW, pady=5)
        self.p2_text_widget = scrolledtext.ScrolledText(self, width=50, height=4)
        p2_text = phase.participant_2_text or phase.text or ""
        self.p2_text_widget.insert('1.0', p2_text)
        self.p2_text_widget.grid(row=1, column=1, sticky=tk.W, pady=5, padx=(5, 0))
        self.p2_text_widget.bind('<<Modified>>', self._on_p2_text_modified)

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(row=2, column=0, columnspan=2, sticky='ew', pady=10)

        # Continue Keys
        ttk.Label(self, text="P1 Continue Key:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.p1_key_var = tk.StringVar(value=phase.p1_continue_key or "space")
        ttk.Entry(self, textvariable=self.p1_key_var, width=20).grid(
            row=3, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        self.p1_key_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(self, text="P2 Continue Key:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.p2_key_var = tk.StringVar(value=phase.p2_continue_key or "space")
        ttk.Entry(self, textvariable=self.p2_key_var, width=20).grid(
            row=4, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        self.p2_key_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(
            self, text="e.g. 'space', 'enter' — with keyboard routing, both can use the same key",
            font=('Arial', 8, 'italic')
        ).grid(row=5, column=1, sticky=tk.W, pady=(0, 5), padx=(5, 0))

        # Waiting Message
        ttk.Label(self, text="Waiting Message:").grid(row=6, column=0, sticky=tk.W, pady=2)
        self.waiting_msg_var = tk.StringVar(value=phase.waiting_message or "(waiting for partner)")
        ttk.Entry(self, textvariable=self.waiting_msg_var, width=40).grid(
            row=6, column=1, sticky=tk.W, pady=2, padx=(5, 0))
        self.waiting_msg_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Label(
            self, text="Shown after a participant presses their key while waiting for the other",
            font=('Arial', 8, 'italic')
        ).grid(row=7, column=0, columnspan=2, sticky=tk.W, pady=(0, 5), padx=(5, 0))

    def _on_p1_text_modified(self, event=None):
        """Handle P1 text modification."""
        if self.p1_text_widget.edit_modified():
            self.p1_text_widget.edit_modified(False)
            self._on_property_change()

    def _on_p2_text_modified(self, event=None):
        """Handle P2 text modification."""
        if self.p2_text_widget.edit_modified():
            self.p2_text_widget.edit_modified(False)
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
            # Per-participant text
            p1_text = self.p1_text_widget.get('1.0', 'end-1c').strip()
            p2_text = self.p2_text_widget.get('1.0', 'end-1c').strip()
            self.phase.participant_1_text = p1_text if p1_text else None
            self.phase.participant_2_text = p2_text if p2_text else None
            self.phase.text = p1_text or p2_text or self.phase.text

            # Per-participant continue keys (always dual-acknowledge)
            p1_key = self.p1_key_var.get().strip()
            p2_key = self.p2_key_var.get().strip()
            self.phase.p1_continue_key = p1_key if p1_key else "space"
            self.phase.p2_continue_key = p2_key if p2_key else "space"

            # Legacy continue_key is no longer user-editable; clear it
            # so the runtime always takes the dual-acknowledge path
            self.phase.continue_key = None

            waiting_msg = self.waiting_msg_var.get().strip()
            self.phase.waiting_message = waiting_msg if waiting_msg else None

            # Always wait for key, always both, no duration
            self.phase.wait_for_key = True
            self.phase.duration = None
            self.phase.display_target = "both"
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
