"""
Marker binding GUI widgets for the DyadicSync timeline editor.

This module provides reusable tkinter widgets for managing LSL marker bindings:
- MarkerTemplatePicker: Dropdown for selecting marker templates from catalog
- MarkerBindingEditorDialog: Dialog for editing a single MarkerBinding
- MarkerBindingListWidget: List widget for managing multiple MarkerBindings

Author: DyadicSync Development Team
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Optional, Callable
import logging

from core.markers.catalog import MarkerCatalog
from core.markers.templates import MarkerBinding, validate_template_syntax, get_template_description

logger = logging.getLogger(__name__)


class MarkerTemplatePicker(ttk.Frame):
    """
    Combo widget for selecting marker templates from catalog with validation.

    Features:
    - Dropdown populated from MarkerCatalog (integer and string markers)
    - Custom template entry option
    - Live validation indicator (✓/✗)
    - Preview of template description
    - Change callback support
    """

    def __init__(self, parent, initial_template: str = "", on_change: Optional[Callable] = None):
        """
        Initialize MarkerTemplatePicker widget.

        Args:
            parent: Parent tkinter widget
            initial_template: Initial template string to display
            on_change: Callback function called when template changes
        """
        super().__init__(parent)

        self.on_change = on_change
        self._catalog = MarkerCatalog()

        # Create layout
        self._create_widgets(initial_template)
        self._populate_catalog_templates()

        # Initial validation
        self._validate_template()

    def _create_widgets(self, initial_template: str):
        """Create and layout the widget components."""
        # Hint label
        hint_label = ttk.Label(
            self,
            text="Select from catalog or type custom template:",
            font=('TkDefaultFont', 8),
            foreground='#666'
        )
        hint_label.grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 2))

        # Template entry/dropdown
        self.template_var = tk.StringVar(value=initial_template)
        self.template_combo = ttk.Combobox(
            self,
            textvariable=self.template_var,
            width=30,
            state='normal'  # Allow custom entry
        )
        self.template_combo.grid(row=1, column=0, sticky='ew', padx=(0, 5))

        # Validation indicator
        self.validation_label = ttk.Label(self, text="", width=2)
        self.validation_label.grid(row=1, column=1)

        # Preview/description label
        self.preview_label = ttk.Label(
            self,
            text="",
            font=('TkDefaultFont', 8),
            foreground='gray'
        )
        self.preview_label.grid(row=2, column=0, columnspan=2, sticky='w', pady=(2, 0))

        # Configure column weights
        self.columnconfigure(0, weight=1)

        # Bind events
        self.template_var.trace_add('write', lambda *args: self._on_template_change())
        self.template_combo.bind('<<ComboboxSelected>>', lambda e: self._on_template_change())

    def _populate_catalog_templates(self):
        """Populate dropdown with templates from catalog."""
        templates = []

        # Get all marker definitions from catalog
        all_definitions = self._catalog.get_all_definitions()

        # Add integer marker templates
        for marker_def in all_definitions:
            if marker_def.marker_type == 'integer':
                if marker_def.template_pattern:
                    # Show: "100# - Trial Start"
                    display = f"{marker_def.template_pattern} - {marker_def.name}"
                    templates.append(display)
                elif marker_def.code:
                    # Fixed code marker: "8888 - Baseline Start"
                    display = f"{marker_def.code} - {marker_def.name}"
                    templates.append(display)

        # Add string marker templates
        for marker_def in all_definitions:
            if marker_def.marker_type == 'string':
                # Show: "{type}_start - Type Start Event"
                display = f"{marker_def.template_pattern} - {marker_def.name}"
                templates.append(display)

        # Add empty option for "no marker"
        templates.insert(0, "")

        self.template_combo['values'] = templates

    def _on_template_change(self):
        """Handle template value changes."""
        template = self.template_var.get()
        logger.debug(f"MarkerTemplatePicker._on_template_change: template changed to '{template}'")

        self._validate_template()

        if self.on_change:
            logger.debug("  Calling on_change callback")
            self.on_change()
        else:
            logger.debug("  No on_change callback registered")

    def _validate_template(self):
        """Validate current template and update UI indicators."""
        template = self.get_template()

        if not template:
            # Empty is valid (no marker)
            self.validation_label.config(text="", foreground="black")
            self.preview_label.config(text="No marker will be sent")
            return

        # Validate syntax
        is_valid, message = validate_template_syntax(template)

        if is_valid:
            self.validation_label.config(text="✓", foreground="green")

            # Show description/preview
            description = get_template_description(template)
            self.preview_label.config(text=description, foreground="gray")
        else:
            self.validation_label.config(text="✗", foreground="red")
            self.preview_label.config(text=f"Error: {message}", foreground="red")

    def get_template(self) -> str:
        """
        Get the current template string (cleaned).

        Returns:
            Template string without display suffix (e.g., "100#" not "100# - Trial Start")
        """
        value = self.template_var.get().strip()

        # If user selected from dropdown, extract just the template part
        # Format is: "100# - Trial Start" or "8888 - Baseline Start"
        if ' - ' in value:
            value = value.split(' - ')[0].strip()

        return value

    def set_template(self, template: str):
        """Set the template value programmatically."""
        self.template_var.set(template)
        self._validate_template()

    def is_valid(self) -> bool:
        """Check if current template is valid."""
        template = self.get_template()

        if not template:
            return True  # Empty is valid

        is_valid, _ = validate_template_syntax(template)
        return is_valid


class MarkerBindingEditorDialog(tk.Toplevel):
    """
    Dialog for editing a single MarkerBinding.

    Provides form fields for:
    - Event type (dropdown)
    - Marker template (MarkerTemplatePicker)
    - Participant (radio buttons: Both/P1/P2)
    - Preview of what the binding does

    Usage:
        dialog = MarkerBindingEditorDialog(parent, ...)
        result = dialog.show()  # Blocks until user closes dialog
        if result:
            # Process the MarkerBinding result
    """

    def __init__(
        self,
        parent,
        binding: Optional[MarkerBinding] = None,
        available_events: Optional[List[str]] = None,
        title: str = "Edit Marker Binding"
    ):
        """
        Initialize MarkerBindingEditorDialog.

        Args:
            parent: Parent tkinter widget
            binding: Existing MarkerBinding to edit (None for new binding)
            available_events: List of event types available for this phase
            title: Dialog window title

        Note:
            Call show() method to display the dialog and wait for user input.
        """
        super().__init__(parent)

        logger.debug(f"MarkerBindingEditorDialog.__init__: Opening dialog (title={title})")
        logger.debug(f"  binding={binding}, available_events={available_events}")

        self.title(title)
        self.transient(parent)

        self.binding = binding
        self.available_events = available_events or []
        self.result = None
        self._destroyed = False

        # Create UI
        self._create_widgets()

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_rootx() + 50
        y = parent.winfo_rooty() + 50
        self.geometry(f"+{x}+{y}")

        # Prevent accidental closure
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Set modal after geometry is set
        self.grab_set()
        self.focus_set()

        logger.debug("MarkerBindingEditorDialog.__init__: Dialog created and displayed")

    def show(self) -> Optional[MarkerBinding]:
        """
        Display the dialog and wait for user input.

        Returns:
            MarkerBinding object if user clicked OK, None if cancelled

        Note:
            This method blocks until the dialog is closed.
        """
        logger.debug("MarkerBindingEditorDialog.show: Waiting for user input")
        self.wait_window()
        logger.debug(f"MarkerBindingEditorDialog.show: Dialog closed, returning result={self.result}")
        return self.result

    def _create_widgets(self):
        """Create and layout dialog widgets."""
        # Main content frame
        content = ttk.Frame(self, padding=10)
        content.pack(fill=tk.BOTH, expand=True)

        # Event Type
        ttk.Label(content, text="Event Type:").grid(row=0, column=0, sticky='w', pady=5)
        self.event_var = tk.StringVar(
            value=self.binding.event_type if self.binding else ""
        )
        event_combo = ttk.Combobox(
            content,
            textvariable=self.event_var,
            values=self.available_events,
            state='readonly',
            width=30
        )
        event_combo.grid(row=0, column=1, sticky='ew', pady=5)

        # Add logging for event type changes
        def on_event_type_change(*args):
            logger.debug(f"Event type changed to: {self.event_var.get()}")
            logger.debug(f"Dialog still alive: {self.winfo_exists()}")

        self.event_var.trace_add('write', on_event_type_change)
        event_combo.bind('<<ComboboxSelected>>', lambda e: logger.debug("Event type combobox selected event fired"))

        # Marker Template
        ttk.Label(content, text="Marker Template:").grid(row=1, column=0, sticky='nw', pady=5)
        self.template_picker = MarkerTemplatePicker(
            content,
            initial_template=self.binding.marker_template if self.binding else "",
            on_change=self._update_preview
        )
        self.template_picker.grid(row=1, column=1, sticky='ew', pady=5)

        # Participant
        ttk.Label(content, text="Send Marker For:").grid(row=2, column=0, sticky='nw', pady=5)
        participant_frame = ttk.Frame(content)
        participant_frame.grid(row=2, column=1, sticky='w', pady=5)

        self.participant_var = tk.IntVar(
            value=0 if self.binding is None or self.binding.participant is None else self.binding.participant
        )

        ttk.Radiobutton(
            participant_frame,
            text="Both Participants",
            variable=self.participant_var,
            value=0
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Radiobutton(
            participant_frame,
            text="Participant 1 Only",
            variable=self.participant_var,
            value=1
        ).pack(side=tk.LEFT, padx=(0, 10))

        ttk.Radiobutton(
            participant_frame,
            text="Participant 2 Only",
            variable=self.participant_var,
            value=2
        ).pack(side=tk.LEFT)

        # CSV Integration Info
        csv_info_frame = ttk.LabelFrame(content, text="ℹ CSV Variable Substitution", padding=5)
        csv_info_frame.grid(row=3, column=0, columnspan=2, sticky='ew', pady=5)

        csv_info_text = (
            "Templates can use ANY column from your trial CSV file:\n"
            "  • Integer: 100# → trial number (1001, 1002...)\n"
            "  • String: {type}_start → uses 'type' column (e.g., 'happy_start')\n"
            "  • Combined: {emotion}_{trial_index} → multiple columns\n"
            "  • Rating: 300#0$ → includes response value (300107 = trial 1, rating 7)"
        )

        ttk.Label(
            csv_info_frame,
            text=csv_info_text,
            font=('TkDefaultFont', 8),
            foreground='#444',
            justify=tk.LEFT
        ).pack(anchor='w')

        # Preview
        preview_frame = ttk.LabelFrame(content, text="Preview", padding=5)
        preview_frame.grid(row=4, column=0, columnspan=2, sticky='ew', pady=10)

        self.preview_text = tk.Text(
            preview_frame,
            height=3,
            wrap=tk.WORD,
            font=('TkDefaultFont', 9),
            state='disabled',
            background='#f0f0f0'
        )
        self.preview_text.pack(fill=tk.BOTH, expand=True)

        # Update preview initially
        self._update_preview()

        # Button panel
        button_panel = ttk.Frame(content)
        button_panel.grid(row=5, column=0, columnspan=2, sticky='e', pady=(10, 0))

        ttk.Button(button_panel, text="OK", command=self._on_ok).pack(side=tk.RIGHT, padx=(5, 0))
        ttk.Button(button_panel, text="Cancel", command=self._on_cancel).pack(side=tk.RIGHT)

        # Configure column weights
        content.columnconfigure(1, weight=1)

    def _update_preview(self):
        """Update preview text based on current selections."""
        event_type = self.event_var.get()
        template = self.template_picker.get_template()
        participant = self.participant_var.get()

        # Build preview message
        preview_lines = []

        if not event_type:
            preview_lines.append("⚠ Select an event type")
        else:
            preview_lines.append(f"When event '{event_type}' occurs:")

        if not template:
            preview_lines.append("  → No marker will be sent")
        else:
            participant_text = {
                0: "both participants",
                1: "participant 1 only",
                2: "participant 2 only"
            }[participant]

            # Get template description
            description = get_template_description(template)
            preview_lines.append(f"  → Send marker for {participant_text}")
            preview_lines.append(f"  → {description}")

        # Update text widget
        self.preview_text.config(state='normal')
        self.preview_text.delete('1.0', tk.END)
        self.preview_text.insert('1.0', '\n'.join(preview_lines))
        self.preview_text.config(state='disabled')

    def _on_ok(self):
        """Handle OK button - validate and save result."""
        logger.debug("MarkerBindingEditorDialog._on_ok: OK button clicked")

        # Validate event type
        event_type = self.event_var.get()
        logger.debug(f"  event_type={event_type}")

        if not event_type:
            logger.warning("  Validation failed: No event type selected")
            messagebox.showerror("Validation Error", "Please select an event type.", parent=self)
            return

        # Get template
        template = self.template_picker.get_template()
        logger.debug(f"  template={template}")

        # Validate template if provided
        if template and not self.template_picker.is_valid():
            logger.warning(f"  Validation failed: Invalid template syntax: {template}")
            messagebox.showerror(
                "Validation Error",
                "Invalid marker template. Please correct the template syntax.",
                parent=self
            )
            return

        # Get participant
        participant_value = self.participant_var.get()
        participant = None if participant_value == 0 else participant_value
        logger.debug(f"  participant={participant}")

        # Create MarkerBinding
        try:
            self.result = MarkerBinding(
                event_type=event_type,
                marker_template=template,
                participant=participant
            )
            logger.debug(f"  Created MarkerBinding successfully: {self.result}")
            logger.debug("  Destroying dialog")
            self._destroyed = True
            self.destroy()
        except Exception as e:
            logger.error(f"  Failed to create MarkerBinding: {e}")
            messagebox.showerror(
                "Error Creating Binding",
                f"Failed to create marker binding: {e}",
                parent=self
            )

    def _on_cancel(self):
        """Handle Cancel button."""
        logger.debug("MarkerBindingEditorDialog._on_cancel: Cancel clicked or window closed")

        if self._destroyed:
            logger.warning("  Dialog already destroyed, ignoring")
            return

        self._destroyed = True
        self.result = None

        logger.debug("  Destroying dialog")
        self.destroy()

    def destroy(self):
        """Override destroy to add logging."""
        if not self._destroyed:
            logger.warning("MarkerBindingEditorDialog.destroy: Dialog destroyed unexpectedly!")
            logger.warning(f"  result={self.result}")
            import traceback
            logger.warning("  Stack trace:")
            for line in traceback.format_stack():
                logger.warning(f"    {line.strip()}")

        super().destroy()

    def get_result(self) -> Optional[MarkerBinding]:
        """Get the result MarkerBinding (or None if cancelled)."""
        return self.result


class MarkerBindingListWidget(ttk.LabelFrame):
    """
    Widget for editing a list of MarkerBinding objects.

    Features:
    - Listbox showing: "event_type -> marker_template (Participant X)"
    - Add/Edit/Remove/Reorder buttons
    - Opens MarkerBindingEditorDialog for editing
    - Change callback support
    """

    def __init__(
        self,
        parent,
        bindings: Optional[List[MarkerBinding]] = None,
        available_events: Optional[List[str]] = None,
        on_change: Optional[Callable] = None,
        label: str = "Event Markers"
    ):
        """
        Initialize MarkerBindingListWidget.

        Args:
            parent: Parent tkinter widget
            bindings: Initial list of MarkerBinding objects
            available_events: List of event types available for this phase
            on_change: Callback function called when bindings change
            label: Label for the frame
        """
        super().__init__(parent, text=label, padding=5)

        self.bindings = bindings.copy() if bindings else []
        self.available_events = available_events or []
        self.on_change = on_change

        # Create UI
        self._create_widgets()
        self._refresh_listbox()

    def _create_widgets(self):
        """Create and layout widget components."""
        # Listbox with scrollbar
        listbox_frame = ttk.Frame(self)
        listbox_frame.grid(row=0, column=0, sticky='nsew', padx=(0, 5))

        scrollbar = ttk.Scrollbar(listbox_frame, orient=tk.VERTICAL)
        self.listbox = tk.Listbox(
            listbox_frame,
            yscrollcommand=scrollbar.set,
            height=6,
            width=50,
            selectmode=tk.SINGLE
        )
        scrollbar.config(command=self.listbox.yview)

        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Bind double-click to edit
        self.listbox.bind('<Double-Button-1>', lambda e: self._edit_binding())

        # Button panel
        button_panel = ttk.Frame(self)
        button_panel.grid(row=0, column=1, sticky='n')

        ttk.Button(button_panel, text="Add", command=self._add_binding, width=10).pack(pady=(0, 5))
        ttk.Button(button_panel, text="Edit", command=self._edit_binding, width=10).pack(pady=(0, 5))
        ttk.Button(button_panel, text="Remove", command=self._remove_binding, width=10).pack(pady=(0, 5))
        ttk.Button(button_panel, text="↑ Up", command=self._move_up, width=10).pack(pady=(0, 5))
        ttk.Button(button_panel, text="↓ Down", command=self._move_down, width=10).pack()

        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

    def _refresh_listbox(self):
        """Refresh listbox display from bindings list."""
        self.listbox.delete(0, tk.END)

        for binding in self.bindings:
            # Format: "video_start -> 100# (Both)"
            display = self._format_binding_display(binding)
            self.listbox.insert(tk.END, display)

    def _format_binding_display(self, binding: MarkerBinding) -> str:
        """Format a binding for display in listbox."""
        # Event type
        event = binding.event_type

        # Marker template
        template = binding.marker_template if binding.marker_template else "(none)"

        # Participant
        if binding.participant is None:
            participant_text = "Both"
        elif binding.participant == 1:
            participant_text = "P1"
        elif binding.participant == 2:
            participant_text = "P2"
        else:
            participant_text = f"P{binding.participant}"

        return f"{event} → {template} ({participant_text})"

    def _get_phase_editor(self):
        """
        Navigate widget tree to find the PhasePropertyEditor instance.

        Returns:
            PhasePropertyEditor instance if found, None otherwise
        """
        # Import here to avoid circular dependency
        from gui.phase_widgets import PhasePropertyEditor

        # Walk up the widget tree looking for PhasePropertyEditor
        widget = self.master
        while widget is not None:
            if isinstance(widget, PhasePropertyEditor):
                return widget
            widget = widget.master if hasattr(widget, 'master') else None

        logger.warning("MarkerBindingListWidget._get_phase_editor: Could not find PhasePropertyEditor in widget tree")
        return None

    def _add_binding(self):
        """Add a new binding via dialog."""
        logger.debug("MarkerBindingListWidget._add_binding: Opening dialog")
        logger.debug(f"  available_events={self.available_events}")

        # Get phase editor to manage dialog-open flag
        phase_editor = self._get_phase_editor()
        if phase_editor:
            phase_editor._dialog_open_count += 1
            logger.debug(f"  Incremented dialog count to {phase_editor._dialog_open_count}")

        try:
            # Parent dialog to toplevel window, not to this widget
            # This prevents the dialog from being destroyed when the phase editor reloads
            toplevel = self.winfo_toplevel()

            dialog = MarkerBindingEditorDialog(
                toplevel,  # Use toplevel instead of self
                binding=None,
                available_events=self.available_events,
                title="Add Marker Binding"
            )

            # Show dialog and get result (blocks until dialog closes)
            result = dialog.show()

            logger.debug(f"MarkerBindingListWidget._add_binding: Dialog closed, result={result}")

            # Check if widget still exists before proceeding
            # (Parent might have been destroyed while dialog was open)
            if not self.winfo_exists():
                logger.warning("  Widget destroyed while dialog was open, skipping update")
                return

            if result:
                logger.debug(f"  Adding binding to list: {result}")
                self.bindings.append(result)
                logger.debug(f"  Total bindings now: {len(self.bindings)}")
                self._refresh_listbox()
                self._on_bindings_changed()
                logger.debug("  Binding added successfully")
            else:
                logger.debug("  No binding added (user cancelled or validation failed)")

        finally:
            # Decrement dialog count and process any pending phase load
            if phase_editor:
                phase_editor._dialog_open_count -= 1
                logger.debug(f"  Decremented dialog count to {phase_editor._dialog_open_count}")

                # If no more dialogs are open and there's a pending load, execute it
                if phase_editor._dialog_open_count == 0 and phase_editor._pending_phase_load is not None:
                    logger.info("  Executing pending phase load")
                    pending_phase = phase_editor._pending_phase_load
                    phase_editor._pending_phase_load = None
                    phase_editor.load_phase(pending_phase)

    def _edit_binding(self):
        """Edit selected binding via dialog."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a marker binding to edit.", parent=self)
            return

        index = selection[0]
        binding = self.bindings[index]

        # Get phase editor to manage dialog-open flag
        phase_editor = self._get_phase_editor()
        if phase_editor:
            phase_editor._dialog_open_count += 1
            logger.debug(f"MarkerBindingListWidget._edit_binding: Incremented dialog count to {phase_editor._dialog_open_count}")

        try:
            # Parent dialog to toplevel window, not to this widget
            toplevel = self.winfo_toplevel()

            dialog = MarkerBindingEditorDialog(
                toplevel,  # Use toplevel instead of self
                binding=binding,
                available_events=self.available_events,
                title="Edit Marker Binding"
            )

            # Show dialog and get result (blocks until dialog closes)
            result = dialog.show()

            # Check if widget still exists before proceeding
            # (Parent might have been destroyed while dialog was open)
            if not self.winfo_exists():
                logger.warning("MarkerBindingListWidget._edit_binding: Widget destroyed while dialog was open, skipping update")
                return

            if result:
                self.bindings[index] = result
                self._refresh_listbox()
                self._on_bindings_changed()

        finally:
            # Decrement dialog count and process any pending phase load
            if phase_editor:
                phase_editor._dialog_open_count -= 1
                logger.debug(f"MarkerBindingListWidget._edit_binding: Decremented dialog count to {phase_editor._dialog_open_count}")

                # If no more dialogs are open and there's a pending load, execute it
                if phase_editor._dialog_open_count == 0 and phase_editor._pending_phase_load is not None:
                    logger.info("MarkerBindingListWidget._edit_binding: Executing pending phase load")
                    pending_phase = phase_editor._pending_phase_load
                    phase_editor._pending_phase_load = None
                    phase_editor.load_phase(pending_phase)

    def _remove_binding(self):
        """Remove selected binding."""
        selection = self.listbox.curselection()
        if not selection:
            messagebox.showinfo("No Selection", "Please select a marker binding to remove.", parent=self)
            return

        index = selection[0]
        binding = self.bindings[index]

        # Confirm deletion
        confirm = messagebox.askyesno(
            "Confirm Removal",
            f"Remove marker binding:\n\n{self._format_binding_display(binding)}",
            parent=self
        )

        if confirm:
            del self.bindings[index]
            self._refresh_listbox()
            self._on_bindings_changed()

    def _move_up(self):
        """Move selected binding up in list."""
        selection = self.listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index > 0:
            # Swap with previous item
            self.bindings[index], self.bindings[index - 1] = self.bindings[index - 1], self.bindings[index]
            self._refresh_listbox()
            self.listbox.selection_set(index - 1)
            self._on_bindings_changed()

    def _move_down(self):
        """Move selected binding down in list."""
        selection = self.listbox.curselection()
        if not selection:
            return

        index = selection[0]
        if index < len(self.bindings) - 1:
            # Swap with next item
            self.bindings[index], self.bindings[index + 1] = self.bindings[index + 1], self.bindings[index]
            self._refresh_listbox()
            self.listbox.selection_set(index + 1)
            self._on_bindings_changed()

    def _on_bindings_changed(self):
        """Call change callback if registered."""
        if self.on_change:
            self.on_change()

    def get_bindings(self) -> List[MarkerBinding]:
        """Get current list of MarkerBinding objects."""
        return self.bindings.copy()

    def set_bindings(self, bindings: List[MarkerBinding]):
        """Set bindings list programmatically."""
        self.bindings = bindings.copy()
        self._refresh_listbox()
