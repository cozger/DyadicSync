"""
Reusable widgets for Timeline Editor dialogs.

Provides specialized input widgets for common parameter types:
- Duration picker (seconds/minutes)
- File path browser
- Template variable selector
- Scale type selector (Likert-7, etc.)
- Key binding widget
- Validation label with icons
"""

import tkinter as tk
from tkinter import ttk, filedialog
from typing import Callable, Optional, List
from pathlib import Path


class DurationPicker(ttk.Frame):
    """
    Widget for picking duration in seconds with optional minutes:seconds display.

    Features:
    - Spinbox for seconds
    - Optional minutes:seconds display
    - Validation (min/max)
    """

    def __init__(self, parent, label: str = "Duration:", default_seconds: float = 3.0,
                 min_seconds: float = 0.1, max_seconds: float = 3600.0,
                 show_formatted: bool = True):
        """
        Initialize duration picker.

        Args:
            parent: Parent widget
            label: Label text
            default_seconds: Default duration in seconds
            min_seconds: Minimum allowed seconds
            max_seconds: Maximum allowed seconds
            show_formatted: Show MM:SS formatted display
        """
        super().__init__(parent)

        self.min_seconds = min_seconds
        self.max_seconds = max_seconds

        # Label
        ttk.Label(self, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        # Spinbox for seconds
        self.seconds_var = tk.DoubleVar(value=default_seconds)
        self.spinbox = ttk.Spinbox(
            self,
            from_=min_seconds,
            to=max_seconds,
            textvariable=self.seconds_var,
            width=8,
            command=self._on_change
        )
        self.spinbox.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Label(self, text="seconds").pack(side=tk.LEFT)

        # Formatted display (MM:SS)
        if show_formatted:
            self.formatted_label = ttk.Label(
                self,
                text=self._format_duration(default_seconds),
                foreground="gray"
            )
            self.formatted_label.pack(side=tk.LEFT, padx=(10, 0))

            # Update formatted display when value changes
            self.seconds_var.trace_add('write', lambda *args: self._update_formatted())
        else:
            self.formatted_label = None

    def _format_duration(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"({mins:02d}:{secs:02d})"

    def _update_formatted(self):
        """Update formatted display."""
        if self.formatted_label:
            try:
                seconds = self.seconds_var.get()
                self.formatted_label.config(text=self._format_duration(seconds))
            except tk.TclError:
                pass

    def _on_change(self):
        """Handle spinbox change."""
        self._update_formatted()

    def get(self) -> float:
        """Get current duration in seconds."""
        return self.seconds_var.get()

    def set(self, seconds: float):
        """Set duration in seconds."""
        self.seconds_var.set(max(self.min_seconds, min(self.max_seconds, seconds)))


class FilePathWidget(ttk.Frame):
    """
    Widget for selecting file paths with browse button.

    Features:
    - Entry field for path
    - Browse button
    - File/directory mode
    - File type filters
    - Validation (file exists)
    """

    def __init__(self, parent, label: str = "File:", default_path: str = "",
                 mode: str = 'file', file_types: List = None, width: int = 30):
        """
        Initialize file path widget.

        Args:
            parent: Parent widget
            label: Label text
            default_path: Default file path
            mode: 'file' or 'directory'
            file_types: List of (description, pattern) tuples for file filter
            width: Entry field width
        """
        super().__init__(parent)

        self.mode = mode
        self.file_types = file_types or [("All files", "*.*")]

        # Label
        if label:
            ttk.Label(self, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        # Entry
        self.path_var = tk.StringVar(value=default_path)
        self.entry = ttk.Entry(self, textvariable=self.path_var, width=width)
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # Browse button
        browse_btn = ttk.Button(self, text="Browse...", command=self._browse, width=10)
        browse_btn.pack(side=tk.LEFT)

        # Validation indicator
        self.valid_label = ttk.Label(self, text="", foreground="red", width=3)
        self.valid_label.pack(side=tk.LEFT)

        # Validate on change
        self.path_var.trace_add('write', lambda *args: self._validate())
        self._validate()

    def _browse(self):
        """Open file/directory browser."""
        if self.mode == 'directory':
            path = filedialog.askdirectory(
                title="Select Directory",
                initialdir=self.path_var.get() or "."
            )
        else:
            path = filedialog.askopenfilename(
                title="Select File",
                filetypes=self.file_types,
                initialdir=Path(self.path_var.get()).parent if self.path_var.get() else "."
            )

        if path:
            self.path_var.set(path)

    def _validate(self):
        """Validate current path."""
        path = self.path_var.get()
        if not path:
            self.valid_label.config(text="", foreground="gray")
            return

        path_obj = Path(path)

        if self.mode == 'directory':
            if path_obj.is_dir():
                self.valid_label.config(text="✓", foreground="green")
            else:
                self.valid_label.config(text="✗", foreground="red")
        else:
            if path_obj.is_file():
                self.valid_label.config(text="✓", foreground="green")
            else:
                self.valid_label.config(text="✗", foreground="orange")  # May be created later

    def get(self) -> str:
        """Get current file path."""
        return self.path_var.get()

    def set(self, path: str):
        """Set file path."""
        self.path_var.set(path)

    def is_valid(self) -> bool:
        """Check if current path is valid."""
        path = self.path_var.get()
        if not path:
            return False

        path_obj = Path(path)
        if self.mode == 'directory':
            return path_obj.is_dir()
        else:
            return path_obj.is_file()


class TemplateVariableWidget(ttk.Frame):
    """
    Widget for selecting between template variable or fixed file path.

    Features:
    - Radio buttons to choose mode (template vs. fixed)
    - Dropdown for template variables
    - File browser for fixed paths
    """

    def __init__(self, parent, label: str = "Video:", available_variables: List[str] = None,
                 default_mode: str = 'template', default_value: str = "{video1}"):
        """
        Initialize template variable widget.

        Args:
            parent: Parent widget
            label: Label text
            available_variables: List of available template variables (without braces)
            default_mode: 'template' or 'fixed'
            default_value: Default value
        """
        super().__init__(parent)

        self.available_variables = available_variables or ['video1', 'video2']

        # Label
        ttk.Label(self, text=label, font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=(5, 2))

        # Mode selection
        self.mode_var = tk.StringVar(value=default_mode)

        # Template radio + dropdown
        template_frame = ttk.Frame(self)
        template_frame.pack(fill=tk.X, pady=2)

        ttk.Radiobutton(
            template_frame,
            text="Template variable:",
            variable=self.mode_var,
            value='template',
            command=self._on_mode_change
        ).pack(side=tk.LEFT)

        # Template dropdown
        template_options = [f"{{{var}}}" for var in self.available_variables]
        self.template_var = tk.StringVar(
            value=default_value if default_mode == 'template' else template_options[0]
        )
        self.template_combo = ttk.Combobox(
            template_frame,
            textvariable=self.template_var,
            values=template_options,
            state='readonly',
            width=15
        )
        self.template_combo.pack(side=tk.LEFT, padx=(5, 0))

        # Fixed path radio + browser
        fixed_frame = ttk.Frame(self)
        fixed_frame.pack(fill=tk.X, pady=2)

        ttk.Radiobutton(
            fixed_frame,
            text="Fixed path:",
            variable=self.mode_var,
            value='fixed',
            command=self._on_mode_change
        ).pack(side=tk.LEFT)

        # File browser (without label since we have radio button)
        self.file_widget = FilePathWidget(
            fixed_frame,
            label="",
            default_path=default_value if default_mode == 'fixed' else "",
            file_types=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv"),
                ("All files", "*.*")
            ],
            width=25
        )
        self.file_widget.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(5, 0))

        # Update enabled state
        self._on_mode_change()

    def _on_mode_change(self):
        """Handle mode change."""
        if self.mode_var.get() == 'template':
            self.template_combo.config(state='readonly')
            self.file_widget.entry.config(state='disabled')
            self.file_widget.children['!button'].config(state='disabled')
        else:
            self.template_combo.config(state='disabled')
            self.file_widget.entry.config(state='normal')
            self.file_widget.children['!button'].config(state='normal')

    def get(self) -> str:
        """Get current value (template variable or file path)."""
        if self.mode_var.get() == 'template':
            return self.template_var.get()
        else:
            return self.file_widget.get()

    def set(self, value: str):
        """Set value (auto-detect mode based on braces)."""
        if value.startswith('{') and value.endswith('}'):
            self.mode_var.set('template')
            self.template_var.set(value)
        else:
            self.mode_var.set('fixed')
            self.file_widget.set(value)
        self._on_mode_change()


class ScaleTypeSelector(ttk.Frame):
    """
    Widget for selecting rating scale type.

    Features:
    - Dropdown for predefined scales
    - Preview of scale range
    """

    SCALE_TYPES = {
        'likert7': '7-point Likert (1-7)',
        'likert5': '5-point Likert (1-5)',
        'binary': 'Binary (Yes/No)',
        'custom': 'Custom'
    }

    def __init__(self, parent, label: str = "Scale Type:", default: str = 'likert7'):
        """
        Initialize scale type selector.

        Args:
            parent: Parent widget
            label: Label text
            default: Default scale type
        """
        super().__init__(parent)

        # Label
        ttk.Label(self, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        # Dropdown
        self.scale_var = tk.StringVar(value=default)
        self.combo = ttk.Combobox(
            self,
            textvariable=self.scale_var,
            values=list(self.SCALE_TYPES.values()),
            state='readonly',
            width=25
        )
        self.combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Set to display value
        self.combo.set(self.SCALE_TYPES[default])

    def get(self) -> str:
        """Get current scale type key."""
        display_value = self.scale_var.get()
        for key, value in self.SCALE_TYPES.items():
            if value == display_value:
                return key
        return 'likert7'

    def set(self, scale_type: str):
        """Set scale type by key."""
        if scale_type in self.SCALE_TYPES:
            self.combo.set(self.SCALE_TYPES[scale_type])


class KeyBindingWidget(ttk.Frame):
    """
    Widget for configuring key bindings.

    Features:
    - Entry that captures key presses
    - Display current binding
    - Clear button
    """

    def __init__(self, parent, label: str = "Key:", default_key: str = "space"):
        """
        Initialize key binding widget.

        Args:
            parent: Parent widget
            label: Label text
            default_key: Default key name
        """
        super().__init__(parent)

        # Label
        ttk.Label(self, text=label, width=15, anchor=tk.W).pack(side=tk.LEFT)

        # Entry (read-only, captures key press)
        self.key_var = tk.StringVar(value=default_key)
        self.entry = ttk.Entry(self, textvariable=self.key_var, width=15, state='readonly')
        self.entry.pack(side=tk.LEFT, padx=(0, 5))

        # Bind key capture
        self.entry.bind('<KeyPress>', self._on_key_press)
        self.entry.bind('<FocusIn>', lambda e: self.entry.config(foreground='blue'))
        self.entry.bind('<FocusOut>', lambda e: self.entry.config(foreground='black'))

        # Clear button
        ttk.Button(self, text="Clear", command=self._clear, width=8).pack(side=tk.LEFT)

        # Hint label
        ttk.Label(self, text="(click and press key)", foreground="gray", font=("Arial", 8)).pack(side=tk.LEFT, padx=(5, 0))

    def _on_key_press(self, event):
        """Capture key press."""
        key = event.keysym.lower()
        self.key_var.set(key)

    def _clear(self):
        """Clear key binding."""
        self.key_var.set("")

    def get(self) -> str:
        """Get current key binding."""
        return self.key_var.get()

    def set(self, key: str):
        """Set key binding."""
        self.key_var.set(key)


class ValidationLabel(ttk.Label):
    """
    Label that shows validation status with icon.

    Features:
    - ✓ for valid
    - ✗ for invalid
    - Color coding
    """

    def __init__(self, parent, **kwargs):
        """Initialize validation label."""
        super().__init__(parent, text="", **kwargs)

    def set_valid(self, message: str = ""):
        """Show valid status."""
        self.config(text=f"✓ {message}" if message else "✓", foreground="green")

    def set_invalid(self, message: str = ""):
        """Show invalid status."""
        self.config(text=f"✗ {message}" if message else "✗", foreground="red")

    def set_warning(self, message: str = ""):
        """Show warning status."""
        self.config(text=f"⚠ {message}" if message else "⚠", foreground="orange")

    def clear(self):
        """Clear validation status."""
        self.config(text="")
