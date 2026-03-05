"""
Instruction Phase Configuration Dialog.

Configures InstructionPhase parameters:
- P1 instruction text
- P2 instruction text
- Continue key(s) - if two keys, both must be pressed
- Per-participant confirmation with waiting message
"""

import tkinter as tk
from tkinter import ttk
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from core.execution.phases.instruction_phase import InstructionPhase


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
        super().__init__(parent, "Configure Instruction Phase", width=500, height=600)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Per-participant instructions
        text_frame = ttk.LabelFrame(content_frame, text="Instructions", padding=10)
        text_frame.pack(fill=tk.X, pady=10)

        # P1 Text
        p1_frame = ttk.Frame(text_frame)
        p1_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p1_frame, text="P1 Text:").pack(anchor=tk.W)
        self.p1_text_widget = tk.Text(p1_frame, height=4, width=55)
        self.p1_text_widget.pack(fill=tk.X, expand=True, padx=5, pady=2)
        p1_text = self.phase.participant_1_text or self.phase.text or ""
        if p1_text:
            self.p1_text_widget.insert('1.0', p1_text)

        # P2 Text
        p2_frame = ttk.Frame(text_frame)
        p2_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p2_frame, text="P2 Text:").pack(anchor=tk.W)
        self.p2_text_widget = tk.Text(p2_frame, height=4, width=55)
        self.p2_text_widget.pack(fill=tk.X, expand=True, padx=5, pady=2)
        p2_text = self.phase.participant_2_text or self.phase.text or ""
        if p2_text:
            self.p2_text_widget.insert('1.0', p2_text)

        # Continue key(s) - legacy single-key mode
        key_frame = ttk.LabelFrame(content_frame, text="Continue Key(s)", padding=10)
        key_frame.pack(fill=tk.X, pady=10)

        key_entry_frame = ttk.Frame(key_frame)
        key_entry_frame.pack(fill=tk.X, pady=2)
        ttk.Label(key_entry_frame, text="Key(s):", width=8).pack(side=tk.LEFT)
        self.continue_key_var = tk.StringVar(value=self.phase.continue_key or "space")
        ttk.Entry(key_entry_frame, textvariable=self.continue_key_var, width=20).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            key_frame,
            text="e.g. 'space' or 'space, enter' (two keys = both must be pressed)",
            font=("Arial", 8),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(5, 0))

        # Per-participant confirmation section
        confirm_frame = ttk.LabelFrame(content_frame, text="Per-Participant Confirmation (Optional)", padding=10)
        confirm_frame.pack(fill=tk.X, pady=10)

        # P1 Key
        p1_key_frame = ttk.Frame(confirm_frame)
        p1_key_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p1_key_frame, text="P1 Key:", width=15).pack(side=tk.LEFT)
        self.p1_key_var = tk.StringVar(value=self.phase.p1_continue_key or "")
        ttk.Entry(p1_key_frame, textvariable=self.p1_key_var, width=15).pack(side=tk.LEFT, padx=5)

        # P2 Key
        p2_key_frame = ttk.Frame(confirm_frame)
        p2_key_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p2_key_frame, text="P2 Key:", width=15).pack(side=tk.LEFT)
        self.p2_key_var = tk.StringVar(value=self.phase.p2_continue_key or "")
        ttk.Entry(p2_key_frame, textvariable=self.p2_key_var, width=15).pack(side=tk.LEFT, padx=5)

        # Waiting Message
        msg_frame = ttk.Frame(confirm_frame)
        msg_frame.pack(fill=tk.X, pady=2)
        ttk.Label(msg_frame, text="Waiting Message:", width=15).pack(side=tk.LEFT)
        self.waiting_msg_var = tk.StringVar(
            value=self.phase.waiting_message or "(waiting for partner)")
        ttk.Entry(msg_frame, textvariable=self.waiting_msg_var, width=35).pack(side=tk.LEFT, padx=5)

        ttk.Label(
            confirm_frame,
            text="When both keys are set, each participant must press their own key.\n"
                 "After pressing, they see the waiting message until partner presses too.",
            font=("Arial", 8),
            foreground="gray"
        ).pack(anchor=tk.W, pady=(5, 0))

    def _validate(self) -> List[str]:
        """Validate instruction config."""
        errors = []

        p1_text = self.p1_text_widget.get("1.0", tk.END).strip()
        p2_text = self.p2_text_widget.get("1.0", tk.END).strip()
        if not p1_text and not p2_text:
            errors.append("At least one instruction text is required")

        # Validate per-participant keys
        p1_key = self.p1_key_var.get().strip()
        p2_key = self.p2_key_var.get().strip()
        if (p1_key and not p2_key) or (p2_key and not p1_key):
            errors.append("Both P1 and P2 keys must be set for per-participant confirmation")

        if p1_key and p2_key:
            if InstructionPhase._resolve_key_name(p1_key) is None:
                errors.append(f"Invalid P1 key: '{p1_key}'")
            if InstructionPhase._resolve_key_name(p2_key) is None:
                errors.append(f"Invalid P2 key: '{p2_key}'")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect instruction config."""
        p1_text = self.p1_text_widget.get("1.0", tk.END).strip()
        p2_text = self.p2_text_widget.get("1.0", tk.END).strip()
        continue_key = self.continue_key_var.get().strip() or "space"

        p1_key = self.p1_key_var.get().strip()
        p2_key = self.p2_key_var.get().strip()
        waiting_msg = self.waiting_msg_var.get().strip()

        return {
            'participant_1_text': p1_text if p1_text else None,
            'participant_2_text': p2_text if p2_text else None,
            'text': p1_text or p2_text,
            'continue_key': continue_key,
            'wait_for_key': True,
            'duration': None,
            'display_target': 'both',
            'p1_continue_key': p1_key if p1_key else None,
            'p2_continue_key': p2_key if p2_key else None,
            'waiting_message': waiting_msg if waiting_msg else None
        }
