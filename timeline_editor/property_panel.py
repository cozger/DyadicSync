"""
Property panel for displaying and editing block properties.

Redesigned for hierarchical block-based experiment structure.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.execution.block import Block
from gui.phase_widgets import PhasePropertyEditor
from gui.block_widgets import (
    BlockInfoEditor,
    ProcedureListWidget,
    TrialListConfigEditor,
    RandomizationConfigEditor,
    TemplateVariableValidator
)


class PropertyPanel(ttk.Frame):
    """
    Panel for editing properties of the selected block.

    Supports:
    - Block information (name, type)
    - Procedure editing (phase list)
    - Phase property editing
    - Trial list configuration (for trial_based blocks)
    - Randomization settings (for trial_based blocks)
    - Template variable validation
    """

    def __init__(self, parent, on_change: Optional[callable] = None):
        """
        Initialize property panel.

        Args:
            parent: Parent widget
            on_change: Callback when properties change
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        self.on_change = on_change
        self._current_block: Optional[Block] = None
        self._configure_scheduled = False  # Flag to prevent Configure loop

        # Title with validation indicator
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        self.title_label = ttk.Label(
            title_frame,
            text="Block Properties",
            font=("Arial", 12, "bold")
        )
        self.title_label.pack(side=tk.LEFT)

        self.validation_label = ttk.Label(
            title_frame,
            text="",
            font=("Arial", 16)
        )
        self.validation_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Scrollable content
        self.canvas = tk.Canvas(self, bg="#FFFFFF")
        self.scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)

        self.scrollable_frame = ttk.Frame(self.canvas)
        self.scrollable_frame.bind("<Configure>", self._on_configure_debounced)

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor=tk.NW)
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        # Create editor widgets (will be shown/hidden dynamically)
        self._create_editors()

        # Pack scrollbar and canvas
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # No selection message
        self.no_selection_label = ttk.Label(
            self,
            text="No block selected.\n\nClick on a block in the timeline to edit its properties.",
            justify=tk.CENTER,
            font=("Arial", 10, "italic")
        )

        self._show_no_selection()

    def _create_editors(self):
        """Create all editor widgets."""
        container = self.scrollable_frame

        # Block Info Editor
        self.block_info_editor = BlockInfoEditor(
            container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            on_change=self._handle_change
        )
        # Don't pack yet

        # Separator
        self.separator1 = ttk.Separator(container, orient=tk.HORIZONTAL)

        # Phase Property Editor (for selected phase)
        self.phase_editor = PhasePropertyEditor(
            container,
            on_change=self._handle_change
        )

        # Procedure List Widget
        self.procedure_widget = ProcedureListWidget(
            container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            phase_editor=self.phase_editor,
            on_change=self._handle_change
        )

        # Separator
        self.separator2 = ttk.Separator(container, orient=tk.HORIZONTAL)

        # Trial List Config Editor (only for trial_based blocks)
        self.trial_list_editor = TrialListConfigEditor(
            container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            on_change=self._handle_change
        )

        # Separator
        self.separator3 = ttk.Separator(container, orient=tk.HORIZONTAL)

        # Randomization Config Editor (only for trial_based blocks)
        self.randomization_editor = RandomizationConfigEditor(
            container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            on_change=self._handle_change
        )

        # Separator
        self.separator4 = ttk.Separator(container, orient=tk.HORIZONTAL)

        # Validation warnings
        self.validation_frame = ttk.Frame(container)
        self.validation_text = tk.Text(
            self.validation_frame,
            height=3,
            wrap=tk.WORD,
            bg='#FFF3CD',
            fg='#856404',
            font=('Arial', 9),
            relief=tk.FLAT,
            state=tk.DISABLED
        )

        # Apply Changes button
        self.apply_button = ttk.Button(
            container,
            text="Apply Changes",
            command=self._apply_changes,
            width=20
        )

    def _on_configure_debounced(self, event):
        """Debounced configure handler to prevent loops."""
        if not self._configure_scheduled:
            self._configure_scheduled = True
            self.after(10, self._update_scroll_region)

    def _update_scroll_region(self):
        """Update scroll region (debounced)."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self._configure_scheduled = False

    def _show_no_selection(self):
        """Show the 'no selection' message."""
        self.canvas.pack_forget()
        self.scrollbar.pack_forget()
        self.no_selection_label.pack(expand=True)

    def _show_editor(self):
        """Show the property editor."""
        self.no_selection_label.pack_forget()
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _handle_change(self):
        """Handle property change."""
        # Refresh validation
        if self._current_block:
            self._update_validation()

            # Refresh stats in block info editor
            self.block_info_editor.refresh_stats()

        if self.on_change:
            self.on_change()

    def _apply_changes(self):
        """Apply all changes and validate."""
        if not self._current_block:
            return

        # Validate block
        errors = self._current_block.validate()
        if errors:
            messagebox.showerror(
                "Validation Errors",
                "Cannot apply changes:\n\n" + "\n".join(errors)
            )
            return

        # Show success message
        messagebox.showinfo("Success", "Changes applied successfully.")

        if self.on_change:
            self.on_change()

    def load_block(self, block: Block):
        """
        Load a block for editing.

        Args:
            block: Block object to edit
        """
        self._current_block = block

        # Update title
        self.title_label.config(text=f"Block: {block.name}")

        # Show editor
        self._show_editor()

        # Update block reference in all editors
        self.block_info_editor.block = block
        self.procedure_widget.block = block
        self.trial_list_editor.block = block
        self.randomization_editor.block = block

        # Load block info
        self.block_info_editor.pack(fill=tk.X, padx=10, pady=5)

        # Load procedure
        self.separator1.pack(fill=tk.X, padx=10, pady=10)
        self.procedure_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.procedure_widget.refresh()

        # Load phase editor (initially empty)
        self.phase_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.phase_editor.load_phase(None)

        # Show/hide trial-based widgets based on block type
        if block.block_type == 'trial_based':
            self.separator2.pack(fill=tk.X, padx=10, pady=10)
            self.trial_list_editor.pack(fill=tk.X, padx=10, pady=5)
            self.trial_list_editor.refresh()

            self.separator3.pack(fill=tk.X, padx=10, pady=10)
            self.randomization_editor.pack(fill=tk.X, padx=10, pady=5)
            self.randomization_editor.refresh()
        else:
            self.separator2.pack_forget()
            self.trial_list_editor.pack_forget()
            self.separator3.pack_forget()
            self.randomization_editor.pack_forget()

        # Validation frame
        self._update_validation()

        # Apply button
        self.separator4.pack(fill=tk.X, padx=10, pady=10)
        self.apply_button.pack(pady=10)

        # Force update scroll region
        self.after(50, self._update_scroll_region)

    def _update_validation(self):
        """Update validation warnings."""
        if not self._current_block:
            return

        warnings = TemplateVariableValidator.validate(self._current_block)

        if warnings:
            # Show validation frame
            self.validation_frame.pack(fill=tk.X, padx=10, pady=5)
            self.validation_text.pack(fill=tk.X, padx=5, pady=5)

            # Update text
            self.validation_text.config(state=tk.NORMAL)
            self.validation_text.delete('1.0', tk.END)
            self.validation_text.insert('1.0', "⚠ Validation Warnings:\n" + "\n".join(f"• {w}" for w in warnings))
            self.validation_text.config(state=tk.DISABLED)

            # Update icon in title
            self.validation_label.config(text="⚠", foreground='orange')
        else:
            # Hide validation frame
            self.validation_frame.pack_forget()

            # Update icon in title
            self.validation_label.config(text="✓", foreground='green')

    def clear(self):
        """Clear the property panel."""
        self._current_block = None
        self.title_label.config(text="Block Properties")
        self.validation_label.config(text="")

        # Hide all editors
        self.block_info_editor.pack_forget()
        self.separator1.pack_forget()
        self.procedure_widget.pack_forget()
        self.phase_editor.pack_forget()
        self.separator2.pack_forget()
        self.trial_list_editor.pack_forget()
        self.separator3.pack_forget()
        self.randomization_editor.pack_forget()
        self.validation_frame.pack_forget()
        self.separator4.pack_forget()
        self.apply_button.pack_forget()

        self._show_no_selection()


# Backward compatibility alias (for any code still referencing load_trial)
# This will raise a clear error if old code tries to use it
def _deprecated_load_trial(self, trial):
    raise NotImplementedError(
        "PropertyPanel.load_trial() is deprecated. "
        "Use PropertyPanel.load_block() instead. "
        "The PropertyPanel has been redesigned for block-based experiments."
    )

PropertyPanel.load_trial = _deprecated_load_trial
