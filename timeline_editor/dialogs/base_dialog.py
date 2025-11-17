"""
Base dialog class for Timeline Editor dialogs.

Provides:
- Consistent styling and layout
- Validation framework with real-time feedback
- Standard OK/Cancel buttons
- Modal behavior
"""

import tkinter as tk
from tkinter import ttk
from typing import Optional, Dict, Any, List, Callable


class BaseDialog(tk.Toplevel):
    """
    Base class for all Timeline Editor dialogs.

    Features:
    - Modal dialog with grab_set()
    - Consistent styling (E-Prime style)
    - Validation framework
    - Standard button layout
    - Result dictionary

    Usage:
        class MyDialog(BaseDialog):
            def _build_content(self, content_frame):
                # Build your UI here
                self.my_var = tk.StringVar()
                ttk.Label(content_frame, text="Name:").pack()
                ttk.Entry(content_frame, textvariable=self.my_var).pack()

            def _validate(self) -> List[str]:
                errors = []
                if not self.my_var.get():
                    errors.append("Name is required")
                return errors

            def _collect_result(self) -> Dict[str, Any]:
                return {'name': self.my_var.get()}
    """

    def __init__(self, parent, title: str = "Dialog", width: int = 400, height: int = 300):
        """
        Initialize base dialog.

        Args:
            parent: Parent window
            title: Dialog title
            width: Dialog width in pixels
            height: Dialog height in pixels
        """
        super().__init__(parent)

        self.result: Optional[Dict[str, Any]] = None
        self.validation_errors: List[str] = []

        # Configure dialog
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.transient(parent)
        self.resizable(True, True)

        # E-Prime style colors
        self.configure(bg="#F0F0F0")

        # Center on parent
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Build UI
        self._build_ui()

        # Modal behavior
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        # Focus on dialog
        self.focus_set()

    def _build_ui(self):
        """Build the dialog UI (called by __init__)."""
        # Title label (optional, can be overridden)
        if hasattr(self, 'dialog_description'):
            desc_label = ttk.Label(
                self,
                text=self.dialog_description,
                font=("Arial", 10),
                wraplength=self.winfo_reqwidth() - 40
            )
            desc_label.pack(pady=(10, 5), padx=10)

        # Content frame (scrollable if needed)
        self.content_frame = ttk.Frame(self)
        self.content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Let subclass build content
        self._build_content(self.content_frame)

        # Validation error label
        self.error_label = ttk.Label(
            self,
            text="",
            foreground="red",
            font=("Arial", 9),
            wraplength=self.winfo_reqwidth() - 40
        )
        self.error_label.pack(pady=(0, 5), padx=10)

        # Button frame
        button_frame = ttk.Frame(self)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=10)

        # Buttons (right-aligned)
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel
        ).pack(side=tk.RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="OK",
            command=self._on_ok,
            style="Accent.TButton"
        ).pack(side=tk.RIGHT)

        # Bind Enter/Escape
        self.bind("<Return>", lambda e: self._on_ok())
        self.bind("<Escape>", lambda e: self._on_cancel())

    def _build_content(self, content_frame: ttk.Frame):
        """
        Build dialog content (override in subclass).

        Args:
            content_frame: Frame to add content to
        """
        raise NotImplementedError("Subclass must implement _build_content()")

    def _validate(self) -> List[str]:
        """
        Validate dialog inputs (override in subclass).

        Returns:
            List of error messages (empty if valid)
        """
        return []

    def _collect_result(self) -> Dict[str, Any]:
        """
        Collect dialog result (override in subclass).

        Returns:
            Dictionary of result values
        """
        return {}

    def _on_ok(self):
        """Handle OK button click."""
        # Validate
        errors = self._validate()
        self.validation_errors = errors

        if errors:
            # Show first error
            self.error_label.config(text=f"Error: {errors[0]}")
            return

        # Clear error
        self.error_label.config(text="")

        # Collect result
        self.result = self._collect_result()

        # Close dialog
        self.grab_release()
        self.destroy()

    def _on_cancel(self):
        """Handle Cancel button click."""
        self.result = None
        self.grab_release()
        self.destroy()

    def show(self) -> Optional[Dict[str, Any]]:
        """
        Show dialog and wait for result.

        Returns:
            Result dictionary if OK clicked, None if cancelled
        """
        self.wait_window()
        return self.result


