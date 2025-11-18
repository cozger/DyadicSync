"""
Device Setup Dialog
Modal dialog for configuring hardware devices (displays and audio) from the Timeline Editor.
Saves configuration directly to Timeline metadata.

Author: DyadicSync Development Team
Date: 2025-11-16
"""

import tkinter as tk
from tkinter import ttk, messagebox
import sys
from pathlib import Path
from typing import Optional, Dict, List
import threading
import time

# Add core to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.device_scanner import DeviceScanner, DisplayInfo, AudioDeviceInfo
from core.execution.timeline import Timeline


class DeviceSetupDialog(tk.Toplevel):
    """
    Modal dialog for device configuration.
    Integrates with Timeline Editor to save settings directly to timeline metadata.
    """

    def __init__(self, parent, timeline: Timeline):
        """
        Initialize device setup dialog.

        Args:
            parent: Parent window (Timeline Editor)
            timeline: Timeline instance to save configuration to
        """
        super().__init__(parent)

        self.timeline = timeline
        self.result = None  # Will be set to True if user saves

        # Window configuration
        self.title("Device Setup")
        self.geometry("1200x100")  # Temporary height, will resize after content is built
        self.minsize(900, 400)

        # Make modal
        self.transient(parent)
        self.grab_set()

        # Initialize components
        self.scanner = DeviceScanner()

        # Theme colors (dark theme to match timeline editor)
        self.theme_colors = {
            'bg': '#1e1e1e',
            'fg': '#ffffff',
            'panel_bg': '#2b2b2b',
            'button_bg': '#3c3c3c',
            'button_fg': '#ffffff',
            'canvas_bg': '#2a2a2a',
            'entry_bg': '#3c3c3c',
            'entry_fg': '#ffffff',
            'status_ready': '#00ff88',
            'status_warning': '#ffaa00',
            'status_error': '#ff4466',
            'status_inactive': '#666666',
            'accent': '#00ff88',
        }

        # Device data
        self.displays: List[DisplayInfo] = []
        self.audio_output_devices: List[AudioDeviceInfo] = []
        self.audio_input_devices: List[AudioDeviceInfo] = []

        # Widget references
        self.status_labels: Dict[str, tk.Label] = {}
        self.device_vars: Dict[str, tk.StringVar] = {}
        self.display_combos: Dict[str, ttk.Combobox] = {}
        self.audio_output_combos: Dict[str, ttk.Combobox] = {}
        self.audio_input_combos: Dict[str, ttk.Combobox] = {}

        # Setup UI
        self._configure_styles()
        self._create_ui()
        self._scan_devices()
        self._load_from_timeline()

        # Apply dynamic sizing and center on parent
        self.update_idletasks()
        required_height = self.winfo_reqheight()
        width = 1200

        # Set dynamic size
        self.geometry(f"{width}x{required_height}")
        self.minsize(900, required_height)

        # Center on parent
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (required_height // 2)
        self.geometry(f"{width}x{required_height}+{x}+{y}")

        # Configure window close
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

    def _configure_styles(self):
        """Configure TTK styles"""
        self.configure(bg=self.theme_colors['bg'])

    def _on_content_configure(self, event):
        """Update scroll region when content changes"""
        self.content_canvas.configure(scrollregion=self.content_canvas.bbox("all"))

    def _on_mousewheel(self, event):
        """Handle mousewheel scrolling"""
        self.content_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _create_ui(self):
        """Create the main UI"""
        # Main container
        main_frame = tk.Frame(self, bg=self.theme_colors['bg'])
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Title
        title_label = tk.Label(
            main_frame,
            text="Hardware Device Configuration",
            font=('Arial', 16, 'bold'),
            bg=self.theme_colors['bg'],
            fg=self.theme_colors['accent']
        )
        title_label.pack(anchor='w', pady=(0, 20))

        # Create scrollable content area
        content_container = tk.Frame(main_frame, bg=self.theme_colors['bg'])
        content_container.pack(fill='both', expand=True, pady=(0, 0))

        # Canvas for scrolling
        self.content_canvas = tk.Canvas(content_container, bg=self.theme_colors['bg'], highlightthickness=0)
        content_scrollbar = ttk.Scrollbar(content_container, orient=tk.VERTICAL, command=self.content_canvas.yview)

        # Scrollable frame inside canvas
        self.scrollable_content = tk.Frame(self.content_canvas, bg=self.theme_colors['bg'])
        self.scrollable_content.bind("<Configure>", self._on_content_configure)

        self.content_canvas.create_window((0, 0), window=self.scrollable_content, anchor=tk.NW)
        self.content_canvas.configure(yscrollcommand=content_scrollbar.set)

        # Pack canvas and scrollbar
        content_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Enable mousewheel scrolling
        self.content_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # Sections (now in scrollable_content)
        self._create_display_section(self.scrollable_content)
        self._create_audio_output_section(self.scrollable_content)
        self._create_audio_input_section(self.scrollable_content)
        self._create_status_section(self.scrollable_content)

        # Buttons at bottom (fixed, always visible)
        self._create_buttons(main_frame)

    def _create_display_section(self, parent):
        """Create display configuration section"""
        section = ttk.LabelFrame(parent, text="Display Configuration", padding=10)
        section.pack(fill='x', pady=(0, 15))

        # Control monitor
        tk.Label(section, text="Control Monitor (Experimenter):", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['control_monitor'] = tk.StringVar()
        control_combo = ttk.Combobox(section, textvariable=self.device_vars['control_monitor'], state='readonly')
        control_combo.pack(fill='x', pady=(0, 10))
        control_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('control'))
        self.display_combos['control'] = control_combo

        # Participant 1
        tk.Label(section, text="Participant 1 Monitor:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p1_monitor'] = tk.StringVar()
        p1_combo = ttk.Combobox(section, textvariable=self.device_vars['p1_monitor'], state='readonly')
        p1_combo.pack(fill='x', pady=(0, 10))
        p1_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('p1'))
        self.display_combos['p1'] = p1_combo

        # Participant 2
        tk.Label(section, text="Participant 2 Monitor:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p2_monitor'] = tk.StringVar()
        p2_combo = ttk.Combobox(section, textvariable=self.device_vars['p2_monitor'], state='readonly')
        p2_combo.pack(fill='x', pady=(0, 5))
        p2_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('p2'))
        self.display_combos['p2'] = p2_combo

    def _create_audio_output_section(self, parent):
        """Create audio output configuration section"""
        section = ttk.LabelFrame(parent, text="Audio Output Configuration", padding=10)
        section.pack(fill='x', pady=(0, 15))

        # Participant 1
        frame1 = tk.Frame(section)
        frame1.pack(fill='x', pady=(0, 10))

        tk.Label(frame1, text="Participant 1:", font=('Arial', 9)).pack(anchor='w')
        audio_frame = tk.Frame(frame1)
        audio_frame.pack(fill='x')

        self.device_vars['p1_audio_out'] = tk.StringVar()
        p1_combo = ttk.Combobox(audio_frame, textvariable=self.device_vars['p1_audio_out'], state='readonly')
        p1_combo.pack(side='left', fill='x', expand=True)
        self.audio_output_combos['p1'] = p1_combo

        test_btn1 = ttk.Button(audio_frame, text="Test", width=8, command=lambda: self._test_audio('p1'))
        test_btn1.pack(side='left', padx=(5, 0))

        # Participant 2
        frame2 = tk.Frame(section)
        frame2.pack(fill='x')

        tk.Label(frame2, text="Participant 2:", font=('Arial', 9)).pack(anchor='w')
        audio_frame2 = tk.Frame(frame2)
        audio_frame2.pack(fill='x')

        self.device_vars['p2_audio_out'] = tk.StringVar()
        p2_combo = ttk.Combobox(audio_frame2, textvariable=self.device_vars['p2_audio_out'], state='readonly')
        p2_combo.pack(side='left', fill='x', expand=True)
        self.audio_output_combos['p2'] = p2_combo

        test_btn2 = ttk.Button(audio_frame2, text="Test", width=8, command=lambda: self._test_audio('p2'))
        test_btn2.pack(side='left', padx=(5, 0))

    def _create_audio_input_section(self, parent):
        """Create audio input configuration section (optional)"""
        section = ttk.LabelFrame(parent, text="Audio Input Configuration (Optional)", padding=10)
        section.pack(fill='x', pady=(0, 15))

        # Participant 1
        tk.Label(section, text="Participant 1:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p1_audio_in'] = tk.StringVar()
        p1_input_combo = ttk.Combobox(section, textvariable=self.device_vars['p1_audio_in'], state='readonly')
        p1_input_combo.pack(fill='x', pady=(0, 10))
        self.audio_input_combos['p1'] = p1_input_combo

        # Participant 2
        tk.Label(section, text="Participant 2:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p2_audio_in'] = tk.StringVar()
        p2_input_combo = ttk.Combobox(section, textvariable=self.device_vars['p2_audio_in'], state='readonly')
        p2_input_combo.pack(fill='x', pady=(0, 5))
        self.audio_input_combos['p2'] = p2_input_combo

    def _create_status_section(self, parent):
        """Create status display section"""
        section = ttk.LabelFrame(parent, text="Configuration Status", padding=10)
        section.pack(fill='x', pady=(0, 15))

        # Display status
        self.status_labels['displays'] = tk.Label(
            section,
            text="◯ Displays not configured",
            font=('Arial', 9),
            fg=self.theme_colors['status_inactive'],
            anchor='w'
        )
        self.status_labels['displays'].pack(fill='x', pady=(0, 5))

        # Audio status
        self.status_labels['audio'] = tk.Label(
            section,
            text="◯ Audio not configured",
            font=('Arial', 9),
            fg=self.theme_colors['status_inactive'],
            anchor='w'
        )
        self.status_labels['audio'].pack(fill='x')

    def _create_buttons(self, parent):
        """Create bottom action buttons"""
        button_frame = tk.Frame(parent, bg=self.theme_colors['bg'])
        button_frame.pack(fill='x', pady=(0, 0))

        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15
        )
        cancel_btn.pack(side='right', padx=(5, 0))

        # Save and Return button
        save_btn = ttk.Button(
            button_frame,
            text="Save and Return",
            command=self._on_save_and_return,
            width=20
        )
        save_btn.pack(side='right')

        # Rescan button
        rescan_btn = ttk.Button(
            button_frame,
            text="Rescan Devices",
            command=self._scan_devices,
            width=15
        )
        rescan_btn.pack(side='left')

    def _scan_devices(self):
        """Scan for available devices"""
        # Scan displays
        self.displays = self.scanner.scan_displays()

        # Scan audio
        audio_devices = self.scanner.scan_audio_devices()
        self.audio_output_devices = audio_devices.get('output', [])
        self.audio_input_devices = audio_devices.get('input', [])

        # Update combo boxes
        self._update_display_combos()
        self._update_audio_combos()

    def _update_display_combos(self):
        """Update display combo boxes with scanned displays"""
        display_options = [f"{d.index}: {d.name} ({d.width}x{d.height})" for d in self.displays]

        for combo in self.display_combos.values():
            combo['values'] = display_options

    def _update_audio_combos(self):
        """Update audio combo boxes with scanned devices"""
        # Handle both AudioDeviceInfo objects and dict format
        output_options = []
        for d in self.audio_output_devices:
            if hasattr(d, 'index'):
                output_options.append(f"{d.index}: {d.name}")
            else:
                output_options.append(f"{d['index']}: {d['name']}")

        input_options = []
        for d in self.audio_input_devices:
            if hasattr(d, 'index'):
                input_options.append(f"{d.index}: {d.name}")
            else:
                input_options.append(f"{d['index']}: {d['name']}")

        for combo in self.audio_output_combos.values():
            combo['values'] = output_options

        for combo in self.audio_input_combos.values():
            combo['values'] = input_options

    def _load_from_timeline(self):
        """Load existing configuration from timeline metadata"""
        # Load display configuration
        control_idx = self.timeline.metadata.get('control_monitor')
        if control_idx is not None:
            self._select_display_by_index('control', control_idx)

        p1_monitor_idx = self.timeline.metadata.get('participant_1_monitor')
        if p1_monitor_idx is not None:
            self._select_display_by_index('p1', p1_monitor_idx)

        p2_monitor_idx = self.timeline.metadata.get('participant_2_monitor')
        if p2_monitor_idx is not None:
            self._select_display_by_index('p2', p2_monitor_idx)

        # Load audio configuration
        p1_audio_idx = self.timeline.metadata.get('audio_device_1')
        if p1_audio_idx is not None:
            self._select_audio_by_index('p1', 'output', p1_audio_idx)

        p2_audio_idx = self.timeline.metadata.get('audio_device_2')
        if p2_audio_idx is not None:
            self._select_audio_by_index('p2', 'output', p2_audio_idx)

        # Update status
        self._update_status()

    def _select_display_by_index(self, participant: str, display_idx: int):
        """Helper to select a display in combobox by index"""
        for i, display in enumerate(self.displays):
            if display.index == display_idx:
                if participant == 'control':
                    self.display_combos['control'].current(i)
                elif participant == 'p1':
                    self.display_combos['p1'].current(i)
                elif participant == 'p2':
                    self.display_combos['p2'].current(i)
                self._on_display_selected(participant)
                break

    def _select_audio_by_index(self, participant: str, io_type: str, device_idx: int):
        """Helper to select an audio device in combobox by index"""
        devices = self.audio_output_devices if io_type == 'output' else self.audio_input_devices
        combos = self.audio_output_combos if io_type == 'output' else self.audio_input_combos

        for i, device in enumerate(devices):
            # Handle both AudioDeviceInfo objects and dict format
            dev_idx = device.index if hasattr(device, 'index') else device['index']
            if dev_idx == device_idx:
                combos[participant].current(i)
                break

    def _on_display_selected(self, participant: str):
        """Handle display selection"""
        self._update_status()

    def _test_audio(self, participant: str):
        """Test audio device"""
        selected = self.device_vars[f'{participant}_audio_out'].get()
        if not selected:
            messagebox.showwarning("No Device Selected", "Please select an audio device first")
            return

        device_idx = int(selected.split(':')[0])

        try:
            import sounddevice as sd
            import numpy as np

            # Generate 440 Hz tone
            duration = 1.0  # seconds
            sample_rate = 44100
            t = np.linspace(0, duration, int(sample_rate * duration))
            wave = 0.3 * np.sin(2 * np.pi * 440 * t)

            # Play through selected device
            sd.play(wave, sample_rate, device=device_idx)
            sd.wait()

            messagebox.showinfo(
                "Audio Test",
                f"Test tone played on device {device_idx}\nDid you hear a beep?"
            )

        except Exception as e:
            messagebox.showerror("Audio Test Failed", f"Failed to test audio:\n{str(e)}")

    def _update_status(self):
        """Update status labels based on current configuration"""
        # Check display configuration
        control = self.device_vars['control_monitor'].get()
        p1_display = self.device_vars['p1_monitor'].get()
        p2_display = self.device_vars['p2_monitor'].get()

        if control and p1_display and p2_display:
            self.status_labels['displays'].config(
                text="✓ All displays configured",
                fg=self.theme_colors['status_ready']
            )
        else:
            missing = []
            if not control:
                missing.append("Control")
            if not p1_display:
                missing.append("P1")
            if not p2_display:
                missing.append("P2")
            self.status_labels['displays'].config(
                text=f"⚠ Missing: {', '.join(missing)}",
                fg=self.theme_colors['status_warning']
            )

        # Check audio configuration
        p1_audio = self.device_vars['p1_audio_out'].get()
        p2_audio = self.device_vars['p2_audio_out'].get()

        if p1_audio and p2_audio:
            self.status_labels['audio'].config(
                text="✓ All audio devices configured",
                fg=self.theme_colors['status_ready']
            )
        else:
            missing = []
            if not p1_audio:
                missing.append("P1")
            if not p2_audio:
                missing.append("P2")
            self.status_labels['audio'].config(
                text=f"⚠ Missing: {', '.join(missing)}",
                fg=self.theme_colors['status_warning']
            )

    def _validate_configuration(self) -> tuple[bool, List[str]]:
        """Validate current configuration"""
        issues = []

        # Check displays
        control = self.device_vars['control_monitor'].get()
        p1_display = self.device_vars['p1_monitor'].get()
        p2_display = self.device_vars['p2_monitor'].get()

        if not control:
            issues.append("Control monitor not selected")
        if not p1_display:
            issues.append("Participant 1 monitor not selected")
        if not p2_display:
            issues.append("Participant 2 monitor not selected")

        # Check for P1/P2 conflict
        if p1_display and p2_display and p1_display == p2_display:
            issues.append("Participant monitors cannot be the same")

        # Check audio
        p1_audio = self.device_vars['p1_audio_out'].get()
        p2_audio = self.device_vars['p2_audio_out'].get()

        if not p1_audio:
            issues.append("Participant 1 audio device not selected")
        if not p2_audio:
            issues.append("Participant 2 audio device not selected")

        return (len(issues) == 0, issues)

    def _on_save_and_return(self):
        """Save configuration to timeline and close dialog"""
        # Validate
        valid, issues = self._validate_configuration()

        if not valid:
            issue_text = "Please fix the following issues:\n\n" + "\n".join(f"• {issue}" for issue in issues)
            messagebox.showwarning("Configuration Incomplete", issue_text)
            return

        # Extract device indices from combo selections
        control_monitor = int(self.device_vars['control_monitor'].get().split(':')[0])
        p1_monitor = int(self.device_vars['p1_monitor'].get().split(':')[0])
        p2_monitor = int(self.device_vars['p2_monitor'].get().split(':')[0])
        p1_audio = int(self.device_vars['p1_audio_out'].get().split(':')[0])
        p2_audio = int(self.device_vars['p2_audio_out'].get().split(':')[0])

        # Save to timeline metadata
        self.timeline.metadata['control_monitor'] = control_monitor
        self.timeline.metadata['participant_1_monitor'] = p1_monitor
        self.timeline.metadata['participant_2_monitor'] = p2_monitor
        self.timeline.metadata['audio_device_1'] = p1_audio
        self.timeline.metadata['audio_device_2'] = p2_audio

        # Mark result as successful
        self.result = True

        # Close dialog
        self.destroy()

    def _on_cancel(self):
        """Cancel and close dialog without saving"""
        self.result = False
        self.destroy()
