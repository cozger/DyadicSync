"""
Marker Catalog Manager Dialog.

Provides a GUI for managing the global marker catalog:
- View all integer and string marker definitions
- Add/Edit/Delete marker definitions
- Import/Export CodeBook.txt
- Validate marker templates
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional
import logging
from pathlib import Path

from core.markers.catalog import MarkerCatalog, MarkerDefinition

logger = logging.getLogger(__name__)


class MarkerCatalogDialog(tk.Toplevel):
    """Dialog for managing the global marker catalog."""

    def __init__(self, parent):
        """
        Initialize marker catalog manager dialog.

        Args:
            parent: Parent window
        """
        super().__init__(parent)

        self.title("Marker Catalog Manager")
        self.geometry("800x600")
        self.transient(parent)
        self.grab_set()

        self.catalog = MarkerCatalog()

        # Create UI
        self._create_widgets()
        self._load_catalog_data()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create and layout dialog widgets."""
        # Main content frame
        content = ttk.Frame(self, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Tabbed notebook for integer/string markers
        self.notebook = ttk.Notebook(content)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Integer markers tab
        self.integer_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.integer_tab, text="Integer Markers")
        self._create_integer_marker_view(self.integer_tab)

        # String markers tab
        self.string_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.string_tab, text="String Markers")
        self._create_string_marker_view(self.string_tab)

        # Button panel
        button_panel = ttk.Frame(content)
        button_panel.pack(fill=tk.X)

        ttk.Button(
            button_panel,
            text="Add Integer Marker",
            command=self._add_integer_marker
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            button_panel,
            text="Add String Marker",
            command=self._add_string_marker
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            button_panel,
            text="Edit",
            command=self._edit_selected
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            button_panel,
            text="Remove",
            command=self._remove_selected
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(
            button_panel,
            text="Import CodeBook",
            command=self._import_codebook
        ).pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            button_panel,
            text="Export CodeBook",
            command=self._export_codebook
        ).pack(side=tk.LEFT, padx=(0, 20))

        ttk.Button(
            button_panel,
            text="Close",
            command=self.destroy
        ).pack(side=tk.RIGHT)

    def _create_integer_marker_view(self, parent):
        """Create tree view for integer markers."""
        # Columns: Code, Template, Name, Description
        columns = ('code', 'template', 'name', 'description')

        self.integer_tree = ttk.Treeview(
            parent,
            columns=columns,
            show='headings',
            selectmode='browse'
        )

        self.integer_tree.heading('code', text='Code')
        self.integer_tree.heading('template', text='Template')
        self.integer_tree.heading('name', text='Name')
        self.integer_tree.heading('description', text='Description')

        self.integer_tree.column('code', width=80)
        self.integer_tree.column('template', width=100)
        self.integer_tree.column('name', width=150)
        self.integer_tree.column('description', width=400)

        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.integer_tree.yview)
        self.integer_tree.configure(yscrollcommand=scrollbar.set)

        # Pack
        self.integer_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self.integer_tree.bind('<Double-Button-1>', lambda e: self._edit_selected())

    def _create_string_marker_view(self, parent):
        """Create tree view for string markers."""
        # Columns: Template, Name, Description
        columns = ('template', 'name', 'description')

        self.string_tree = ttk.Treeview(
            parent,
            columns=columns,
            show='headings',
            selectmode='browse'
        )

        self.string_tree.heading('template', text='Template')
        self.string_tree.heading('name', text='Name')
        self.string_tree.heading('description', text='Description')

        self.string_tree.column('template', width=150)
        self.string_tree.column('name', width=150)
        self.string_tree.column('description', width=450)

        # Scrollbar
        scrollbar = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=self.string_tree.yview)
        self.string_tree.configure(yscrollcommand=scrollbar.set)

        # Pack
        self.string_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self.string_tree.bind('<Double-Button-1>', lambda e: self._edit_selected())

    def _load_catalog_data(self):
        """Load marker definitions from catalog into tree views."""
        # Clear existing items
        self.integer_tree.delete(*self.integer_tree.get_children())
        self.string_tree.delete(*self.string_tree.get_children())

        # Get all marker definitions
        all_definitions = self.catalog.get_all_definitions()

        # Load integer markers
        integer_markers = [d for d in all_definitions if d.marker_type == 'integer']
        for marker_def in sorted(integer_markers, key=lambda m: m.code or 0):
            self.integer_tree.insert('', tk.END, values=(
                marker_def.code or '',
                marker_def.template_pattern or '',
                marker_def.name,
                marker_def.description or ''
            ), tags=(marker_def.name,))  # Store name as tag for lookup

        # Load string markers
        string_markers = [d for d in all_definitions if d.marker_type == 'string']
        for marker_def in sorted(string_markers, key=lambda m: m.name):
            self.string_tree.insert('', tk.END, values=(
                marker_def.template_pattern,
                marker_def.name,
                marker_def.description or ''
            ), tags=(marker_def.name,))  # Store name as tag for lookup

    def _get_selected_marker(self):
        """Get the currently selected marker definition."""
        # Check which tab is active
        current_tab = self.notebook.select()
        tab_text = self.notebook.tab(current_tab, "text")

        if tab_text == "Integer Markers":
            selection = self.integer_tree.selection()
            if not selection:
                return None, None

            item = self.integer_tree.item(selection[0])
            values = item['values']
            # Get by code (first column)
            code = int(values[0]) if values[0] else None
            template = values[1] if values[1] else None

            # Try to get by code first, then by template
            if code:
                marker_def = self.catalog.get_definition(code)
            elif template:
                marker_def = self.catalog.get_definition(template)
            else:
                return None, None

            return marker_def, 'integer'
        else:  # String Markers
            selection = self.string_tree.selection()
            if not selection:
                return None, None

            item = self.string_tree.item(selection[0])
            values = item['values']
            # Get by template (first column)
            template = values[0]
            marker_def = self.catalog.get_definition(template)
            return marker_def, 'string'

    def _add_integer_marker(self):
        """Add a new integer marker definition."""
        dialog = AddIntegerMarkerDialog(self)
        if dialog.result:
            try:
                # Create MarkerDefinition from dialog result
                marker_def = MarkerDefinition(
                    name=dialog.result['name'],
                    description=dialog.result.get('description', ''),
                    code=dialog.result.get('code'),
                    template_pattern=dialog.result.get('template'),
                    marker_type='integer'
                )
                self.catalog.add_definition(marker_def)
                self._load_catalog_data()
                messagebox.showinfo("Success", "Integer marker added successfully.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add marker: {e}", parent=self)

    def _add_string_marker(self):
        """Add a new string marker definition."""
        dialog = AddStringMarkerDialog(self)
        if dialog.result:
            try:
                # Create MarkerDefinition from dialog result
                marker_def = MarkerDefinition(
                    name=dialog.result['name'],
                    description=dialog.result.get('description', ''),
                    template_pattern=dialog.result['template'],
                    marker_type='string'
                )
                self.catalog.add_definition(marker_def)
                self._load_catalog_data()
                messagebox.showinfo("Success", "String marker added successfully.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to add marker: {e}", parent=self)

    def _edit_selected(self):
        """Edit the selected marker definition."""
        marker_def, marker_type = self._get_selected_marker()

        if not marker_def:
            messagebox.showinfo("No Selection", "Please select a marker to edit.", parent=self)
            return

        # Get the original key (code for integer, template for string)
        if marker_type == 'integer':
            original_key = marker_def.code if marker_def.code else marker_def.template_pattern
            dialog = AddIntegerMarkerDialog(self, marker_def)
            if dialog.result:
                try:
                    # Create updated MarkerDefinition
                    updated_def = MarkerDefinition(
                        name=dialog.result['name'],
                        description=dialog.result.get('description', ''),
                        code=dialog.result.get('code'),
                        template_pattern=dialog.result.get('template'),
                        marker_type='integer'
                    )
                    self.catalog.update_definition(original_key, updated_def)
                    self._load_catalog_data()
                    messagebox.showinfo("Success", "Marker updated successfully.", parent=self)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update marker: {e}", parent=self)
        else:  # string
            original_key = marker_def.template_pattern
            dialog = AddStringMarkerDialog(self, marker_def)
            if dialog.result:
                try:
                    # Create updated MarkerDefinition
                    updated_def = MarkerDefinition(
                        name=dialog.result['name'],
                        description=dialog.result.get('description', ''),
                        template_pattern=dialog.result['template'],
                        marker_type='string'
                    )
                    self.catalog.update_definition(original_key, updated_def)
                    self._load_catalog_data()
                    messagebox.showinfo("Success", "Marker updated successfully.", parent=self)
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to update marker: {e}", parent=self)

    def _remove_selected(self):
        """Remove the selected marker definition."""
        marker_def, marker_type = self._get_selected_marker()

        if not marker_def:
            messagebox.showinfo("No Selection", "Please select a marker to remove.", parent=self)
            return

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Removal",
            f"Remove marker '{marker_def.name}'?\n\nThis cannot be undone.",
            parent=self
        )

        if confirm:
            try:
                # Get the key (code for integer, template for string)
                if marker_type == 'integer':
                    key = marker_def.code if marker_def.code else marker_def.template_pattern
                else:
                    key = marker_def.template_pattern

                self.catalog.remove_definition(key)
                self._load_catalog_data()
                messagebox.showinfo("Success", "Marker removed successfully.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to remove marker: {e}", parent=self)

    def _import_codebook(self):
        """Import marker definitions from CodeBook.txt."""
        file_path = filedialog.askopenfilename(
            parent=self,
            title="Import CodeBook",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            defaultextension=".txt"
        )

        if file_path:
            try:
                self.catalog.import_from_codebook(file_path)
                self.catalog.save()
                self._load_catalog_data()
                messagebox.showinfo("Success", "CodeBook imported successfully.", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to import CodeBook: {e}", parent=self)

    def _export_codebook(self):
        """Export marker definitions to CodeBook.txt."""
        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="Export CodeBook",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            defaultextension=".txt",
            initialfile="CodeBook.txt"
        )

        if file_path:
            try:
                self.catalog.export_to_codebook(file_path)
                messagebox.showinfo("Success", f"CodeBook exported to:\n{file_path}", parent=self)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to export CodeBook: {e}", parent=self)


