"""
Device Manager GUI
A graphical interface for configuring displays and audio devices for DyadicSync experiments.
Follows the YouQuantiPy visual style and design patterns.

Author: DyadicSync Development Team
Date: 2025-11-15
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import sys
from pathlib import Path
from typing import Optional, Dict, List
import threading

# Add core to path
sys.path.insert(0, str(Path(__file__).parent))

from core.device_scanner import DeviceScanner, DisplayInfo, AudioDeviceInfo
from core.device_config import DeviceConfigHandler


class DeviceManagerGUI(tk.Tk):
    """
    Main GUI application for device management.
    Follows YQP design patterns: 3-column layout, Azure theme, state-based colors.
    """

    def __init__(self):
        super().__init__()

        # Window configuration
        self.title("DyadicSync - Device Manager")
        self.geometry("1400x800")
        self.minsize(1000, 600)

        # Initialize components
        self.scanner = DeviceScanner()
        self.config = DeviceConfigHandler()

        # Theme colors
        self.current_theme = self.config.get('gui.theme', 'dark')
        self.theme_colors = self._get_theme_colors()

        # State variables
        self.left_panel_collapsed = self.config.get('gui.left_panel_collapsed', False)
        self.right_panel_collapsed = self.config.get('gui.right_panel_collapsed', False)

        # Device data
        self.displays: List[DisplayInfo] = []
        self.audio_output_devices: List[AudioDeviceInfo] = []
        self.audio_input_devices: List[AudioDeviceInfo] = []

        # Widget references
        self.status_labels: Dict[str, tk.Label] = {}
        self.device_vars: Dict[str, tk.StringVar] = {}

        # Setup UI
        self._configure_grid()
        self._create_panels()
        self._create_widgets()
        self._scan_devices()
        self._load_current_config()

        # Configure window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _get_theme_colors(self) -> Dict[str, str]:
        """Get color palette based on current theme"""
        if self.current_theme == 'dark':
            return {
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
        else:  # light theme
            return {
                'bg': '#f5f5f5',
                'fg': '#000000',
                'panel_bg': '#ffffff',
                'button_bg': '#e0e0e0',
                'button_fg': '#000000',
                'canvas_bg': '#ffffff',
                'entry_bg': '#ffffff',
                'entry_fg': '#000000',
                'status_ready': '#00aa44',
                'status_warning': '#ff8800',
                'status_error': '#dd0000',
                'status_inactive': '#999999',
                'accent': '#0088cc',
            }

    def _configure_grid(self):
        """Configure root grid layout (3-column design)"""
        self.configure(bg=self.theme_colors['bg'])

        # Column configuration
        self.grid_columnconfigure(0, weight=0, minsize=250)  # Left panel (control)
        self.grid_columnconfigure(1, weight=1)                # Center (monitors)
        self.grid_columnconfigure(2, weight=0, minsize=300)  # Right panel (status)

        # Row configuration
        self.grid_rowconfigure(0, weight=1)

    def _create_panels(self):
        """Create the three main panels"""
        # Left panel - Device selection controls
        self.left_panel = ttk.Frame(self, padding=10)
        self.left_panel.grid(row=0, column=0, sticky='nsew', padx=5, pady=5)

        # Center panel - Monitor previews
        self.center_panel = ttk.Frame(self, padding=10)
        self.center_panel.grid(row=0, column=1, sticky='nsew', padx=5, pady=5)

        # Right panel - Status and validation
        self.right_panel = ttk.Frame(self, padding=10)
        self.right_panel.grid(row=0, column=2, sticky='nsew', padx=5, pady=5)

    def _create_widgets(self):
        """Create all widgets"""
        self._create_left_panel_widgets()
        self._create_center_panel_widgets()
        self._create_right_panel_widgets()

    def _create_left_panel_widgets(self):
        """Create control panel widgets"""
        # Title
        title = tk.Label(
            self.left_panel,
            text="Device Configuration",
            font=('Arial', 14, 'bold'),
            bg=self.theme_colors['panel_bg'],
            fg=self.theme_colors['fg']
        )
        title.pack(anchor='w', pady=(0, 20))

        # Refresh button
        refresh_btn = ttk.Button(
            self.left_panel,
            text="⟳ Refresh Devices",
            command=self._scan_devices,
            width=25
        )
        refresh_btn.pack(anchor='w', pady=(0, 10))

        # Theme toggle button
        theme_text = "☀ Light Mode" if self.current_theme == 'dark' else "☾ Dark Mode"
        theme_btn = ttk.Button(
            self.left_panel,
            text=theme_text,
            command=self._toggle_theme,
            width=25
        )
        theme_btn.pack(anchor='w', pady=(0, 20))

        # Display selection section
        self._create_display_section()

        # Audio output section
        self._create_audio_output_section()

        # Audio input section
        self._create_audio_input_section()

        # Experiment settings section
        self._create_experiment_section()

        # Action buttons
        self._create_action_buttons()

    def _create_display_section(self):
        """Create display selection section"""
        section = ttk.LabelFrame(self.left_panel, text="Display Configuration", padding=10)
        section.pack(fill='x', pady=(10, 0))

        # Control monitor
        tk.Label(section, text="Control Monitor:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['control_monitor'] = tk.StringVar()
        control_combo = ttk.Combobox(
            section,
            textvariable=self.device_vars['control_monitor'],
            state='readonly',
            width=35
        )
        control_combo.pack(anchor='w', pady=(0, 10))
        control_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('control'))

        # Participant 1 monitor
        tk.Label(section, text="Participant 1 Monitor:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p1_monitor'] = tk.StringVar()
        p1_combo = ttk.Combobox(
            section,
            textvariable=self.device_vars['p1_monitor'],
            state='readonly',
            width=35
        )
        p1_combo.pack(anchor='w', pady=(0, 10))
        p1_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('p1'))

        # Participant 2 monitor
        tk.Label(section, text="Participant 2 Monitor:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p2_monitor'] = tk.StringVar()
        p2_combo = ttk.Combobox(
            section,
            textvariable=self.device_vars['p2_monitor'],
            state='readonly',
            width=35
        )
        p2_combo.pack(anchor='w', pady=(0, 10))
        p2_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('p2'))

        # Store combobox references
        self.display_combos = {
            'control': control_combo,
            'p1': p1_combo,
            'p2': p2_combo
        }

    def _create_audio_output_section(self):
        """Create audio output device section"""
        section = ttk.LabelFrame(self.left_panel, text="Audio Output (Speakers/Headphones)", padding=10)
        section.pack(fill='x', pady=(10, 0))

        # Participant 1 audio output
        tk.Label(section, text="Participant 1:", font=('Arial', 9)).pack(anchor='w')
        p1_frame = tk.Frame(section)
        p1_frame.pack(fill='x', pady=(0, 10))

        self.device_vars['p1_audio_out'] = tk.StringVar()
        p1_audio_combo = ttk.Combobox(
            p1_frame,
            textvariable=self.device_vars['p1_audio_out'],
            state='readonly',
            width=28
        )
        p1_audio_combo.pack(side='left', fill='x', expand=True)

        test_btn_p1 = ttk.Button(
            p1_frame,
            text="Test",
            command=lambda: self._test_audio_output('p1'),
            width=6
        )
        test_btn_p1.pack(side='left', padx=(5, 0))

        # Participant 2 audio output
        tk.Label(section, text="Participant 2:", font=('Arial', 9)).pack(anchor='w')
        p2_frame = tk.Frame(section)
        p2_frame.pack(fill='x', pady=(0, 5))

        self.device_vars['p2_audio_out'] = tk.StringVar()
        p2_audio_combo = ttk.Combobox(
            p2_frame,
            textvariable=self.device_vars['p2_audio_out'],
            state='readonly',
            width=28
        )
        p2_audio_combo.pack(side='left', fill='x', expand=True)

        test_btn_p2 = ttk.Button(
            p2_frame,
            text="Test",
            command=lambda: self._test_audio_output('p2'),
            width=6
        )
        test_btn_p2.pack(side='left', padx=(5, 0))

        # Store combobox references
        self.audio_output_combos = {
            'p1': p1_audio_combo,
            'p2': p2_audio_combo
        }

    def _create_audio_input_section(self):
        """Create audio input device section (optional, for future use)"""
        section = ttk.LabelFrame(self.left_panel, text="Audio Input (Optional)", padding=10)
        section.pack(fill='x', pady=(10, 0))

        # Participant 1 audio input
        tk.Label(section, text="Participant 1:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p1_audio_in'] = tk.StringVar()
        p1_input_combo = ttk.Combobox(
            section,
            textvariable=self.device_vars['p1_audio_in'],
            state='readonly',
            width=35
        )
        p1_input_combo.pack(anchor='w', pady=(0, 10))

        # Participant 2 audio input
        tk.Label(section, text="Participant 2:", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['p2_audio_in'] = tk.StringVar()
        p2_input_combo = ttk.Combobox(
            section,
            textvariable=self.device_vars['p2_audio_in'],
            state='readonly',
            width=35
        )
        p2_input_combo.pack(anchor='w', pady=(0, 5))

        # Store combobox references
        self.audio_input_combos = {
            'p1': p1_input_combo,
            'p2': p2_input_combo
        }

    def _create_experiment_section(self):
        """Create experiment settings section"""
        section = ttk.LabelFrame(self.left_panel, text="Experiment Settings", padding=10)
        section.pack(fill='x', pady=(10, 0))

        # Baseline length
        tk.Label(section, text="Baseline Length (seconds):", font=('Arial', 9)).pack(anchor='w')
        self.device_vars['baseline_length'] = tk.StringVar(value="240")
        baseline_entry = ttk.Entry(section, textvariable=self.device_vars['baseline_length'], width=10)
        baseline_entry.pack(anchor='w', pady=(0, 10))

    def _create_action_buttons(self):
        """Create action buttons at bottom of left panel"""
        button_frame = tk.Frame(self.left_panel)
        button_frame.pack(fill='x', pady=(20, 0))

        # Save configuration
        save_btn = ttk.Button(
            button_frame,
            text="Save Configuration",
            command=self._save_configuration,
            width=25
        )
        save_btn.pack(anchor='w', pady=(0, 5))

        # Validate configuration
        validate_btn = ttk.Button(
            button_frame,
            text="Validate Configuration",
            command=self._validate_configuration,
            width=25
        )
        validate_btn.pack(anchor='w', pady=(0, 5))

        # Launch experiment
        launch_btn = ttk.Button(
            button_frame,
            text="Launch Experiment",
            command=self._launch_experiment,
            width=25
        )
        launch_btn.pack(anchor='w', pady=(0, 5))

    def _create_center_panel_widgets(self):
        """Create monitor preview widgets in center panel"""
        title = tk.Label(
            self.center_panel,
            text="Monitor Configuration Preview",
            font=('Arial', 12, 'bold'),
            bg=self.theme_colors['panel_bg'],
            fg=self.theme_colors['fg']
        )
        title.pack(anchor='w', pady=(0, 10))

        # Create canvas for monitor visualization
        self.monitor_canvas = tk.Canvas(
            self.center_panel,
            bg=self.theme_colors['canvas_bg'],
            highlightthickness=1,
            highlightbackground=self.theme_colors['status_inactive']
        )
        self.monitor_canvas.pack(fill='both', expand=True)

        # Instructions
        instructions = tk.Label(
            self.center_panel,
            text="Select displays from the left panel to configure your multi-monitor setup.\n"
                 "Control monitor is for experimenter, participant monitors for video playback.",
            font=('Arial', 9),
            bg=self.theme_colors['panel_bg'],
            fg=self.theme_colors['status_inactive'],
            justify='left'
        )
        instructions.pack(anchor='w', pady=(10, 0))

    def _create_right_panel_widgets(self):
        """Create status and validation widgets in right panel"""
        title = tk.Label(
            self.right_panel,
            text="System Status",
            font=('Arial', 12, 'bold'),
            bg=self.theme_colors['panel_bg'],
            fg=self.theme_colors['fg']
        )
        title.pack(anchor='w', pady=(0, 20))

        # Display status section
        display_section = ttk.LabelFrame(self.right_panel, text="Display Status", padding=10)
        display_section.pack(fill='x', pady=(0, 10))

        self.status_labels['displays_found'] = self._create_status_label(
            display_section, "Displays Found:", "0"
        )
        self.status_labels['control_display'] = self._create_status_label(
            display_section, "Control Monitor:", "Not configured"
        )
        self.status_labels['p1_display'] = self._create_status_label(
            display_section, "P1 Monitor:", "Not configured"
        )
        self.status_labels['p2_display'] = self._create_status_label(
            display_section, "P2 Monitor:", "Not configured"
        )

        # Audio status section
        audio_section = ttk.LabelFrame(self.right_panel, text="Audio Status", padding=10)
        audio_section.pack(fill='x', pady=(0, 10))

        self.status_labels['audio_out_found'] = self._create_status_label(
            audio_section, "Output Devices:", "0"
        )
        self.status_labels['audio_in_found'] = self._create_status_label(
            audio_section, "Input Devices:", "0"
        )
        self.status_labels['p1_audio'] = self._create_status_label(
            audio_section, "P1 Audio Out:", "Not configured"
        )
        self.status_labels['p2_audio'] = self._create_status_label(
            audio_section, "P2 Audio Out:", "Not configured"
        )

        # Validation status section
        validation_section = ttk.LabelFrame(self.right_panel, text="Configuration Status", padding=10)
        validation_section.pack(fill='x', pady=(0, 10))

        self.status_labels['validation'] = tk.Label(
            validation_section,
            text="Not validated",
            font=('Arial', 10),
            fg=self.theme_colors['status_inactive'],
            anchor='w',
            justify='left',
            wraplength=250
        )
        self.status_labels['validation'].pack(fill='x')

    def _create_status_label(self, parent, label_text: str, value_text: str) -> tk.Label:
        """Helper to create a status label pair"""
        frame = tk.Frame(parent)
        frame.pack(fill='x', pady=2)

        tk.Label(
            frame,
            text=label_text,
            font=('Arial', 9),
            anchor='w'
        ).pack(side='left')

        value_label = tk.Label(
            frame,
            text=value_text,
            font=('Arial', 9, 'bold'),
            fg=self.theme_colors['status_inactive'],
            anchor='e'
        )
        value_label.pack(side='right')

        return value_label

    # Event handlers and functionality methods will continue...

    def _scan_devices(self):
        """Scan all available devices and update UI"""
        # Scan displays
        self.displays = self.scanner.scan_displays(force_refresh=True)
        display_names = [f"{d.index}: {d.name} ({d.width}x{d.height})" for d in self.displays]

        # Update display comboboxes
        for combo in self.display_combos.values():
            combo['values'] = display_names

        # Scan audio devices
        audio_devices = self.scanner.scan_audio_devices(force_refresh=True)
        self.audio_output_devices = audio_devices['output']
        self.audio_input_devices = audio_devices['input']

        output_names = [f"{d.index}: {d.name}" for d in self.audio_output_devices]
        input_names = [f"{d.index}: {d.name}" for d in self.audio_input_devices]

        # Update audio output comboboxes
        for combo in self.audio_output_combos.values():
            combo['values'] = output_names

        # Update audio input comboboxes
        for combo in self.audio_input_combos.values():
            combo['values'] = input_names

        # Update status labels
        self.status_labels['displays_found'].config(
            text=str(len(self.displays)),
            fg=self.theme_colors['status_ready'] if len(self.displays) >= 3 else self.theme_colors['status_warning']
        )
        self.status_labels['audio_out_found'].config(
            text=str(len(self.audio_output_devices)),
            fg=self.theme_colors['status_ready'] if len(self.audio_output_devices) >= 2 else self.theme_colors['status_warning']
        )
        self.status_labels['audio_in_found'].config(text=str(len(self.audio_input_devices)))

        # Redraw monitor visualization
        self._draw_monitor_layout()

    def _load_current_config(self):
        """Load current configuration values into UI"""
        # Load displays
        control_idx = self.config.get('displays.control_monitor')
        p1_idx = self.config.get('displays.participant_1_monitor')
        p2_idx = self.config.get('displays.participant_2_monitor')

        if control_idx is not None:
            self._select_display_by_index('control', control_idx)
        if p1_idx is not None:
            self._select_display_by_index('p1', p1_idx)
        if p2_idx is not None:
            self._select_display_by_index('p2', p2_idx)

        # Load audio output
        p1_audio_idx = self.config.get('audio.participant_1_output')
        p2_audio_idx = self.config.get('audio.participant_2_output')

        if p1_audio_idx is not None:
            self._select_audio_by_index('p1', 'output', p1_audio_idx)
        if p2_audio_idx is not None:
            self._select_audio_by_index('p2', 'output', p2_audio_idx)

        # Load audio input
        p1_input_idx = self.config.get('audio.participant_1_input')
        p2_input_idx = self.config.get('audio.participant_2_input')

        if p1_input_idx is not None:
            self._select_audio_by_index('p1', 'input', p1_input_idx)
        if p2_input_idx is not None:
            self._select_audio_by_index('p2', 'input', p2_input_idx)

        # Load experiment settings
        baseline_length = self.config.get('experiment.baseline_length', 240)
        self.device_vars['baseline_length'].set(str(baseline_length))

    def _select_display_by_index(self, participant: str, display_idx: int):
        """Helper to select a display in combobox by index"""
        for i, display in enumerate(self.displays):
            if display.index == display_idx:
                self.display_combos[participant].current(i)
                self._on_display_selected(participant)
                break

    def _select_audio_by_index(self, participant: str, device_type: str, device_idx: int):
        """Helper to select an audio device in combobox by index"""
        if device_type == 'output':
            devices = self.audio_output_devices
            combos = self.audio_output_combos
        else:
            devices = self.audio_input_devices
            combos = self.audio_input_combos

        for i, device in enumerate(devices):
            if device.index == device_idx:
                combos[participant].current(i)
                break

    def _on_display_selected(self, participant: str):
        """Handle display selection"""
        selected = self.device_vars[f'{participant}_monitor'].get()
        if not selected:
            return

        # Extract index from selection string
        display_idx = int(selected.split(':')[0])

        # Update status label
        status_key = f'{participant}_display' if participant != 'control' else 'control_display'
        self.status_labels[status_key].config(
            text=f"Display {display_idx}",
            fg=self.theme_colors['status_ready']
        )

        # Redraw monitor layout
        self._draw_monitor_layout()

    def _test_audio_output(self, participant: str):
        """Test audio output device"""
        selected = self.device_vars[f'{participant}_audio_out'].get()
        if not selected:
            messagebox.showwarning("No Device", f"Please select an audio device for {participant.upper()} first")
            return

        device_idx = int(selected.split(':')[0])

        # Show testing message
        self.status_labels[f'{participant}_audio'].config(
            text="Testing...",
            fg=self.theme_colors['status_warning']
        )
        self.update()

        # Test in thread to avoid blocking UI
        def test_thread():
            success, message = self.scanner.test_audio_output(device_idx, duration=1.0, frequency=440.0)

            # Update UI from main thread
            self.after(0, lambda: self._update_audio_test_result(participant, success, message))

        threading.Thread(target=test_thread, daemon=True).start()

    def _update_audio_test_result(self, participant: str, success: bool, message: str):
        """Update UI after audio test"""
        if success:
            self.status_labels[f'{participant}_audio'].config(
                text="Tested OK",
                fg=self.theme_colors['status_ready']
            )
            messagebox.showinfo("Audio Test", message)
        else:
            self.status_labels[f'{participant}_audio'].config(
                text="Test Failed",
                fg=self.theme_colors['status_error']
            )
            messagebox.showerror("Audio Test Failed", message)

    def _save_configuration(self):
        """Save current configuration"""
        try:
            # Collect all settings
            updates = {}

            # Displays
            for key, combo_key in [('control_monitor', 'control_monitor'),
                                  ('participant_1_monitor', 'p1_monitor'),
                                  ('participant_2_monitor', 'p2_monitor')]:
                selected = self.device_vars[combo_key].get()
                if selected:
                    display_idx = int(selected.split(':')[0])
                    updates[f'displays.{key}'] = display_idx

            # Audio output
            for key, combo_key in [('participant_1_output', 'p1_audio_out'),
                                  ('participant_2_output', 'p2_audio_out')]:
                selected = self.device_vars[combo_key].get()
                if selected:
                    device_idx = int(selected.split(':')[0])
                    updates[f'audio.{key}'] = device_idx

            # Audio input (optional)
            for key, combo_key in [('participant_1_input', 'p1_audio_in'),
                                  ('participant_2_input', 'p2_audio_in')]:
                selected = self.device_vars[combo_key].get()
                if selected:
                    device_idx = int(selected.split(':')[0])
                    updates[f'audio.{key}'] = device_idx

            # Experiment settings
            try:
                baseline_length = int(self.device_vars['baseline_length'].get())
                updates['experiment.baseline_length'] = baseline_length
            except ValueError:
                pass

            # Save theme
            updates['gui.theme'] = self.current_theme

            # Apply updates
            self.config.update(updates, save=True)

            messagebox.showinfo("Success", "Configuration saved successfully")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to save configuration: {str(e)}")

    def _validate_configuration(self):
        """Validate current configuration"""
        # First save current settings
        self._save_configuration()

        # Then validate
        ready, issues = self.config.is_ready_for_experiment()

        if ready:
            self.status_labels['validation'].config(
                text="✓ Configuration is valid and ready for experiment",
                fg=self.theme_colors['status_ready']
            )
            messagebox.showinfo("Validation", "Configuration is valid!\n\nReady to run experiment.")
        else:
            issue_text = "Configuration issues:\n\n" + "\n".join(f"• {issue}" for issue in issues)
            self.status_labels['validation'].config(
                text="✗ " + "\n".join(issues),
                fg=self.theme_colors['status_error']
            )
            messagebox.showwarning("Validation Failed", issue_text)

    def _launch_experiment(self):
        """Launch the main experiment"""
        # Validate first
        ready, issues = self.config.is_ready_for_experiment()

        if not ready:
            issue_text = "Cannot launch experiment. Issues:\n\n" + "\n".join(f"• {issue}" for issue in issues)
            messagebox.showerror("Cannot Launch", issue_text)
            return

        # Ask for confirmation
        if not messagebox.askyesno("Launch Experiment",
                                  "Launch the DyadicSync experiment?\n\n"
                                  "Make sure all equipment is properly connected."):
            return

        # Close this window and launch experiment
        messagebox.showinfo("Launch", "Experiment GUI will launch.\n\n"
                                     "Note: Full experiment integration coming soon.\n"
                                     "For now, run WithBaseline.py manually with configured settings.")

    def _toggle_theme(self):
        """Toggle between light and dark theme"""
        self.current_theme = 'light' if self.current_theme == 'dark' else 'dark'
        self.theme_colors = self._get_theme_colors()

        # Update theme in config
        self.config.set('gui.theme', self.current_theme, save=True)

        # Recreate UI with new theme
        messagebox.showinfo("Theme Changed",
                          "Theme will be applied on next launch.\n\n"
                          "For immediate effect, please restart the application.")

    def _draw_monitor_layout(self):
        """Draw visualization of monitor layout"""
        self.monitor_canvas.delete('all')

        if not self.displays:
            return

        # Get canvas dimensions
        canvas_width = self.monitor_canvas.winfo_width()
        canvas_height = self.monitor_canvas.winfo_height()

        if canvas_width <= 1:  # Canvas not yet rendered
            canvas_width = 600
            canvas_height = 400

        # Calculate scale to fit all monitors
        all_x = [d.x for d in self.displays] + [d.x + d.width for d in self.displays]
        all_y = [d.y for d in self.displays] + [d.y + d.height for d in self.displays]

        min_x, max_x = min(all_x), max(all_x)
        min_y, max_y = min(all_y), max(all_y)

        total_width = max_x - min_x
        total_height = max_y - min_y

        if total_width == 0 or total_height == 0:
            return

        # Scale with padding
        padding = 40
        scale_x = (canvas_width - 2 * padding) / total_width
        scale_y = (canvas_height - 2 * padding) / total_height
        scale = min(scale_x, scale_y)

        # Draw each monitor
        for display in self.displays:
            x1 = (display.x - min_x) * scale + padding
            y1 = (display.y - min_y) * scale + padding
            x2 = x1 + display.width * scale
            y2 = y1 + display.height * scale

            # Determine color based on assignment
            fill_color = self.theme_colors['canvas_bg']
            outline_color = self.theme_colors['status_inactive']
            label_color = self.theme_colors['fg']

            # Check if this display is assigned
            control_idx = self._get_selected_display_index('control')
            p1_idx = self._get_selected_display_index('p1')
            p2_idx = self._get_selected_display_index('p2')

            assignment = None
            if display.index == control_idx:
                outline_color = self.theme_colors['accent']
                assignment = "Control"
            if display.index == p1_idx:
                outline_color = self.theme_colors['status_ready']
                assignment = "P1"
            if display.index == p2_idx:
                outline_color = '#ff4466'  # Red for P2
                assignment = "P2"

            # Draw monitor rectangle
            self.monitor_canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=outline_color,
                width=3,
                fill=fill_color
            )

            # Draw label
            center_x = (x1 + x2) / 2
            center_y = (y1 + y2) / 2

            label_text = f"Display {display.index}\n{display.width}x{display.height}"
            if assignment:
                label_text += f"\n({assignment})"

            self.monitor_canvas.create_text(
                center_x, center_y,
                text=label_text,
                fill=label_color,
                font=('Arial', 9, 'bold'),
                justify='center'
            )

    def _get_selected_display_index(self, participant: str) -> Optional[int]:
        """Get currently selected display index for a participant"""
        selected = self.device_vars[f'{participant}_monitor'].get()
        if selected:
            return int(selected.split(':')[0])
        return None

    def _on_closing(self):
        """Handle window close"""
        self.destroy()


def main():
    """Main entry point"""
    app = DeviceManagerGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
