"""
Pre-execution dialogs for subject info and headset selection.

Provides dialogs for:
- Subject ID and session number entry
- EEG headset assignment (B16 or B1A)
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Tuple
from .base_dialog import BaseDialog


class SubjectSessionDialog(BaseDialog):
    """
    Dialog for entering subject ID and session number.

    Features:
    - Integer-only input fields
    - Info about setting to 0 to disable data saving
    - Validation
    """

    def __init__(self, parent):
        """
        Initialize subject/session dialog.

        Args:
            parent: Parent window
        """
        self.dialog_description = "Enter subject and session information.\nSet either field to 0 to disable data saving."
        self.subject_var = tk.StringVar(value="1")
        self.session_var = tk.StringVar(value="1")

        super().__init__(parent, title="Subject & Session Info", width=350)

    def _build_content(self, content_frame):
        """Build the dialog content."""
        # Subject ID field
        subject_frame = ttk.Frame(content_frame)
        subject_frame.pack(fill=tk.X, pady=5)

        ttk.Label(subject_frame, text="Subject ID:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        subject_entry = ttk.Entry(subject_frame, textvariable=self.subject_var, width=10)
        subject_entry.pack(side=tk.LEFT, padx=5)

        # Validate integer input
        vcmd = (self.register(self._validate_integer), '%P')
        subject_entry.config(validate='key', validatecommand=vcmd)

        # Session number field
        session_frame = ttk.Frame(content_frame)
        session_frame.pack(fill=tk.X, pady=5)

        ttk.Label(session_frame, text="Session:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)
        session_entry = ttk.Entry(session_frame, textvariable=self.session_var, width=10)
        session_entry.pack(side=tk.LEFT, padx=5)
        session_entry.config(validate='key', validatecommand=vcmd)

        # Info label
        info_label = ttk.Label(
            content_frame,
            text="💡 Tip: Set to 0 to disable data saving\n(useful for testing)",
            font=("Arial", 9),
            foreground="#666666"
        )
        info_label.pack(pady=10)

        # Focus on subject field
        subject_entry.focus_set()
        subject_entry.select_range(0, tk.END)

    def _validate_integer(self, value):
        """Validate that input is an integer."""
        if value == "":
            return True
        try:
            int(value)
            return True
        except ValueError:
            return False

    def _validate(self):
        """Validate the inputs."""
        errors = []

        if not self.subject_var.get():
            errors.append("Subject ID is required")
        if not self.session_var.get():
            errors.append("Session number is required")

        try:
            subject_id = int(self.subject_var.get())
            if subject_id < 0:
                errors.append("Subject ID cannot be negative")
        except ValueError:
            errors.append("Subject ID must be a number")

        try:
            session = int(self.session_var.get())
            if session < 0:
                errors.append("Session number cannot be negative")
        except ValueError:
            errors.append("Session number must be a number")

        return errors

    def _collect_result(self):
        """Collect dialog result."""
        return {
            'subject_id': int(self.subject_var.get()),
            'session': int(self.session_var.get())
        }

    @classmethod
    def prompt(cls, parent) -> Optional[Tuple[int, int]]:
        """
        Show dialog and return result.

        Args:
            parent: Parent window

        Returns:
            (subject_id, session) tuple, or None if cancelled
        """
        dialog = cls(parent)
        parent.wait_window(dialog)

        if dialog.result:
            return (dialog.result['subject_id'], dialog.result['session'])
        return None


class HeadsetSelectionDialog(BaseDialog):
    """
    Dialog for selecting which EEG headset is assigned to Participant 1.

    Features:
    - Radio button selection: B16 or B1A
    - LSL marker info (9161 for B16, 9162 for Other)
    - Visual instructions
    """

    def __init__(self, parent):
        """
        Initialize headset selection dialog.

        Args:
            parent: Parent window
        """
        self.dialog_description = "Select which EEG headset is assigned to Participant 1.\nThis will send an LSL marker for data pairing."
        self.headset_var = tk.StringVar(value="B16")

        super().__init__(parent, title="Headset Selection", width=400)

    def _build_content(self, content_frame):
        """Build the dialog content."""
        # Instructions
        instructions = ttk.Label(
            content_frame,
            text="Which headset is Participant 1 wearing?",
            font=("Arial", 11, "bold")
        )
        instructions.pack(pady=(5, 15))

        # Radio buttons frame
        radio_frame = ttk.LabelFrame(content_frame, text="Headset Assignment", padding=10)
        radio_frame.pack(fill=tk.X, padx=20, pady=10)

        # B16 option
        b16_radio = ttk.Radiobutton(
            radio_frame,
            text="B16 Headset",
            variable=self.headset_var,
            value="B16"
        )
        b16_radio.pack(anchor=tk.W, pady=5)

        b16_info = ttk.Label(
            radio_frame,
            text="    → Will send LSL marker: 9161",
            font=("Arial", 9),
            foreground="#666666"
        )
        b16_info.pack(anchor=tk.W, padx=20)

        # Other option
        other_radio = ttk.Radiobutton(
            radio_frame,
            text="B1A Headset",
            variable=self.headset_var,
            value="B1A"
        )
        other_radio.pack(anchor=tk.W, pady=(10, 5))

        other_info = ttk.Label(
            radio_frame,
            text="    → Will send LSL marker: 9162",
            font=("Arial", 9),
            foreground="#666666"
        )
        other_info.pack(anchor=tk.W, padx=20)

        # Note about data pairing
        note = ttk.Label(
            content_frame,
            text="This marker helps pair EEG data with the correct participant\nduring post-hoc analysis.",
            font=("Arial", 9, "italic"),
            foreground="#555555",
            justify=tk.CENTER
        )
        note.pack(pady=(10, 5))

    def _validate(self):
        """Validate the selection."""
        errors = []

        if not self.headset_var.get():
            errors.append("Please select a headset")
        elif self.headset_var.get() not in ['B16', 'B1A']:
            errors.append("Invalid headset selection")

        return errors

    def _collect_result(self):
        """Collect dialog result."""
        return {
            'headset': self.headset_var.get()
        }

    @classmethod
    def prompt(cls, parent) -> Optional[str]:
        """
        Show dialog and return result.

        Args:
            parent: Parent window

        Returns:
            'B16' or 'B1A', or None if cancelled
        """
        dialog = cls(parent)
        parent.wait_window(dialog)

        if dialog.result:
            return dialog.result['headset']
        return None
