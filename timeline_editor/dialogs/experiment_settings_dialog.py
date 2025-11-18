"""
Experiment Settings Dialog.

Allows configuration of experiment-level settings stored in Timeline.metadata.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Dict, Any, List
import sys
import os
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog


class ExperimentSettingsDialog(FormDialog):
    """
    Dialog for configuring experiment-level settings.

    Settings:
    - Experiment name and description
    - Output directory
    - LSL settings (stream name, enabled/disabled)
    - LabRecorder auto-start (RCS host/port)

    Note: Audio devices and displays are configured via Device Setup dialog.
    """

    def __init__(self, parent, current_metadata: Dict[str, Any]):
        """
        Initialize experiment settings dialog.

        Args:
            parent: Parent window
            current_metadata: Current Timeline.metadata dictionary
        """
        self.current_metadata = current_metadata.copy()

        super().__init__(parent, "Experiment Settings", width=500, height=600)

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # content_frame is already scrollable from BaseDialog - no canvas needed

        # === General Settings ===
        general_frame = ttk.LabelFrame(content_frame, text="General", padding=10)
        general_frame.pack(fill=tk.X, padx=5, pady=5)

        self.add_text_field(
            general_frame,
            "Experiment Name:",
            "name",
            default=self.current_metadata.get('name', 'Untitled Experiment'),
            width=35
        )

        self.add_text_area(
            general_frame,
            "Description:",
            "description",
            default=self.current_metadata.get('description', ''),
            height=3
        )

        # === Output Directory ===
        output_frame = ttk.LabelFrame(content_frame, text="Data Output", padding=10)
        output_frame.pack(fill=tk.X, padx=5, pady=5)

        # Output directory field with browse button
        output_dir_row = ttk.Frame(output_frame)
        output_dir_row.pack(fill=tk.X, pady=5)

        ttk.Label(output_dir_row, text="Output Directory:", width=15, anchor=tk.W).pack(side=tk.LEFT, padx=5)

        self.output_dir_var = tk.StringVar(value=self.current_metadata.get('output_directory', '') or '')
        output_dir_entry = ttk.Entry(output_dir_row, textvariable=self.output_dir_var, width=30)
        output_dir_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)

        ttk.Button(
            output_dir_row,
            text="Browse...",
            command=self._browse_output_directory
        ).pack(side=tk.LEFT, padx=5)

        # Validation indicator
        self.output_dir_status_label = ttk.Label(
            output_frame,
            text="",
            font=("Arial", 8),
            foreground="gray"
        )
        self.output_dir_status_label.pack(fill=tk.X, pady=(0, 5))

        # Update status when directory changes
        self.output_dir_var.trace_add('write', lambda *args: self._check_output_directory())
        self._check_output_directory()  # Initial check

        # Info about data saving
        info_label = ttk.Label(
            output_frame,
            text="⚠️ Output directory is required to run experiments.\n"
                 "Data files will be saved with format: sub-{ID}_ses-{#}_{timestamp}.csv",
            font=("Arial", 8),
            foreground="#666666",
            wraplength=450,
            justify=tk.LEFT
        )
        info_label.pack(fill=tk.X, pady=(5, 0))

        # === LSL Settings ===
        lsl_frame = ttk.LabelFrame(content_frame, text="LSL (Lab Streaming Layer)", padding=10)
        lsl_frame.pack(fill=tk.X, padx=5, pady=5)

        self.add_checkbox(
            lsl_frame,
            "Enable LSL markers",
            "lsl_enabled",
            default=self.current_metadata.get('lsl_enabled', True)
        )

        self.add_text_field(
            lsl_frame,
            "Stream Name:",
            "lsl_stream_name",
            default=self.current_metadata.get('lsl_stream_name', 'ExpEvent_Markers'),
            width=35
        )

        # Info label
        info_label = ttk.Label(
            lsl_frame,
            text="LSL markers are sent during experiment execution.\n"
                 "Requires LabRecorder or similar software to record markers.",
            font=("Arial", 8),
            foreground="gray",
            wraplength=400,
            justify=tk.LEFT
        )
        info_label.pack(fill=tk.X, pady=(5, 0))

        # === LabRecorder Settings ===
        labrecorder_frame = ttk.LabelFrame(content_frame, text="LabRecorder Auto-Start", padding=10)
        labrecorder_frame.pack(fill=tk.X, padx=5, pady=5)

        # Enable checkbox
        self.add_checkbox(
            labrecorder_frame,
            "Enable LabRecorder auto-start",
            "labrecorder_enabled",
            default=self.current_metadata.get('labrecorder_enabled', False)
        )

        # RCS host
        self.add_text_field(
            labrecorder_frame,
            "RCS Host:",
            "labrecorder_host",
            default=self.current_metadata.get('labrecorder_host', 'localhost'),
            width=35
        )

        # RCS port
        self.add_text_field(
            labrecorder_frame,
            "RCS Port:",
            "labrecorder_port",
            default=str(self.current_metadata.get('labrecorder_port', 22345)),
            width=10
        )

        # Test connection button
        test_conn_frame = ttk.Frame(labrecorder_frame)
        test_conn_frame.pack(fill=tk.X, pady=5)
        ttk.Label(test_conn_frame, text="", width=15).pack(side=tk.LEFT)  # Spacer
        ttk.Button(
            test_conn_frame,
            text="Test Connection",
            command=self._test_labrecorder_connection
        ).pack(side=tk.LEFT)

        self.labrecorder_status_label = ttk.Label(
            test_conn_frame,
            text="",
            font=("Arial", 9),
            foreground="gray"
        )
        self.labrecorder_status_label.pack(side=tk.LEFT, padx=10)

        # Info label
        lr_info_label = ttk.Label(
            labrecorder_frame,
            text="⚠️ LabRecorder must be running with Remote Control Socket enabled.\n"
                 "Auto-start will record ALL available LSL streams (EEG, Markers, face sync, etc.)\n"
                 "Filename format: sub-{ID:03d}_ses-{#:02d}_{task}.xdf",
            font=("Arial", 8),
            foreground="gray",
            wraplength=400,
            justify=tk.LEFT
        )
        lr_info_label.pack(fill=tk.X, pady=(5, 0))

    def _test_labrecorder_connection(self):
        """Test connection to LabRecorder RCS."""
        host = self.form_vars['labrecorder_host'].get().strip()
        port_str = self.form_vars['labrecorder_port'].get().strip()

        # Validate port
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError("Port must be between 1 and 65535")
        except ValueError as e:
            self.labrecorder_status_label.config(
                text=f"❌ Invalid port",
                foreground="red"
            )
            messagebox.showerror("Invalid Port", f"Port must be a valid number (1-65535)")
            return

        # Try to connect
        self.labrecorder_status_label.config(
            text="⏳ Connecting...",
            foreground="orange"
        )
        self.labrecorder_status_label.update()

        try:
            from core.labrecorder_control import LabRecorderController

            controller = LabRecorderController(host=host, port=port, timeout=3.0)
            success = controller.connect()
            controller.close()

            if success:
                self.labrecorder_status_label.config(
                    text="✓ Connected",
                    foreground="green"
                )
                messagebox.showinfo(
                    "Connection Successful",
                    f"Successfully connected to LabRecorder at {host}:{port}\n\n"
                    "LabRecorder is ready for auto-start."
                )
            else:
                self.labrecorder_status_label.config(
                    text="❌ Failed",
                    foreground="red"
                )
                messagebox.showerror(
                    "Connection Failed",
                    f"Could not connect to LabRecorder at {host}:{port}\n\n"
                    "Make sure:\n"
                    "1. LabRecorder is running\n"
                    "2. Remote Control Socket (RCS) is enabled in LabRecorder settings\n"
                    "3. Host and port are correct"
                )
        except Exception as e:
            self.labrecorder_status_label.config(
                text="❌ Error",
                foreground="red"
            )
            messagebox.showerror(
                "Connection Error",
                f"Error testing connection:\n\n{str(e)}"
            )

    def _browse_output_directory(self):
        """Browse for output directory."""
        initial_dir = self.output_dir_var.get() or os.path.expanduser("~")

        directory = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=initial_dir
        )

        if directory:
            self.output_dir_var.set(directory)

    def _check_output_directory(self):
        """Check if output directory is valid and update status label."""
        output_dir = self.output_dir_var.get().strip()

        if not output_dir:
            self.output_dir_status_label.config(
                text="⚠️ No directory selected - required for running experiments",
                foreground="orange"
            )
        elif not os.path.exists(output_dir):
            self.output_dir_status_label.config(
                text="❌ Directory does not exist",
                foreground="red"
            )
        elif not os.path.isdir(output_dir):
            self.output_dir_status_label.config(
                text="❌ Path is not a directory",
                foreground="red"
            )
        elif not os.access(output_dir, os.W_OK):
            self.output_dir_status_label.config(
                text="❌ Directory is not writable",
                foreground="red"
            )
        else:
            self.output_dir_status_label.config(
                text="✓ Directory is valid and writable",
                foreground="green"
            )

    def _validate(self) -> List[str]:
        """Validate experiment settings."""
        errors = []

        # Validate name
        name = self.form_vars['name'].get().strip()
        if not name:
            errors.append("Experiment name is required")

        # Validate LSL stream name
        if self.form_vars['lsl_enabled'].get():
            stream_name = self.form_vars['lsl_stream_name'].get().strip()
            if not stream_name:
                errors.append("LSL stream name is required when LSL is enabled")

        # Validate LabRecorder settings
        if self.form_vars['labrecorder_enabled'].get():
            host = self.form_vars['labrecorder_host'].get().strip()
            port_str = self.form_vars['labrecorder_port'].get().strip()

            if not host:
                errors.append("LabRecorder host is required when auto-start is enabled")

            try:
                port = int(port_str)
                if not (1 <= port <= 65535):
                    errors.append("LabRecorder port must be between 1 and 65535")
            except ValueError:
                errors.append("LabRecorder port must be a valid number")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect experiment settings."""
        form_values = self.get_form_values()

        # Get output directory (use empty string if not set, not None)
        output_dir = self.output_dir_var.get().strip()

        # Parse LabRecorder port
        labrecorder_port = 22345  # Default
        try:
            labrecorder_port = int(form_values['labrecorder_port'])
        except (ValueError, KeyError):
            pass

        return {
            'name': form_values['name'].strip(),
            'description': form_values['description'].strip(),
            'output_directory': output_dir if output_dir else None,
            'lsl_enabled': form_values['lsl_enabled'],
            'lsl_stream_name': form_values['lsl_stream_name'].strip(),
            'labrecorder_enabled': form_values['labrecorder_enabled'],
            'labrecorder_host': form_values['labrecorder_host'].strip(),
            'labrecorder_port': labrecorder_port
        }
