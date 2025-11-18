"""
Block-level property editors for DyadicSync Timeline Editor.

Provides widgets for editing block properties, procedures, trial lists, and randomization.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Optional, Callable, List, Set
import random
import os
from core.execution.block import Block, RandomizationConfig
from core.execution.procedure import Procedure
from core.execution.phase import Phase
from core.execution.phases.fixation_phase import FixationPhase
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.phases.instruction_phase import InstructionPhase
from core.execution.phases.baseline_phase import BaselinePhase
from core.execution.trial_list import TrialList
from gui.phase_widgets import PhasePropertyEditor


class BlockInfoEditor(ttk.LabelFrame):
    """Editor for basic block properties (name, type, stats)."""

    def __init__(self, parent, block: Block, timeline=None, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Block Information", padding=10)

        self.block = block
        self.timeline = timeline
        self.on_change = on_change
        self._suppress_callbacks = False
        self._original_name = block.name  # Store original name for validation

        # Configure column weights so widgets expand to fill width
        self.columnconfigure(1, weight=1)

        # Block Name
        ttk.Label(self, text="Block Name:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.name_var = tk.StringVar(value=block.name)
        name_entry = ttk.Entry(self, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(5, 0))
        self.name_var.trace_add('write', lambda *args: self._on_property_change())

        # Block Type
        ttk.Label(self, text="Block Type:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.type_var = tk.StringVar(value=block.block_type)
        type_frame = ttk.Frame(self)
        type_frame.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(5, 0))

        ttk.Radiobutton(
            type_frame, text="Simple (no trials)",
            variable=self.type_var, value='simple',
            command=self._on_type_change
        ).pack(anchor=tk.W, pady=2)

        ttk.Radiobutton(
            type_frame, text="Trial-based (with trial list)",
            variable=self.type_var, value='trial_based',
            command=self._on_type_change
        ).pack(anchor=tk.W, pady=2)

        # Read-only stats
        ttk.Separator(self, orient=tk.HORIZONTAL).grid(
            row=2, column=0, columnspan=2, sticky=tk.EW, pady=10
        )

        # Estimated Duration
        ttk.Label(self, text="Estimated Duration:").grid(row=3, column=0, sticky=tk.W, pady=2)
        self.duration_label = ttk.Label(self, text=self._get_duration_text(), font=('Arial', 9))
        self.duration_label.grid(row=3, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

        # Recalculate Duration Button
        self.recalc_button = ttk.Button(
            self, text="Recalculate", command=self._recalculate_duration
        )
        self.recalc_button.grid(row=3, column=2, sticky=tk.E, pady=2, padx=(5, 0))

        # Trial Count (if trial_based)
        ttk.Label(self, text="Trial Count:").grid(row=4, column=0, sticky=tk.W, pady=2)
        self.trial_count_label = ttk.Label(self, text=self._get_trial_count_text(), font=('Arial', 9))
        self.trial_count_label.grid(row=4, column=1, sticky=tk.EW, pady=2, padx=(5, 0))

    def _get_duration_text(self) -> str:
        """Get estimated duration as formatted string."""
        print(f"[GET_DURATION_TEXT] Called for block '{self.block.name}'")

        if not self.block.procedure:
            print(f"[GET_DURATION_TEXT] No procedure, returning 'Unknown'")
            return "Unknown (no procedure)"

        # Check if accurate duration has been calculated
        if hasattr(self.block, '_cached_duration') and self.block._cached_duration is not None:
            from utilities.format_utils import format_duration_compact
            cached_val = self.block._cached_duration
            formatted = format_duration_compact(cached_val)
            print(f"[GET_DURATION_TEXT] Using cached duration: {cached_val:.2f}s → '{formatted}'")
            return formatted

        # Fall back to estimated duration
        duration = self.block.get_estimated_duration()
        print(f"[GET_DURATION_TEXT] No cached duration, using estimated: {duration}")
        if duration < 0:
            return "Variable (depends on trials)"

        minutes = int(duration // 60)
        seconds = int(duration % 60)
        if minutes > 0:
            result = f"{minutes}m {seconds}s"
        else:
            result = f"{seconds}s"
        print(f"[GET_DURATION_TEXT] Returning: '{result}'")
        return result

    def _get_trial_count_text(self) -> str:
        """Get trial count as formatted string."""
        if self.block.block_type == 'simple':
            return "N/A (simple block)"

        count = self.block.get_trial_count()
        if count == 0:
            return "0 (no trial list loaded)"
        else:
            return str(count)

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def _on_type_change(self):
        """Handle block type change."""
        if not self._suppress_callbacks:
            # Type change may affect trial list visibility
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def _recalculate_duration(self):
        """Manually trigger duration calculation for current block."""
        print(f"[RECALCULATE] User requested duration recalculation for block '{self.block.name}'")

        # Clear cached duration to force recalculation
        self.block.invalidate_duration_cache()

        # Clear LRU cache for video durations (in case files changed)
        from utilities.video_duration import clear_duration_cache
        clear_duration_cache()

        # Recalculate duration
        print(f"[RECALCULATE] Calling calculate_accurate_duration()...")
        duration = self.block.calculate_accurate_duration()
        print(f"[RECALCULATE] Calculation complete. Result: {duration}")
        print(f"[RECALCULATE] Block._cached_duration is now: {getattr(self.block, '_cached_duration', 'NOT SET')}")

        # Update the label
        print(f"[RECALCULATE] Calling refresh_stats()...")
        self.refresh_stats()

        # Force GUI update
        self.update_idletasks()
        print(f"[RECALCULATE] Called update_idletasks()")

        # NOTE: We don't call on_change() here because PropertyPanel._handle_change()
        # invalidates the duration cache, which would undo the calculation we just did.
        # The timeline canvas will update the next time it refreshes (e.g., when clicking
        # another block or when the timeline is saved/loaded).
        print(f"[RECALCULATE] Skipping on_change() to preserve cached duration")

        # Log result to console
        if duration is not None:
            from utilities.format_utils import format_duration_compact
            formatted = format_duration_compact(duration)
            print(f"[RECALCULATE] ✓ Duration recalculated: {formatted}")
        else:
            print(f"[RECALCULATE] ✗ Unable to calculate duration")

    def apply_changes(self):
        """Apply changes to the block object."""
        new_name = self.name_var.get().strip()

        # Validate name is not empty
        if not new_name:
            messagebox.showerror("Invalid Name", "Block name cannot be empty.")
            self.name_var.set(self._original_name)  # Revert to original
            return

        # Validate name uniqueness (if timeline is available and name changed)
        if self.timeline and new_name != self._original_name:
            # Check if name already exists in other blocks
            existing_names = {b.name for b in self.timeline.blocks if b is not self.block}
            if new_name in existing_names:
                messagebox.showerror(
                    "Duplicate Name",
                    f"A block named '{new_name}' already exists.\n\n"
                    f"Please choose a different name."
                )
                self.name_var.set(self._original_name)  # Revert to original
                return

        # Apply the name change
        self.block.name = new_name
        self._original_name = new_name  # Update original name

        # Handle block type change
        old_type = self.block.block_type
        new_type = self.type_var.get()

        if old_type != new_type:
            self.block.block_type = new_type
            # If switching to simple, clear trial list
            if new_type == 'simple':
                self.block.trial_list = None

    def load_block(self, block: Block):
        """
        Load a new block for editing.

        Args:
            block: Block to load
        """
        self.block = block
        self._original_name = block.name
        self.name_var.set(block.name)
        self.type_var.set(block.block_type)
        self.refresh_stats()

    def refresh_stats(self):
        """Refresh read-only statistics."""
        print(f"[REFRESH_STATS] Starting refresh for block '{self.block.name}'")
        duration_text = self._get_duration_text()
        trial_text = self._get_trial_count_text()
        print(f"[REFRESH_STATS] Setting duration label to: '{duration_text}'")
        print(f"[REFRESH_STATS] Setting trial count label to: '{trial_text}'")
        self.duration_label.config(text=duration_text)
        self.trial_count_label.config(text=trial_text)
        # Force Tkinter to process pending GUI updates immediately
        self.update_idletasks()
        print(f"[REFRESH_STATS] Refresh complete, update_idletasks() called")


class ProcedureListWidget(ttk.LabelFrame):
    """
    Widget for editing procedure (list of phases).

    Shows phase list with add/remove/reorder buttons and integrates with phase editor.
    """

    def __init__(self, parent, block: Block, phase_editor: PhasePropertyEditor, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Procedure (Phase List)", padding=10)

        self.block = block
        self.phase_editor = phase_editor
        self.on_change = on_change
        self._selected_phase_index: Optional[int] = None

        # Create procedure if doesn't exist
        if not self.block.procedure:
            self.block.procedure = Procedure(name=f"{block.name} Procedure")

        # Phase list
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)

        # Scrollable listbox for phases
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        self.phase_listbox = tk.Listbox(
            list_frame,
            height=6,
            yscrollcommand=scrollbar.set,
            font=('Arial', 9)
        )
        scrollbar.config(command=self.phase_listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.phase_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.phase_listbox.bind('<<ListboxSelect>>', self._on_phase_select)

        # Buttons for add/remove/reorder
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, pady=(5, 0))

        # Add phase dropdown menu
        self.add_button = ttk.Menubutton(button_frame, text="+ Add Phase")
        self.add_button.pack(side=tk.LEFT, padx=(0, 5))

        add_menu = tk.Menu(self.add_button, tearoff=0)
        add_menu.add_command(label="Fixation Phase", command=lambda: self._add_phase('fixation'))
        add_menu.add_command(label="Video Phase", command=lambda: self._add_phase('video'))
        add_menu.add_command(label="Rating Phase", command=lambda: self._add_phase('rating'))
        add_menu.add_command(label="Instruction Phase", command=lambda: self._add_phase('instruction'))
        add_menu.add_command(label="Baseline Phase", command=lambda: self._add_phase('baseline'))
        self.add_button.config(menu=add_menu)

        # Remove, Move Up, Move Down buttons
        ttk.Button(button_frame, text="Remove", command=self._remove_phase, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↑ Up", command=self._move_up, width=6).pack(side=tk.LEFT, padx=2)
        ttk.Button(button_frame, text="↓ Down", command=self._move_down, width=6).pack(side=tk.LEFT, padx=2)

        # Refresh list
        self._refresh_phase_list()

    def _refresh_phase_list(self):
        """Refresh the phase listbox."""
        self.phase_listbox.delete(0, tk.END)

        if not self.block.procedure:
            return

        SEPARATOR_INTERVAL = 8  # Add visual break every N phases

        for i, phase in enumerate(self.block.procedure.phases):
            # Add visual separator for long lists (every 8 phases)
            if i > 0 and i % SEPARATOR_INTERVAL == 0:
                self.phase_listbox.insert(tk.END, "  /---/ ---")

            # Format: "[1] Fixation (3.0s)"
            duration = phase.get_estimated_duration()
            duration_str = f"{duration}s" if duration >= 0 else "variable"
            display_text = f"[{i+1}] {phase.name} ({duration_str})"
            self.phase_listbox.insert(tk.END, display_text)

    def _listbox_index_to_phase_index(self, listbox_idx: int) -> Optional[int]:
        """Convert listbox index to phase index, accounting for separators."""
        SEPARATOR_INTERVAL = 8
        # Get the text to check if it's a separator
        try:
            text = self.phase_listbox.get(listbox_idx)
            if text.strip().startswith("/---/"):
                return None  # This is a separator, not a phase
        except:
            return None

        # Calculate phase index by subtracting separator count
        # Separators appear before phases 8, 16, 24, etc.
        # So separator count = listbox_idx // (SEPARATOR_INTERVAL + 1)
        separator_count = listbox_idx // (SEPARATOR_INTERVAL + 1)
        phase_idx = listbox_idx - separator_count
        return phase_idx if phase_idx < len(self.block.procedure.phases) else None

    def _phase_index_to_listbox_index(self, phase_idx: int) -> int:
        """Convert phase index to listbox index, accounting for separators."""
        SEPARATOR_INTERVAL = 8
        # Separator count = number of complete intervals before this phase
        separator_count = phase_idx // SEPARATOR_INTERVAL
        return phase_idx + separator_count

    def _on_phase_select(self, event):
        """Handle phase selection."""
        selection = self.phase_listbox.curselection()
        if selection:
            listbox_idx = selection[0]
            phase_idx = self._listbox_index_to_phase_index(listbox_idx)

            if phase_idx is None:
                # Selected a separator - clear selection
                self._selected_phase_index = None
                self.phase_editor.load_phase(None)
                self.phase_listbox.selection_clear(0, tk.END)
            else:
                self._selected_phase_index = phase_idx
                phase = self.block.procedure.phases[phase_idx]
                self.phase_editor.load_phase(phase)
        else:
            # Only clear phase properties if phase listbox has focus
            # This prevents spurious events from other widgets (e.g., marker list clicks)
            # from destroying the phase properties pane
            focused_widget = self.phase_listbox.focus_get()
            if focused_widget == self.phase_listbox:
                self._selected_phase_index = None
                self.phase_editor.load_phase(None)

    def _add_phase(self, phase_type: str):
        """Add a new phase to the procedure."""
        if not self.block.procedure:
            self.block.procedure = Procedure(name=f"{self.block.name} Procedure")

        # Create phase based on type
        if phase_type == 'fixation':
            phase = FixationPhase(name="Fixation", duration=3.0)
        elif phase_type == 'video':
            phase = VideoPhase(
                name="Video Playback",
                participant_1_video="{video1}",
                participant_2_video="{video2}"
            )
        elif phase_type == 'rating':
            phase = RatingPhase(name="Rating Collection")
        elif phase_type == 'instruction':
            phase = InstructionPhase(name="Instructions", text="Welcome!")
        elif phase_type == 'baseline':
            phase = BaselinePhase(name="Baseline", duration=240.0)
        else:
            return

        self.block.procedure.add_phase(phase)
        self._refresh_phase_list()

        # Invalidate duration cache when procedure changes
        self.block.invalidate_duration_cache()

        # Select the new phase (convert phase index to listbox index)
        new_phase_idx = len(self.block.procedure.phases) - 1
        new_listbox_idx = self._phase_index_to_listbox_index(new_phase_idx)
        self.phase_listbox.selection_clear(0, tk.END)
        self.phase_listbox.selection_set(new_listbox_idx)
        self.phase_listbox.see(new_listbox_idx)
        self._on_phase_select(None)

        if self.on_change:
            self.on_change()

    def _remove_phase(self):
        """Remove selected phase."""
        if self._selected_phase_index is None:
            messagebox.showwarning("No Selection", "Please select a phase to remove.")
            return

        if not messagebox.askyesno("Confirm", "Remove selected phase?"):
            return

        self.block.procedure.remove_phase(self._selected_phase_index)
        self._refresh_phase_list()
        self.phase_editor.load_phase(None)
        self._selected_phase_index = None

        # Invalidate duration cache when procedure changes
        self.block.invalidate_duration_cache()

        if self.on_change:
            self.on_change()

    def _move_up(self):
        """Move selected phase up."""
        if self._selected_phase_index is None or self._selected_phase_index == 0:
            return

        idx = self._selected_phase_index
        self.block.procedure.reorder_phase(idx, idx - 1)
        self._refresh_phase_list()

        # Re-select at new position (convert phase index to listbox index)
        new_phase_idx = idx - 1
        new_listbox_idx = self._phase_index_to_listbox_index(new_phase_idx)
        self.phase_listbox.selection_clear(0, tk.END)
        self.phase_listbox.selection_set(new_listbox_idx)
        self._selected_phase_index = new_phase_idx

        if self.on_change:
            self.on_change()

    def _move_down(self):
        """Move selected phase down."""
        if self._selected_phase_index is None:
            return
        if self._selected_phase_index >= len(self.block.procedure.phases) - 1:
            return

        idx = self._selected_phase_index
        self.block.procedure.reorder_phase(idx, idx + 1)
        self._refresh_phase_list()

        # Re-select at new position (convert phase index to listbox index)
        new_phase_idx = idx + 1
        new_listbox_idx = self._phase_index_to_listbox_index(new_phase_idx)
        self.phase_listbox.selection_clear(0, tk.END)
        self.phase_listbox.selection_set(new_listbox_idx)
        self._selected_phase_index = new_phase_idx

        if self.on_change:
            self.on_change()

    def refresh(self):
        """Refresh the phase list display."""
        self._refresh_phase_list()


class TrialListConfigEditor(ttk.LabelFrame):
    """Editor for trial list configuration (CSV source, preview)."""

    def __init__(self, parent, block: Block, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Trial List Configuration", padding=10)

        self.block = block
        self.on_change = on_change
        self._suppress_callbacks = False

        # Configure column weights so widgets expand to fill width
        self.columnconfigure(1, weight=1)

        # CSV Source Path
        ttk.Label(self, text="CSV Source:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.source_var = tk.StringVar(
            value=block.trial_list.source if block.trial_list else ""
        )
        source_entry = ttk.Entry(self, textvariable=self.source_var)
        source_entry.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(5, 0))
        self.source_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Button(self, text="Browse...", command=self._browse_csv, width=10).grid(
            row=0, column=2, sticky=tk.W, pady=5, padx=(5, 0)
        )

        # CSV Info (columns, row count)
        info_frame = ttk.Frame(self)
        info_frame.grid(row=1, column=0, columnspan=3, sticky=tk.EW, pady=5)

        ttk.Label(info_frame, text="Columns:").pack(side=tk.LEFT, padx=(0, 5))
        self.columns_label = ttk.Label(info_frame, text=self._get_columns_text(), font=('Arial', 9))
        self.columns_label.pack(side=tk.LEFT, padx=(0, 10))

        ttk.Label(info_frame, text="Rows:").pack(side=tk.LEFT, padx=(0, 5))
        self.rows_label = ttk.Label(info_frame, text=self._get_row_count_text(), font=('Arial', 9))
        self.rows_label.pack(side=tk.LEFT)

        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=3, sticky=tk.W, pady=(5, 0))

        ttk.Button(button_frame, text="Load CSV", command=self._load_csv, width=12).pack(
            side=tk.LEFT, padx=(0, 5)
        )
        ttk.Button(button_frame, text="Edit Data...", command=self._edit_data, width=12).pack(
            side=tk.LEFT
        )

    def _get_columns_text(self) -> str:
        """Get CSV columns as text."""
        if not self.block.trial_list or not self.block.trial_list.trials:
            return "No data loaded"

        try:
            columns = self.block.trial_list.get_columns()
            if len(columns) > 5:
                return f"{', '.join(columns[:5])}, ..."
            else:
                return ', '.join(columns)
        except:
            return "Error reading columns"

    def _get_row_count_text(self) -> str:
        """Get row count as text."""
        if not self.block.trial_list:
            return "0"
        return str(len(self.block.trial_list.trials))

    def _browse_csv(self):
        """Open file browser for CSV selection."""
        filename = filedialog.askopenfilename(
            title="Select Trial List CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if filename:
            self.source_var.set(filename)
            # Invalidate duration cache when CSV path changes
            self.block.invalidate_duration_cache()

    def _load_csv(self):
        """Load CSV file into trial list."""
        csv_path = self.source_var.get().strip()
        if not csv_path:
            messagebox.showwarning("No File", "Please specify a CSV file path.")
            return

        if not os.path.exists(csv_path):
            messagebox.showerror("File Not Found", f"CSV file not found:\n{csv_path}")
            return

        try:
            self.block.trial_list = TrialList(source=csv_path, source_type='csv')
            self.columns_label.config(text=self._get_columns_text())
            self.rows_label.config(text=self._get_row_count_text())

            # Automatically calculate accurate duration after loading CSV
            # This probes video files to get exact durations
            self.block.calculate_accurate_duration()

            messagebox.showinfo("Success", f"Loaded {len(self.block.trial_list.trials)} trials from CSV.")

            if self.on_change:
                self.on_change()
        except Exception as e:
            messagebox.showerror("Error Loading CSV", f"Failed to load CSV:\n{str(e)}")

    def _edit_data(self):
        """Open trial data editor dialog."""
        if not self.block.trial_list:
            messagebox.showwarning("No Data", "Please load a CSV file first.")
            return

        # Import here to avoid circular dependency
        from gui.trial_table_widget import TrialDataEditorDialog

        dialog = TrialDataEditorDialog(self, self.block.trial_list)
        dialog.grab_set()  # Modal dialog
        self.wait_window(dialog)

        # Refresh after editing
        self.columns_label.config(text=self._get_columns_text())
        self.rows_label.config(text=self._get_row_count_text())

        if self.on_change:
            self.on_change()

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks and self.on_change:
            self.on_change()

    def refresh(self):
        """Refresh display."""
        self.source_var.set(self.block.trial_list.source if self.block.trial_list else "")
        self.columns_label.config(text=self._get_columns_text())
        self.rows_label.config(text=self._get_row_count_text())


class RandomizationConfigEditor(ttk.LabelFrame):
    """Editor for randomization configuration."""

    def __init__(self, parent, block: Block, on_change: Optional[Callable] = None):
        super().__init__(parent, text="Randomization Settings", padding=10)

        self.block = block
        self.on_change = on_change
        self._suppress_callbacks = False

        # Configure column weights so widgets expand to fill width
        self.columnconfigure(1, weight=1)

        # Randomization Method
        ttk.Label(self, text="Method:").grid(row=0, column=0, sticky=tk.W, pady=5)

        self.method_var = tk.StringVar(value=block.randomization.method)
        method_combo = ttk.Combobox(
            self, textvariable=self.method_var,
            values=['none', 'full', 'block', 'latin_square', 'constrained'],
            state='readonly'
        )
        method_combo.grid(row=0, column=1, sticky=tk.EW, pady=5, padx=(5, 0))
        method_combo.bind('<<ComboboxSelected>>', lambda e: self._on_property_change())

        # Seed
        ttk.Label(self, text="Random Seed:").grid(row=1, column=0, sticky=tk.W, pady=5)

        seed_frame = ttk.Frame(self)
        seed_frame.grid(row=1, column=1, sticky=tk.EW, pady=5, padx=(5, 0))

        self.seed_var = tk.StringVar(
            value=str(block.randomization.seed) if block.randomization.seed is not None else ""
        )
        seed_entry = ttk.Entry(seed_frame, textvariable=self.seed_var, width=15)
        seed_entry.pack(side=tk.LEFT, padx=(0, 5))
        self.seed_var.trace_add('write', lambda *args: self._on_property_change())

        ttk.Button(seed_frame, text="Generate", command=self._generate_seed, width=10).pack(side=tk.LEFT)

        # Constraints (simplified - just show count)
        ttk.Label(self, text="Constraints:").grid(row=2, column=0, sticky=tk.W, pady=5)

        constraint_count = len(block.randomization.constraints)
        self.constraint_label = ttk.Label(
            self, text=f"{constraint_count} constraint(s) defined",
            font=('Arial', 9)
        )
        self.constraint_label.grid(row=2, column=1, sticky=tk.EW, pady=5, padx=(5, 0))

        # Note: Full constraint editor would be complex, leaving for future enhancement

    def _generate_seed(self):
        """Generate a random seed."""
        seed = random.randint(1000, 9999)
        self.seed_var.set(str(seed))

    def _on_property_change(self):
        """Handle property change."""
        if not self._suppress_callbacks:
            self.apply_changes()
            if self.on_change:
                self.on_change()

    def apply_changes(self):
        """Apply changes to randomization config."""
        try:
            self.block.randomization.method = self.method_var.get()

            seed_str = self.seed_var.get().strip()
            self.block.randomization.seed = int(seed_str) if seed_str else None
        except ValueError:
            pass  # Ignore invalid seed during typing

    def refresh(self):
        """Refresh display."""
        self.method_var.set(self.block.randomization.method)
        self.seed_var.set(
            str(self.block.randomization.seed) if self.block.randomization.seed is not None else ""
        )
        constraint_count = len(self.block.randomization.constraints)
        self.constraint_label.config(text=f"{constraint_count} constraint(s) defined")


class TemplateVariableValidator:
    """
    Validates template variables in phases against CSV columns.

    Provides warnings when template variables don't match trial list columns.
    """

    @staticmethod
    def validate(block: Block) -> List[str]:
        """
        Validate template variables against trial list.

        Args:
            block: Block to validate

        Returns:
            List of warning messages
        """
        warnings = []

        if not block.procedure:
            return warnings

        if block.block_type != 'trial_based' or not block.trial_list:
            # No validation needed for simple blocks or blocks without trial list
            return warnings

        # Get required variables from all phases
        required_vars = block.procedure.get_required_variables()

        if not required_vars:
            return warnings

        # Get available columns from trial list
        try:
            available_columns = set(block.trial_list.get_columns())
        except:
            return [f"Error reading trial list columns"]

        # Find missing variables
        missing_vars = required_vars - available_columns

        if missing_vars:
            warnings.append(
                f"Template variables not found in CSV: {', '.join(missing_vars)}"
            )

        return warnings

    @staticmethod
    def get_validation_icon(block: Block) -> str:
        """
        Get validation status icon.

        Returns:
            "✓" if valid, "⚠" if warnings
        """
        warnings = TemplateVariableValidator.validate(block)
        return "⚠" if warnings else "✓"
