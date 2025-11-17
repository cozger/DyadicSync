"""
Experiment Settings Dialog.

Allows configuration of experiment-level settings stored in Timeline.metadata.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, List
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from timeline_editor.dialogs.base_dialog import FormDialog
from timeline_editor.dialogs.widgets import DurationPicker
from core.device_scanner import DeviceScanner


class ExperimentSettingsDialog(FormDialog):
    """
    Dialog for configuring experiment-level settings.

    Settings:
    - Experiment name and description
    - Audio devices (P1 and P2)
    - Baseline duration
    - LSL settings (stream name, enabled/disabled)
    """

    def __init__(self, parent, current_metadata: Dict[str, Any]):
        """
        Initialize experiment settings dialog.

        Args:
            parent: Parent window
            current_metadata: Current Timeline.metadata dictionary
        """
        self.current_metadata = current_metadata.copy()
        self.audio_devices = []
        self.device_scanner = None

        # Scan for audio devices
        self._scan_devices()

        super().__init__(parent, "Experiment Settings", width=500, height=600)

    def _scan_devices(self):
        """Scan for available audio devices."""
        try:
            self.device_scanner = DeviceScanner()
            devices = self.device_scanner.scan_audio_devices()
            self.audio_devices = devices.get('all', [])
        except Exception as e:
            print(f"Warning: Could not scan audio devices: {e}")
            self.audio_devices = []

    def _build_content(self, content_frame: ttk.Frame):
        """Build dialog content."""
        # Scrollable frame for all settings
        canvas = tk.Canvas(content_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(content_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # === General Settings ===
        general_frame = ttk.LabelFrame(scrollable_frame, text="General", padding=10)
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

        # === Device Setup Note ===
        note_frame = ttk.Frame(scrollable_frame)
        note_frame.pack(fill=tk.X, padx=5, pady=(5, 0))

        note_label = ttk.Label(
            note_frame,
            text="💡 For display configuration (monitors), use the Device Setup button in the toolbar.",
            font=('Arial', 9, 'italic'),
            foreground='#666666',
            wraplength=450
        )
        note_label.pack(anchor='w', padx=10)

        # === Audio Devices ===
        audio_frame = ttk.LabelFrame(scrollable_frame, text="Audio Devices", padding=10)
        audio_frame.pack(fill=tk.X, padx=5, pady=5)

        # Build device options for dropdown
        if self.audio_devices:
            device_options = [
                f"{dev['index']}: {dev['name']}" for dev in self.audio_devices
            ]
        else:
            device_options = ["No devices found"]

        # P1 audio device
        current_p1 = self.current_metadata.get('audio_device_1')
        p1_default = self._find_device_display(current_p1) if current_p1 is not None else ""

        self.add_dropdown(
            audio_frame,
            "Participant 1:",
            "audio_device_1",
            options=device_options,
            default=p1_default
        )

        # Test button for P1
        p1_test_frame = ttk.Frame(audio_frame)
        p1_test_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p1_test_frame, text="", width=15).pack(side=tk.LEFT)  # Spacer
        ttk.Button(
            p1_test_frame,
            text="Test Audio",
            command=lambda: self._test_audio(1)
        ).pack(side=tk.LEFT)

        # P2 audio device
        current_p2 = self.current_metadata.get('audio_device_2')
        p2_default = self._find_device_display(current_p2) if current_p2 is not None else ""

        self.add_dropdown(
            audio_frame,
            "Participant 2:",
            "audio_device_2",
            options=device_options,
            default=p2_default
        )

        # Test button for P2
        p2_test_frame = ttk.Frame(audio_frame)
        p2_test_frame.pack(fill=tk.X, pady=2)
        ttk.Label(p2_test_frame, text="", width=15).pack(side=tk.LEFT)  # Spacer
        ttk.Button(
            p2_test_frame,
            text="Test Audio",
            command=lambda: self._test_audio(2)
        ).pack(side=tk.LEFT)

        # Rescan button
        rescan_frame = ttk.Frame(audio_frame)
        rescan_frame.pack(fill=tk.X, pady=5)
        ttk.Label(rescan_frame, text="", width=15).pack(side=tk.LEFT)  # Spacer
        ttk.Button(
            rescan_frame,
            text="Rescan Devices",
            command=self._rescan_devices
        ).pack(side=tk.LEFT)

        # === Baseline Settings ===
        baseline_frame = ttk.LabelFrame(scrollable_frame, text="Baseline", padding=10)
        baseline_frame.pack(fill=tk.X, padx=5, pady=5)

        # Duration picker
        self.baseline_duration = DurationPicker(
            baseline_frame,
            label="Duration:",
            default_seconds=self.current_metadata.get('baseline_duration', 240),
            min_seconds=10,
            max_seconds=600,
            show_formatted=True
        )
        self.baseline_duration.pack(fill=tk.X, pady=5)

        # === LSL Settings ===
        lsl_frame = ttk.LabelFrame(scrollable_frame, text="LSL (Lab Streaming Layer)", padding=10)
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

    def _find_device_display(self, device_index: int) -> str:
        """
        Find display string for device index.

        Args:
            device_index: Device index

        Returns:
            Display string like "9: Device Name"
        """
        for dev in self.audio_devices:
            if dev['index'] == device_index:
                return f"{dev['index']}: {dev['name']}"
        return ""

    def _parse_device_index(self, display_str: str) -> int:
        """
        Parse device index from display string.

        Args:
            display_str: String like "9: Device Name"

        Returns:
            Device index (or None if invalid)
        """
        try:
            return int(display_str.split(':')[0])
        except (ValueError, IndexError):
            return None

    def _test_audio(self, participant: int):
        """
        Test audio device with sine wave.

        Args:
            participant: 1 or 2
        """
        device_key = f"audio_device_{participant}"
        display_str = self.form_vars[device_key].get()

        if display_str == "No devices found":
            messagebox.showwarning("No Device", "No audio devices available")
            return

        device_index = self._parse_device_index(display_str)

        if device_index is None:
            messagebox.showwarning("Invalid Device", "Please select a valid audio device")
            return

        try:
            from core.device_manager import DeviceManager

            # Create temporary device manager
            dm = DeviceManager()

            # Test audio
            messagebox.showinfo(
                "Testing Audio",
                f"Playing test tone on device {device_index}...\n\n"
                f"You should hear a 440Hz sine wave for 1 second."
            )

            dm.test_audio_device(device_index, duration=1.0)

            messagebox.showinfo("Test Complete", "Audio test completed successfully!")

        except Exception as e:
            messagebox.showerror("Test Failed", f"Audio test failed:\n\n{str(e)}")

    def _rescan_devices(self):
        """Rescan audio devices and update dropdowns."""
        self._scan_devices()

        # Update device options
        if self.audio_devices:
            device_options = [
                f"{dev['index']}: {dev['name']}" for dev in self.audio_devices
            ]
        else:
            device_options = ["No devices found"]

        # Update comboboxes
        self.form_widgets['audio_device_1'].config(values=device_options)
        self.form_widgets['audio_device_2'].config(values=device_options)

        messagebox.showinfo("Rescan Complete", f"Found {len(self.audio_devices)} audio devices")

    def _validate(self) -> List[str]:
        """Validate experiment settings."""
        errors = []

        # Validate name
        name = self.form_vars['name'].get().strip()
        if not name:
            errors.append("Experiment name is required")

        # Validate audio devices
        p1_device = self.form_vars['audio_device_1'].get()
        p2_device = self.form_vars['audio_device_2'].get()

        if p1_device == "No devices found" or p2_device == "No devices found":
            errors.append("Audio devices must be configured")

        # Check if same device selected for both
        if p1_device and p2_device and p1_device == p2_device:
            errors.append("Participants must use different audio devices")

        # Validate LSL stream name
        if self.form_vars['lsl_enabled'].get():
            stream_name = self.form_vars['lsl_stream_name'].get().strip()
            if not stream_name:
                errors.append("LSL stream name is required when LSL is enabled")

        return errors

    def _collect_result(self) -> Dict[str, Any]:
        """Collect experiment settings."""
        form_values = self.get_form_values()

        # Parse device indices
        p1_device = self._parse_device_index(form_values['audio_device_1'])
        p2_device = self._parse_device_index(form_values['audio_device_2'])

        # Get baseline duration
        baseline_duration = self.baseline_duration.get()

        return {
            'name': form_values['name'].strip(),
            'description': form_values['description'].strip(),
            'audio_device_1': p1_device,
            'audio_device_2': p2_device,
            'baseline_duration': baseline_duration,
            'lsl_enabled': form_values['lsl_enabled'],
            'lsl_stream_name': form_values['lsl_stream_name'].strip()
        }