class FormDialog(BaseDialog):
    """
    Extended base dialog with form-building helpers.

    Provides methods to easily build form-style dialogs with labels and inputs.
    """

    def __init__(self, parent, title: str = "Dialog", width: int = 400, height: int = 300):
        """Initialize form dialog."""
        self.form_widgets: Dict[str, tk.Widget] = {}
        self.form_vars: Dict[str, tk.Variable] = {}
        super().__init__(parent, title, width, height)

    def add_text_field(self, parent: ttk.Frame, label: str, key: str,
                       default: str = "", width: int = 30) -> ttk.Entry:
        """
        Add a text input field to the form.

        Args:
            parent: Parent frame
            label: Field label
            key: Key for result dictionary
            default: Default value
            width: Entry width

        Returns:
            Entry widget
        """
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=5)

        ttk.Label(row_frame, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        var = tk.StringVar(value=default)
        entry = ttk.Entry(row_frame, textvariable=var, width=width)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.form_vars[key] = var
        self.form_widgets[key] = entry

        return entry

    def add_number_field(self, parent: ttk.Frame, label: str, key: str,
                         default: float = 0.0, min_val: float = 0.0,
                         max_val: float = 1000.0) -> ttk.Spinbox:
        """
        Add a numeric input field to the form.

        Args:
            parent: Parent frame
            label: Field label
            key: Key for result dictionary
            default: Default value
            min_val: Minimum value
            max_val: Maximum value

        Returns:
            Spinbox widget
        """
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=5)

        ttk.Label(row_frame, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        var = tk.DoubleVar(value=default)
        spinbox = ttk.Spinbox(
            row_frame,
            from_=min_val,
            to=max_val,
            textvariable=var,
            width=10
        )
        spinbox.pack(side=tk.LEFT)

        self.form_vars[key] = var
        self.form_widgets[key] = spinbox

        return spinbox

    def add_checkbox(self, parent: ttk.Frame, label: str, key: str,
                     default: bool = False) -> ttk.Checkbutton:
        """
        Add a checkbox to the form.

        Args:
            parent: Parent frame
            label: Checkbox label
            key: Key for result dictionary
            default: Default checked state

        Returns:
            Checkbutton widget
        """
        var = tk.BooleanVar(value=default)
        checkbox = ttk.Checkbutton(parent, text=label, variable=var)
        checkbox.pack(fill=tk.X, pady=5)

        self.form_vars[key] = var
        self.form_widgets[key] = checkbox

        return checkbox

    def add_dropdown(self, parent: ttk.Frame, label: str, key: str,
                     options: List[str], default: str = "") -> ttk.Combobox:
        """
        Add a dropdown selector to the form.

        Args:
            parent: Parent frame
            label: Field label
            key: Key for result dictionary
            options: List of options
            default: Default selection

        Returns:
            Combobox widget
        """
        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=tk.X, pady=5)

        ttk.Label(row_frame, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        var = tk.StringVar(value=default if default else (options[0] if options else ""))
        combo = ttk.Combobox(row_frame, textvariable=var, values=options, state='readonly', width=27)
        combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.form_vars[key] = var
        self.form_widgets[key] = combo

        return combo

    def add_text_area(self, parent: ttk.Frame, label: str, key: str,
                      default: str = "", height: int = 5) -> tk.Text:
        """
        Add a multi-line text area to the form.

        Args:
            parent: Parent frame
            label: Field label
            key: Key for result dictionary
            default: Default text
            height: Text area height in lines

        Returns:
            Text widget
        """
        label_widget = ttk.Label(parent, text=label, anchor=tk.W)
        label_widget.pack(fill=tk.X, pady=(5, 2))

        text = tk.Text(parent, height=height, width=40, wrap=tk.WORD)
        text.pack(fill=tk.BOTH, expand=True, pady=(0, 5))
        text.insert("1.0", default)

        self.form_widgets[key] = text

        return text

    def get_form_values(self) -> Dict[str, Any]:
        """
        Get all form values as a dictionary.

        Returns:
            Dictionary of form values
        """
        result = {}

        # Get variable values
        for key, var in self.form_vars.items():
            result[key] = var.get()

        # Get text widget values
        for key, widget in self.form_widgets.items():
            if isinstance(widget, tk.Text):
                result[key] = widget.get("1.0", tk.END).strip()

        return result

    def _collect_result(self) -> Dict[str, Any]:
        """Default result collection using form values."""
        return self.get_form_values()


class ConfirmDialog(BaseDialog):
    """
    Simple confirmation dialog with custom message.

    Usage:
        dialog = ConfirmDialog(parent, "Are you sure?", "This action cannot be undone.")
        if dialog.show():
            # User confirmed
            pass
    """

    def __init__(self, parent, title: str, message: str, width: int = 400, height: int = 150):
        """
        Initialize confirmation dialog.

        Args:
            parent: Parent window
            title: Dialog title
            message: Confirmation message
            width: Dialog width
            height: Dialog height
        """
        self.message = message
        super().__init__(parent, title, width, height)

    def _build_content(self, content_frame: ttk.Frame):
        """Build confirmation message."""
        message_label = ttk.Label(
            content_frame,
            text=self.message,
            font=("Arial", 10),
            wraplength=self.winfo_reqwidth() - 40,
            justify=tk.CENTER
        )
        message_label.pack(expand=True, pady=20)

    def _collect_result(self) -> Dict[str, Any]:
        """Return confirmed=True."""
        return {'confirmed': True}

    def show(self) -> bool:
        """
        Show dialog and return confirmation.

        Returns:
            True if confirmed, False if cancelled
        """
        result = super().show()
        return result is not None and result.get('confirmed', False)
