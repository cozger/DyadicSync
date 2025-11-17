"""
Procedure Editor Dialog.

Allows editing of Procedure objects (phase sequences).

Features:
- Phase list view with add/remove/reorder
- Edit phase button (opens phase config dialogs)
- Required variables display
- Duration estimation
- Drag-and-drop reordering (future)
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List, Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from timeline_editor.dialogs.base_dialog import BaseDialog
from core.execution.procedure import Procedure
from core.execution.phase import Phase
from core.execution.phases.fixation_phase import FixationPhase
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.phases.instruction_phase import InstructionPhase
from core.execution.phases.baseline_phase import BaselinePhase


class ProcedureEditorDialog(BaseDialog):
    """
    Dialog for editing Procedure (phase sequence).

    Layout:
    - Left: Phase list (listbox)
    - Right: Controls (Add Phase dropdown, Edit, Remove, Move Up/Down)
    - Bottom: Required variables, estimated duration
    """

    # Phase type mapping
    PHASE_TYPES = {
        'Fixation': FixationPhase,
        'Video': VideoPhase,
        'Rating': RatingPhase,
        'Instruction': InstructionPhase,
        'Baseline': BaselinePhase
    }

    # Phase type icons/prefixes
    PHASE_ICONS = {
        'FixationPhase': '⊕',
        'VideoPhase': '▶',
        'RatingPhase': '☆',
        'InstructionPhase': '📄',
        'BaselinePhase': '—'
    }

    def __init__(self, parent, procedure: Procedure, block_type: str = 'simple'):
        """
        Initialize procedure editor dialog.

        Args:
            parent: Parent window
            procedure: Procedure to edit
            block_type: 'simple' or 'trial_based' (affects available phases)
        """
        self.procedure = procedure
        self.block_type = block_type
        self.selected_phase_index: Optional[int] = None

        super().__init__(parent, f"Edit Procedure: {procedure.name}", width=700, height=500)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Main split: phase list (left) + controls (right)
        main_pane = ttk.PanedWindow(content_frame, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # === Left: Phase List ===
        left_frame = ttk.Frame(main_pane)
        main_pane.add(left_frame, weight=3)

        ttk.Label(left_frame, text="Phase Sequence:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        # Listbox with scrollbar
        list_frame = ttk.Frame(left_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.phase_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=("Courier", 10),
            height=15
        )
        scrollbar.config(command=self.phase_listbox.yview)

        self.phase_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind selection
        self.phase_listbox.bind('<<ListboxSelect>>', self._on_phase_select)
        self.phase_listbox.bind('<Double-Button-1>', lambda e: self._edit_selected_phase())

        # Populate list
        self._refresh_phase_list()

        # === Right: Controls ===
        right_frame = ttk.Frame(main_pane)
        main_pane.add(right_frame, weight=1)

        ttk.Label(right_frame, text="Controls:", font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))

        # Add Phase dropdown button
        add_frame = ttk.Frame(right_frame)
        add_frame.pack(fill=tk.X, pady=5)

        add_button = ttk.Menubutton(add_frame, text="Add Phase ▼", width=20)
        add_button.pack(fill=tk.X)

        add_menu = tk.Menu(add_button, tearoff=0)
        add_button.config(menu=add_menu)

        for phase_name in self.PHASE_TYPES.keys():
            add_menu.add_command(
                label=phase_name,
                command=lambda name=phase_name: self._add_phase(name)
            )

        # Edit Phase button
        ttk.Button(
            right_frame,
            text="Edit Phase",
            command=self._edit_selected_phase,
            width=20
        ).pack(fill=tk.X, pady=5)

        # Remove Phase button
        ttk.Button(
            right_frame,
            text="Remove Phase",
            command=self._remove_selected_phase,
            width=20
        ).pack(fill=tk.X, pady=5)

        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Move Up button
        ttk.Button(
            right_frame,
            text="▲ Move Up",
            command=self._move_phase_up,
            width=20
        ).pack(fill=tk.X, pady=2)

        # Move Down button
        ttk.Button(
            right_frame,
            text="▼ Move Down",
            command=self._move_phase_down,
            width=20
        ).pack(fill=tk.X, pady=2)

        ttk.Separator(right_frame, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=10)

        # Duplicate button
        ttk.Button(
            right_frame,
            text="Duplicate Phase",
            command=self._duplicate_selected_phase,
            width=20
        ).pack(fill=tk.X, pady=5)

        # === Bottom: Info Panel ===
        info_frame = ttk.LabelFrame(content_frame, text="Procedure Info", padding=5)
        info_frame.pack(fill=tk.X, pady=(10, 0))

        # Required variables
        self.required_vars_label = ttk.Label(
            info_frame,
            text="Required Variables: (none)",
            font=("Arial", 9)
        )
        self.required_vars_label.pack(anchor=tk.W)

        # Estimated duration
        self.duration_label = ttk.Label(
            info_frame,
            text="Estimated Duration: 0s per trial",
            font=("Arial", 9)
        )
        self.duration_label.pack(anchor=tk.W)

        # Update info
        self._update_info()

    def _refresh_phase_list(self):
        """Refresh the phase listbox."""
        self.phase_listbox.delete(0, tk.END)

        for i, phase in enumerate(self.procedure.phases):
            icon = self.PHASE_ICONS.get(phase.__class__.__name__, '•')
            phase_name = phase.__class__.__name__.replace('Phase', '')

            # Build display string with key info
            info = self._get_phase_info(phase)
            display = f"{i+1}. {icon} {phase_name:12s} {info}"

            self.phase_listbox.insert(tk.END, display)

    def _get_phase_info(self, phase: Phase) -> str:
        """Get summary info string for a phase."""
        if isinstance(phase, FixationPhase):
            return f"({phase.duration}s)"
        elif isinstance(phase, VideoPhase):
            return f"(P1: {phase.participant_1_video}, P2: {phase.participant_2_video})"
        elif isinstance(phase, RatingPhase):
            return f"(Question: {phase.question[:20]}...)"
        elif isinstance(phase, InstructionPhase):
            text_preview = phase.text[:30] + "..." if len(phase.text) > 30 else phase.text
            return f'("{text_preview}")'
        elif isinstance(phase, BaselinePhase):
            return f"({phase.duration}s)"
        else:
            return ""

    def _update_info(self):
        """Update required variables and duration display."""
        # Required variables
        required_vars = self.procedure.get_required_variables()
        if required_vars:
            vars_str = ", ".join(sorted(required_vars))
            self.required_vars_label.config(text=f"Required Variables: {vars_str}")
        else:
            self.required_vars_label.config(text="Required Variables: (none)")

        # Estimated duration
        duration = self.procedure.get_estimated_duration()
        mins = int(duration // 60)
        secs = int(duration % 60)
        if mins > 0:
            self.duration_label.config(text=f"Estimated Duration: {mins}m {secs}s per trial")
        else:
            self.duration_label.config(text=f"Estimated Duration: {secs}s per trial")

    def _on_phase_select(self, event):
        """Handle phase selection in listbox."""
        selection = self.phase_listbox.curselection()
        if selection:
            self.selected_phase_index = selection[0]
        else:
            self.selected_phase_index = None

    def _add_phase(self, phase_type_name: str):
        """
        Add a new phase to the procedure.

        Args:
            phase_type_name: Name of phase type (e.g., 'Fixation')
        """
        phase_class = self.PHASE_TYPES[phase_type_name]

        # Create default phase
        if phase_type_name == 'Fixation':
            phase = FixationPhase(duration=3.0)
        elif phase_type_name == 'Video':
            phase = VideoPhase(p1_video="{video1}", p2_video="{video2}")
        elif phase_type_name == 'Rating':
            phase = RatingPhase(question="How did you feel?", scale_type='likert7')
        elif phase_type_name == 'Instruction':
            phase = InstructionPhase(text="Instruction text here...", wait_for_key=True)
        elif phase_type_name == 'Baseline':
            phase = BaselinePhase(duration=240)
        else:
            messagebox.showerror("Error", f"Unknown phase type: {phase_type_name}")
            return

        # Add to procedure
        if self.selected_phase_index is not None:
            # Insert after selected
            self.procedure.phases.insert(self.selected_phase_index + 1, phase)
            new_index = self.selected_phase_index + 1
        else:
            # Append to end
            self.procedure.add_phase(phase)
            new_index = len(self.procedure.phases) - 1

        # Refresh and select new phase
        self._refresh_phase_list()
        self.phase_listbox.selection_clear(0, tk.END)
        self.phase_listbox.selection_set(new_index)
        self.phase_listbox.see(new_index)
        self.selected_phase_index = new_index

        self._update_info()

        # Auto-open edit dialog for new phase
        self._edit_selected_phase()

    def _edit_selected_phase(self):
        """Edit the selected phase."""
        if self.selected_phase_index is None:
            messagebox.showinfo("No Selection", "Please select a phase to edit")
            return

        phase = self.procedure.phases[self.selected_phase_index]

        # Import phase config dialogs
        from timeline_editor.dialogs.phase_configs import get_phase_config_dialog

        # Get appropriate dialog for phase type
        dialog_class = get_phase_config_dialog(phase.__class__.__name__)

        if dialog_class is None:
            messagebox.showerror("Error", f"No configuration dialog for {phase.__class__.__name__}")
            return

        # Open dialog
        dialog = dialog_class(self, phase)
        result = dialog.show()

        if result:
            # Update phase with new values
            for key, value in result.items():
                if hasattr(phase, key):
                    setattr(phase, key, value)

            # Refresh display
            self._refresh_phase_list()
            self.phase_listbox.selection_set(self.selected_phase_index)
            self._update_info()

    def _remove_selected_phase(self):
        """Remove the selected phase."""
        if self.selected_phase_index is None:
            messagebox.showinfo("No Selection", "Please select a phase to remove")
            return

        phase = self.procedure.phases[self.selected_phase_index]
        phase_name = phase.__class__.__name__.replace('Phase', '')

        if messagebox.askyesno("Confirm Remove", f"Remove {phase_name} phase?"):
            del self.procedure.phases[self.selected_phase_index]
            self._refresh_phase_list()
            self.selected_phase_index = None
            self._update_info()

    def _move_phase_up(self):
        """Move selected phase up in the sequence."""
        if self.selected_phase_index is None or self.selected_phase_index == 0:
            return

        # Swap with previous
        idx = self.selected_phase_index
        self.procedure.phases[idx], self.procedure.phases[idx - 1] = \
            self.procedure.phases[idx - 1], self.procedure.phases[idx]

        # Refresh and maintain selection
        self._refresh_phase_list()
        self.selected_phase_index = idx - 1
        self.phase_listbox.selection_set(self.selected_phase_index)
        self.phase_listbox.see(self.selected_phase_index)

    def _move_phase_down(self):
        """Move selected phase down in the sequence."""
        if self.selected_phase_index is None or \
           self.selected_phase_index >= len(self.procedure.phases) - 1:
            return

        # Swap with next
        idx = self.selected_phase_index
        self.procedure.phases[idx], self.procedure.phases[idx + 1] = \
            self.procedure.phases[idx + 1], self.procedure.phases[idx]

        # Refresh and maintain selection
        self._refresh_phase_list()
        self.selected_phase_index = idx + 1
        self.phase_listbox.selection_set(self.selected_phase_index)
        self.phase_listbox.see(self.selected_phase_index)

    def _duplicate_selected_phase(self):
        """Duplicate the selected phase."""
        if self.selected_phase_index is None:
            messagebox.showinfo("No Selection", "Please select a phase to duplicate")
            return

        phase = self.procedure.phases[self.selected_phase_index]

        # Serialize and deserialize for deep copy
        phase_data = phase.to_dict()
        from core.execution.phases import phase_from_dict
        new_phase = phase_from_dict(phase_data)

        # Insert after selected
        self.procedure.phases.insert(self.selected_phase_index + 1, new_phase)

        # Refresh and select new phase
        self._refresh_phase_list()
        new_index = self.selected_phase_index + 1
        self.phase_listbox.selection_clear(0, tk.END)
        self.phase_listbox.selection_set(new_index)
        self.phase_listbox.see(new_index)
        self.selected_phase_index = new_index

        self._update_info()

    def _validate(self) -> List[str]:
        """Validate procedure."""
        errors = []

        if len(self.procedure.phases) == 0:
            errors.append("Procedure must have at least one phase")

        # Validate each phase
        for i, phase in enumerate(self.procedure.phases):
            phase_errors = phase.validate()
            for err in phase_errors:
                errors.append(f"Phase {i+1}: {err}")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Return the modified procedure."""
        return {'procedure': self.procedure, 'modified': True}
