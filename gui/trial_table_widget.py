"""
Trial data table editor for DyadicSync Timeline Editor.

Provides a spreadsheet-like interface for editing trial data.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, List, Dict, Any
from core.execution.trial_list import TrialList
from core.execution.trial import Trial


class TrialDataEditorDialog(tk.Toplevel):
    """
    Dialog for editing trial data in a spreadsheet-like table.

    Allows add/remove/duplicate rows and edit cell values.
    """

    def __init__(self, parent, trial_list: TrialList):
        super().__init__(parent)

        self.trial_list = trial_list
        self.modified = False

        # Configure dialog
        self.title("Edit Trial Data")
        self.geometry("900x600")
        self.resizable(True, True)

        # Make modal
        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Build UI
        self._build_ui()

        # Load data
        self._load_data()

    def _build_ui(self):
        """Build the dialog UI."""
        # Header
        header_frame = ttk.Frame(self, padding=10)
        header_frame.pack(fill=tk.X)

        ttk.Label(
            header_frame,
            text=f"Editing trial data from: {self.trial_list.source}",
            font=('Arial', 10, 'bold')
        ).pack(side=tk.LEFT)

        # Table frame
        table_frame = ttk.Frame(self, padding=10)
        table_frame.pack(fill=tk.BOTH, expand=True)

        # Create Treeview with scrollbars
        tree_scroll_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL)
        tree_scroll_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL)

        self.tree = ttk.Treeview(
            table_frame,
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
            selectmode='browse'
        )

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind double-click for editing
        self.tree.bind('<Double-Button-1>', self._on_cell_double_click)

        # Button frame
        button_frame = ttk.Frame(self, padding=10)
        button_frame.pack(fill=tk.X)

        # Left side buttons (row operations)
        left_buttons = ttk.Frame(button_frame)
        left_buttons.pack(side=tk.LEFT)

        ttk.Button(left_buttons, text="Add Row", command=self._add_row, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_buttons, text="Duplicate Row", command=self._duplicate_row, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(left_buttons, text="Delete Row", command=self._delete_row, width=12).pack(side=tk.LEFT, padx=2)

        # Right side buttons (dialog actions)
        right_buttons = ttk.Frame(button_frame)
        right_buttons.pack(side=tk.RIGHT)

        ttk.Button(right_buttons, text="Save & Close", command=self._save_and_close, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(right_buttons, text="Cancel", command=self._cancel, width=12).pack(side=tk.LEFT, padx=2)

        # Status bar
        self.status_label = ttk.Label(self, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(fill=tk.X, side=tk.BOTTOM)

    def _load_data(self):
        """Load trial data into the table."""
        # Get columns
        columns = self.trial_list.get_columns()
        if not columns:
            messagebox.showerror("Error", "No columns found in trial list.")
            return

        # Configure tree columns
        # Column #0 is the trial ID, rest are data columns
        self.tree['columns'] = columns
        self.tree.heading('#0', text='Trial ID')
        self.tree.column('#0', width=70, stretch=False)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, stretch=True)

        # Insert data rows
        for trial in self.trial_list.trials:
            values = [str(trial.data.get(col, '')) for col in columns]
            self.tree.insert('', 'end', text=str(trial.trial_id), values=values)

        self._update_status(f"Loaded {len(self.trial_list.trials)} trials")

    def _on_cell_double_click(self, event):
        """Handle double-click on a cell to edit it."""
        # Get selected item and column
        item = self.tree.selection()
        if not item:
            return

        item = item[0]

        # Determine which column was clicked
        region = self.tree.identify_region(event.x, event.y)
        if region != 'cell':
            return

        column = self.tree.identify_column(event.x)
        if column == '#0':
            # Don't allow editing trial ID
            return

        # Get column index (column is in format '#1', '#2', etc.)
        col_index = int(column.replace('#', '')) - 1
        columns = self.tree['columns']
        if col_index < 0 or col_index >= len(columns):
            return

        col_name = columns[col_index]

        # Get current value
        values = self.tree.item(item, 'values')
        current_value = values[col_index] if col_index < len(values) else ''

        # Show edit dialog
        new_value = simpledialog.askstring(
            "Edit Cell",
            f"Edit value for column '{col_name}':",
            initialvalue=current_value,
            parent=self
        )

        if new_value is not None:  # None means cancelled
            # Update tree view
            new_values = list(values)
            new_values[col_index] = new_value
            self.tree.item(item, values=new_values)
            self.modified = True
            self._update_status("Cell edited (unsaved)")

    def _add_row(self):
        """Add a new empty row."""
        columns = self.tree['columns']

        # Create new trial ID (max ID + 1)
        max_id = max([trial.trial_id for trial in self.trial_list.trials], default=0)
        new_id = max_id + 1

        # Create empty values
        values = [''] * len(columns)

        # Insert into tree
        self.tree.insert('', 'end', text=str(new_id), values=values)
        self.modified = True
        self._update_status("Row added (unsaved)")

    def _duplicate_row(self):
        """Duplicate the selected row."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a row to duplicate.")
            return

        item = selection[0]

        # Get values from selected row
        values = self.tree.item(item, 'values')

        # Create new trial ID
        max_id = max([int(self.tree.item(child, 'text')) for child in self.tree.get_children()], default=0)
        new_id = max_id + 1

        # Insert duplicate
        self.tree.insert('', 'end', text=str(new_id), values=values)
        self.modified = True
        self._update_status("Row duplicated (unsaved)")

    def _delete_row(self):
        """Delete the selected row."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a row to delete.")
            return

        if not messagebox.askyesno("Confirm Delete", "Delete selected row?"):
            return

        item = selection[0]
        self.tree.delete(item)
        self.modified = True
        self._update_status("Row deleted (unsaved)")

    def _save_and_close(self):
        """Save changes and close dialog."""
        if self.modified:
            # Collect data from tree
            columns = self.tree['columns']
            new_trials = []

            for item in self.tree.get_children():
                trial_id = int(self.tree.item(item, 'text'))
                values = self.tree.item(item, 'values')

                # Build data dict
                data = {}
                for i, col in enumerate(columns):
                    data[col] = values[i] if i < len(values) else ''

                # Create trial
                trial = Trial(trial_id=trial_id, data=data)
                new_trials.append(trial)

            # Update trial list
            self.trial_list.trials = new_trials

            messagebox.showinfo("Saved", f"Saved {len(new_trials)} trials.")

        self.destroy()

    def _cancel(self):
        """Cancel and close dialog."""
        if self.modified:
            if not messagebox.askyesno("Unsaved Changes", "Discard unsaved changes?"):
                return

        self.destroy()

    def _on_close(self):
        """Handle window close event."""
        self._cancel()

    def _update_status(self, message: str):
        """Update status bar."""
        self.status_label.config(text=message)


class TrialTableWidget(ttk.Frame):
    """
    Embedded trial table widget (for use within other panels).

    Simpler version of TrialDataEditorDialog for embedding.
    """

    def __init__(self, parent, trial_list: Optional[TrialList] = None):
        super().__init__(parent)

        self.trial_list = trial_list
        self._on_change: Optional[callable] = None

        self._build_ui()

        if trial_list:
            self._load_data()

    def _build_ui(self):
        """Build the widget UI."""
        # Table frame with scrollbars
        tree_scroll_y = ttk.Scrollbar(self, orient=tk.VERTICAL)
        tree_scroll_x = ttk.Scrollbar(self, orient=tk.HORIZONTAL)

        self.tree = ttk.Treeview(
            self,
            yscrollcommand=tree_scroll_y.set,
            xscrollcommand=tree_scroll_x.set,
            selectmode='browse',
            height=10
        )

        tree_scroll_y.config(command=self.tree.yview)
        tree_scroll_x.config(command=self.tree.xview)

        tree_scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        tree_scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _load_data(self):
        """Load trial data into the table."""
        if not self.trial_list:
            return

        # Clear existing data
        self.tree.delete(*self.tree.get_children())

        # Get columns
        columns = self.trial_list.get_columns()
        if not columns:
            return

        # Configure tree columns
        self.tree['columns'] = columns
        self.tree.heading('#0', text='ID')
        self.tree.column('#0', width=50, stretch=False)

        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, stretch=True)

        # Insert data rows
        for trial in self.trial_list.trials:
            values = [str(trial.data.get(col, '')) for col in columns]
            self.tree.insert('', 'end', text=str(trial.trial_id), values=values)

    def set_trial_list(self, trial_list: TrialList):
        """Set the trial list to display."""
        self.trial_list = trial_list
        self._load_data()

    def set_on_change(self, callback: callable):
        """Set change callback."""
        self._on_change = callback