class AddIntegerMarkerDialog(tk.Toplevel):
    """Dialog for adding/editing an integer marker definition."""

    def __init__(self, parent, marker_def: Optional[IntegerMarkerDefinition] = None):
        """
        Initialize dialog.

        Args:
            parent: Parent window
            marker_def: Existing marker to edit (None for new marker)
        """
        super().__init__(parent)

        self.title("Integer Marker" if not marker_def else "Edit Integer Marker")
        self.transient(parent)
        self.grab_set()

        self.marker_def = marker_def
        self.result = None

        # Create UI
        self._create_widgets()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create and layout widgets."""
        content = ttk.Frame(self, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Code (optional)
        ttk.Label(content, text="Code (optional):").grid(row=0, column=0, sticky='w', pady=5)
        self.code_var = tk.StringVar(
            value=str(self.marker_def.code) if self.marker_def and self.marker_def.code else ""
        )
        ttk.Entry(content, textvariable=self.code_var, width=30).grid(row=0, column=1, sticky='ew', pady=5)
        ttk.Label(content, text="(e.g., 8888)", font=('Arial', 8), foreground='gray').grid(
            row=0, column=2, sticky='w', padx=(5, 0)
        )

        # Template (optional)
        ttk.Label(content, text="Template (optional):").grid(row=1, column=0, sticky='w', pady=5)
        self.template_var = tk.StringVar(
            value=self.marker_def.template if self.marker_def and self.marker_def.template else ""
        )
        ttk.Entry(content, textvariable=self.template_var, width=30).grid(row=1, column=1, sticky='ew', pady=5)
        ttk.Label(content, text="(e.g., 100#, 300#0$)", font=('Arial', 8), foreground='gray').grid(
            row=1, column=2, sticky='w', padx=(5, 0)
        )

        # Name (required)
        ttk.Label(content, text="Name (required):").grid(row=2, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar(
            value=self.marker_def.name if self.marker_def else ""
        )
        ttk.Entry(content, textvariable=self.name_var, width=30).grid(row=2, column=1, sticky='ew', pady=5)
        ttk.Label(content, text="(e.g., Trial Start)", font=('Arial', 8), foreground='gray').grid(
            row=2, column=2, sticky='w', padx=(5, 0)
        )

        # Description (optional)
        ttk.Label(content, text="Description:").grid(row=3, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(content, width=30, height=4)
        if self.marker_def and self.marker_def.description:
            self.description_text.insert('1.0', self.marker_def.description)
        self.description_text.grid(row=3, column=1, sticky='ew', pady=5)

        # Buttons
        button_panel = ttk.Frame(content)
        button_panel.grid(row=4, column=0, columnspan=3, sticky='e', pady=(10, 0))

        ttk.Button(button_panel, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_panel, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

        content.columnconfigure(1, weight=1)

    def _on_ok(self):
        """Handle OK button."""
        # Validate
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Validation Error", "Name is required.", parent=self)
            return

        code_str = self.code_var.get().strip()
        template = self.template_var.get().strip()

        # Must have either code or template
        if not code_str and not template:
            messagebox.showerror(
                "Validation Error",
                "Must provide either Code or Template (or both).",
                parent=self
            )
            return

        # Parse code if provided
        code = None
        if code_str:
            try:
                code = int(code_str)
            except ValueError:
                messagebox.showerror("Validation Error", "Code must be an integer.", parent=self)
                return

        description = self.description_text.get('1.0', 'end-1c').strip()

        self.result = {
            'code': code,
            'template': template if template else None,
            'name': name,
            'description': description if description else None
        }

        self.destroy()

    def _on_cancel(self):
        """Handle Cancel button."""
        self.result = None
        self.destroy()


class AddStringMarkerDialog(tk.Toplevel):
    """Dialog for adding/editing a string marker definition."""

    def __init__(self, parent, marker_def: Optional[StringMarkerDefinition] = None):
        """
        Initialize dialog.

        Args:
            parent: Parent window
            marker_def: Existing marker to edit (None for new marker)
        """
        super().__init__(parent)

        self.title("String Marker" if not marker_def else "Edit String Marker")
        self.transient(parent)
        self.grab_set()

        self.marker_def = marker_def
        self.result = None

        # Create UI
        self._create_widgets()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def _create_widgets(self):
        """Create and layout widgets."""
        content = ttk.Frame(self, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Template (required)
        ttk.Label(content, text="Template (required):").grid(row=0, column=0, sticky='w', pady=5)
        self.template_var = tk.StringVar(
            value=self.marker_def.template if self.marker_def else ""
        )
        ttk.Entry(content, textvariable=self.template_var, width=30).grid(row=0, column=1, sticky='ew', pady=5)
        ttk.Label(content, text="(e.g., {type}_start)", font=('Arial', 8), foreground='gray').grid(
            row=0, column=2, sticky='w', padx=(5, 0)
        )

        # Name (required)
        ttk.Label(content, text="Name (required):").grid(row=1, column=0, sticky='w', pady=5)
        self.name_var = tk.StringVar(
            value=self.marker_def.name if self.marker_def else ""
        )
        ttk.Entry(content, textvariable=self.name_var, width=30).grid(row=1, column=1, sticky='ew', pady=5)
        ttk.Label(content, text="(e.g., Type Start Event)", font=('Arial', 8), foreground='gray').grid(
            row=1, column=2, sticky='w', padx=(5, 0)
        )

        # Description (optional)
        ttk.Label(content, text="Description:").grid(row=2, column=0, sticky='nw', pady=5)
        self.description_text = tk.Text(content, width=30, height=4)
        if self.marker_def and self.marker_def.description:
            self.description_text.insert('1.0', self.marker_def.description)
        self.description_text.grid(row=2, column=1, sticky='ew', pady=5)

        # Buttons
        button_panel = ttk.Frame(content)
        button_panel.grid(row=3, column=0, columnspan=3, sticky='e', pady=(10, 0))

        ttk.Button(button_panel, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_panel, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

        content.columnconfigure(1, weight=1)

    def _on_ok(self):
        """Handle OK button."""
        # Validate
        template = self.template_var.get().strip()
        name = self.name_var.get().strip()

        if not template:
            messagebox.showerror("Validation Error", "Template is required.", parent=self)
            return

        if not name:
            messagebox.showerror("Validation Error", "Name is required.", parent=self)
            return

        description = self.description_text.get('1.0', 'end-1c').strip()

        self.result = {
            'template': template,
            'name': name,
            'description': description if description else None
        }

        self.destroy()

    def _on_cancel(self):
        """Handle Cancel button."""
        self.result = None
        self.destroy()
