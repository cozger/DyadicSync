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

        # Keyboard identification state
        self._keyboard_info_p1 = None  # KeyboardDeviceInfo or None
        self._keyboard_info_p2 = None
        self._keyboard_identifier = None  # Active KeyboardIdentifier
        self._identifying_participant = None  # 'p1' or 'p2' during identification
        self._identify_poll_id = None  # tkinter after() ID for polling

        # Setup UI
        self._configure_styles()
        self._create_ui()
        self._disable_combobox_scroll()
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

    def _disable_combobox_scroll(self):
        """Disable mouse wheel changing combobox values (click-only selection)."""
        for combo in self.winfo_children_recursive_comboboxes():
            combo.bind('<MouseWheel>', lambda e: 'break')

    def winfo_children_recursive_comboboxes(self):
        """Find all Combobox widgets recursively."""
        result = []
        def _recurse(widget):
            for child in widget.winfo_children():
                if isinstance(child, ttk.Combobox):
                    result.append(child)
                _recurse(child)
        _recurse(self)
        return result

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
        self._create_keyboard_section(self.scrollable_content)
        self._create_status_section(self.scrollable_content)

        # Buttons at bottom (fixed, always visible)
        self._create_buttons(main_frame)

    def _create_display_section(self, parent):
        """Create display configuration section"""
        section = ttk.LabelFrame(parent, text="Display Configuration", padding=10)
        section.pack(fill='x', pady=(0, 15))

        # Control monitor
        tk.Label(section, text="Control Monitor (Experimenter):", font=('Arial', 9)).pack(anchor='w')
        control_frame = tk.Frame(section)
        control_frame.pack(fill='x', pady=(0, 10))

        self.device_vars['control_monitor'] = tk.StringVar()
        control_combo = ttk.Combobox(control_frame, textvariable=self.device_vars['control_monitor'], state='readonly')
        control_combo.pack(side='left', fill='x', expand=True)
        control_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('control'))
        self.display_combos['control'] = control_combo

        ttk.Button(control_frame, text="Test", width=8,
                   command=lambda: self._test_display('control')).pack(side='left', padx=(5, 0))

        # Participant 1
        tk.Label(section, text="Participant 1 Monitor:", font=('Arial', 9)).pack(anchor='w')
        p1_frame = tk.Frame(section)
        p1_frame.pack(fill='x', pady=(0, 10))

        self.device_vars['p1_monitor'] = tk.StringVar()
        p1_combo = ttk.Combobox(p1_frame, textvariable=self.device_vars['p1_monitor'], state='readonly')
        p1_combo.pack(side='left', fill='x', expand=True)
        p1_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('p1'))
        self.display_combos['p1'] = p1_combo

        ttk.Button(p1_frame, text="Test", width=8,
                   command=lambda: self._test_display('p1')).pack(side='left', padx=(5, 0))

        # Participant 2
        tk.Label(section, text="Participant 2 Monitor:", font=('Arial', 9)).pack(anchor='w')
        p2_frame = tk.Frame(section)
        p2_frame.pack(fill='x', pady=(0, 5))

        self.device_vars['p2_monitor'] = tk.StringVar()
        p2_combo = ttk.Combobox(p2_frame, textvariable=self.device_vars['p2_monitor'], state='readonly')
        p2_combo.pack(side='left', fill='x', expand=True)
        p2_combo.bind('<<ComboboxSelected>>', lambda e: self._on_display_selected('p2'))
        self.display_combos['p2'] = p2_combo

        ttk.Button(p2_frame, text="Test", width=8,
                   command=lambda: self._test_display('p2')).pack(side='left', padx=(5, 0))

        # Test All button
        test_all_frame = tk.Frame(section)
        test_all_frame.pack(fill='x', pady=(8, 0))
        ttk.Button(test_all_frame, text="Test All Displays", width=18,
                   command=self._test_all_displays).pack(anchor='e')

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

    def _create_keyboard_section(self, parent):
        """Create keyboard configuration section (optional)"""
        section = ttk.LabelFrame(parent, text="Keyboard Configuration (Optional)", padding=10)
        section.pack(fill='x', pady=(0, 15))

        hint_label = tk.Label(
            section,
            text="Identify each participant's keyboard so both can use the same keys (e.g., 1-7).",
            font=('Arial', 8),
            fg=self.theme_colors['status_inactive'],
            anchor='w'
        )
        hint_label.pack(fill='x', pady=(0, 10))

        # Participant 1
        p1_frame = tk.Frame(section)
        p1_frame.pack(fill='x', pady=(0, 8))

        tk.Label(p1_frame, text="Participant 1:", font=('Arial', 9)).pack(anchor='w')
        p1_row = tk.Frame(p1_frame)
        p1_row.pack(fill='x')

        self.device_vars['p1_keyboard'] = tk.StringVar(value="Not configured")
        self._p1_keyboard_label = tk.Label(
            p1_row, textvariable=self.device_vars['p1_keyboard'],
            font=('Arial', 9), anchor='w', width=50
        )
        self._p1_keyboard_label.pack(side='left', fill='x', expand=True)

        self._p1_identify_btn = ttk.Button(
            p1_row, text="Identify", width=10,
            command=lambda: self._start_keyboard_identify('p1')
        )
        self._p1_identify_btn.pack(side='left', padx=(5, 0))

        ttk.Button(
            p1_row, text="Clear", width=8,
            command=lambda: self._clear_keyboard('p1')
        ).pack(side='left', padx=(5, 0))

        # Participant 2
        p2_frame = tk.Frame(section)
        p2_frame.pack(fill='x', pady=(0, 5))

        tk.Label(p2_frame, text="Participant 2:", font=('Arial', 9)).pack(anchor='w')
        p2_row = tk.Frame(p2_frame)
        p2_row.pack(fill='x')

        self.device_vars['p2_keyboard'] = tk.StringVar(value="Not configured")
        self._p2_keyboard_label = tk.Label(
            p2_row, textvariable=self.device_vars['p2_keyboard'],
            font=('Arial', 9), anchor='w', width=50
        )
        self._p2_keyboard_label.pack(side='left', fill='x', expand=True)

        self._p2_identify_btn = ttk.Button(
            p2_row, text="Identify", width=10,
            command=lambda: self._start_keyboard_identify('p2')
        )
        self._p2_identify_btn.pack(side='left', padx=(5, 0))

        ttk.Button(
            p2_row, text="Clear", width=8,
            command=lambda: self._clear_keyboard('p2')
        ).pack(side='left', padx=(5, 0))

        # Intercept checkbox (requires Interception driver)
        intercept_frame = tk.Frame(section)
        intercept_frame.pack(fill='x', pady=(8, 0))

        # Check if Interception driver is available
        try:
            from core.input.interception_listener import _dll  # noqa: F401
            interception_available = True
        except (ImportError, OSError):
            interception_available = False

        self._intercept_var = tk.BooleanVar(
            value=self.timeline.metadata.get('intercept_keyboards', False) if interception_available else False
        )
        intercept_cb = tk.Checkbutton(
            intercept_frame,
            text="Isolate participant keyboards (block input from reaching other apps)",
            variable=self._intercept_var,
            font=('Arial', 9),
            state='normal' if interception_available else 'disabled',
        )
        intercept_cb.pack(anchor='w')

        if interception_available:
            hint_text = "Uses Interception driver to block participant keypresses from other apps."
            hint_color = self.theme_colors['status_inactive']
        else:
            hint_text = "Requires Interception driver (not installed). See docs/KEYBOARD_ISOLATION_SETUP.md"
            hint_color = self.theme_colors.get('status_warning', '#CC8800')

        intercept_hint = tk.Label(
            intercept_frame,
            text=hint_text,
            font=('Arial', 8),
            fg=hint_color,
            anchor='w',
        )
        intercept_hint.pack(anchor='w', padx=(20, 0))

    def _start_keyboard_identify(self, participant: str):
        """Start keyboard identification for a participant."""
        # Cancel any in-progress identification
        self._cancel_keyboard_identify()

        self._identifying_participant = participant

        # Update button text
        btn = self._p1_identify_btn if participant == 'p1' else self._p2_identify_btn
        var = self.device_vars[f'{participant}_keyboard']
        btn.configure(state='disabled')
        var.set(f"Press any key on {participant.upper()}'s keyboard...")

        # Start identifier
        try:
            from core.input.keyboard_identifier import KeyboardIdentifier
            self._keyboard_identifier = KeyboardIdentifier()
            self._keyboard_identifier.start_listening()

            # Poll for result via tkinter after() (non-blocking)
            self._poll_keyboard_identify()
        except Exception as e:
            var.set(f"Error: {e}")
            btn.configure(state='normal')
            self._identifying_participant = None

    def _poll_keyboard_identify(self):
        """Poll the keyboard identifier for a result (non-blocking)."""
        if not self._keyboard_identifier or not self._identifying_participant:
            return

        result = self._keyboard_identifier.poll_result()
        participant = self._identifying_participant

        if result:
            # Success - got a keypress
            self._keyboard_identifier.stop_listening()
            self._keyboard_identifier = None
            self._identifying_participant = None

            # Check for duplicate (same keyboard assigned to both)
            other = 'p2' if participant == 'p1' else 'p1'
            other_info = self._keyboard_info_p2 if participant == 'p1' else self._keyboard_info_p1
            if other_info and other_info.device_path.lower() == result.device_path.lower():
                self.device_vars[f'{participant}_keyboard'].set("Same as other participant - try again")
                btn = self._p1_identify_btn if participant == 'p1' else self._p2_identify_btn
                btn.configure(state='normal')
                self._update_status()
                return

            # Store result
            if participant == 'p1':
                self._keyboard_info_p1 = result
            else:
                self._keyboard_info_p2 = result

            self.device_vars[f'{participant}_keyboard'].set(result.device_name)
            btn = self._p1_identify_btn if participant == 'p1' else self._p2_identify_btn
            btn.configure(state='normal')
            self._update_status()
        else:
            # Not yet - schedule another poll (100ms)
            self._identify_poll_id = self.after(100, self._poll_keyboard_identify)

    def _cancel_keyboard_identify(self):
        """Cancel any in-progress keyboard identification."""
        if self._identify_poll_id:
            self.after_cancel(self._identify_poll_id)
            self._identify_poll_id = None

        if self._keyboard_identifier:
            self._keyboard_identifier.stop_listening()
            self._keyboard_identifier = None

        if self._identifying_participant:
            participant = self._identifying_participant
            btn = self._p1_identify_btn if participant == 'p1' else self._p2_identify_btn
            btn.configure(state='normal')
            # Restore label if no info was set
            info = self._keyboard_info_p1 if participant == 'p1' else self._keyboard_info_p2
            if not info:
                self.device_vars[f'{participant}_keyboard'].set("Not configured")
            self._identifying_participant = None

    def _clear_keyboard(self, participant: str):
        """Clear keyboard configuration for a participant."""
        self._cancel_keyboard_identify()

        if participant == 'p1':
            self._keyboard_info_p1 = None
        else:
            self._keyboard_info_p2 = None

        self.device_vars[f'{participant}_keyboard'].set("Not configured")
        self._update_status()

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
        self.status_labels['audio'].pack(fill='x', pady=(0, 5))

        # Keyboard status
        self.status_labels['keyboards'] = tk.Label(
            section,
            text="◯ Keyboards: Not configured (using separate key bindings)",
            font=('Arial', 9),
            fg=self.theme_colors['status_inactive'],
            anchor='w'
        )
        self.status_labels['keyboards'].pack(fill='x')

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

        # Load keyboard configuration
        p1_kb_path = self.timeline.metadata.get('keyboard_device_1_path')
        p1_kb_name = self.timeline.metadata.get('keyboard_device_1_name')
        if p1_kb_path:
            from core.input.keyboard_identifier import KeyboardDeviceInfo
            self._keyboard_info_p1 = KeyboardDeviceInfo(
                device_path=p1_kb_path,
                device_name=p1_kb_name or "Unknown Keyboard"
            )
            self.device_vars['p1_keyboard'].set(self._keyboard_info_p1.device_name)

        p2_kb_path = self.timeline.metadata.get('keyboard_device_2_path')
        p2_kb_name = self.timeline.metadata.get('keyboard_device_2_name')
        if p2_kb_path:
            from core.input.keyboard_identifier import KeyboardDeviceInfo
            self._keyboard_info_p2 = KeyboardDeviceInfo(
                device_path=p2_kb_path,
                device_name=p2_kb_name or "Unknown Keyboard"
            )
            self.device_vars['p2_keyboard'].set(self._keyboard_info_p2.device_name)

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

    def _test_display(self, role: str):
        """
        Flash a fullscreen colored overlay on the selected monitor
        so the user can identify which physical screen it is.
        """
        var_key = 'control_monitor' if role == 'control' else f'{role}_monitor'
        selected = self.device_vars[var_key].get()
        if not selected:
            messagebox.showwarning("No Display Selected",
                                   "Please select a display first.")
            return

        display_idx = int(selected.split(':')[0])
        display_info = None
        for d in self.displays:
            if d.index == display_idx:
                display_info = d
                break
        if not display_info:
            return

        role_config = {
            'control': {'label': 'CONTROL\nMONITOR', 'sublabel': 'Experimenter', 'color': '#1565C0'},
            'p1':      {'label': 'PARTICIPANT 1', 'sublabel': 'Left Display', 'color': '#2E7D32'},
            'p2':      {'label': 'PARTICIPANT 2', 'sublabel': 'Right Display', 'color': '#E65100'},
        }
        config = role_config[role]
        self._show_display_test_window(display_info, config)

    def _test_all_displays(self):
        """Flash test overlays on all configured displays simultaneously."""
        roles = [
            ('control', 'control_monitor', 'CONTROL\nMONITOR', 'Experimenter', '#1565C0'),
            ('p1', 'p1_monitor', 'PARTICIPANT 1', 'Left Display', '#2E7D32'),
            ('p2', 'p2_monitor', 'PARTICIPANT 2', 'Right Display', '#E65100'),
        ]

        any_shown = False
        for role, var_key, label, sublabel, color in roles:
            selected = self.device_vars[var_key].get()
            if not selected:
                continue

            display_idx = int(selected.split(':')[0])
            display_info = None
            for d in self.displays:
                if d.index == display_idx:
                    display_info = d
                    break
            if not display_info:
                continue

            config = {'label': label, 'sublabel': sublabel, 'color': color}
            self._show_display_test_window(display_info, config)
            any_shown = True

        if not any_shown:
            messagebox.showwarning("No Displays Configured",
                                   "Please select at least one display first.")

    def _show_display_test_window(self, display_info: 'DisplayInfo', config: dict):
        """
        Create a temporary fullscreen overlay on the given display.
        Auto-closes after 3 seconds, or on click/keypress.
        """
        color = config['color']

        test_win = tk.Toplevel(self)
        test_win.overrideredirect(True)
        test_win.geometry(
            f"{display_info.width}x{display_info.height}"
            f"+{display_info.x}+{display_info.y}"
        )
        test_win.configure(bg=color)
        test_win.attributes('-topmost', True)

        # Role label
        tk.Label(
            test_win, text=config['label'],
            font=('Arial', 80, 'bold'),
            bg=color, fg='white'
        ).place(relx=0.5, rely=0.35, anchor='center')

        # Sub-label
        tk.Label(
            test_win, text=config['sublabel'],
            font=('Arial', 32),
            bg=color, fg='#d0d0d0'
        ).place(relx=0.5, rely=0.52, anchor='center')

        # Display info
        tk.Label(
            test_win,
            text=f"Display {display_info.index + 1}  —  "
                 f"{display_info.width} x {display_info.height}",
            font=('Arial', 20),
            bg=color, fg='#b0b0b0'
        ).place(relx=0.5, rely=0.62, anchor='center')

        # Close hint
        tk.Label(
            test_win,
            text="Click anywhere or wait 3 seconds to close",
            font=('Arial', 14),
            bg=color, fg='#909090'
        ).place(relx=0.5, rely=0.78, anchor='center')

        # Close handlers
        def close_window(event=None):
            if test_win.winfo_exists():
                test_win.destroy()

        test_win.bind('<Button-1>', close_window)
        test_win.bind('<Key>', close_window)
        test_win.focus_set()
        test_win.after(3000, close_window)

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

        # Check keyboard configuration
        has_p1_kb = self._keyboard_info_p1 is not None
        has_p2_kb = self._keyboard_info_p2 is not None

        if has_p1_kb and has_p2_kb:
            self.status_labels['keyboards'].config(
                text="✓ Both keyboards identified (unified key mode enabled)",
                fg=self.theme_colors['status_ready']
            )
        elif has_p1_kb or has_p2_kb:
            missing_kb = "P2" if has_p1_kb else "P1"
            self.status_labels['keyboards'].config(
                text=f"⚠ Keyboards: Only {('P1' if has_p1_kb else 'P2')} identified - {missing_kb} also required",
                fg=self.theme_colors['status_warning']
            )
        else:
            self.status_labels['keyboards'].config(
                text="◯ Keyboards: Not configured (using separate key bindings)",
                fg=self.theme_colors['status_inactive']
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

        # Keyboard: both or neither (warn, don't block)
        has_p1_kb = self._keyboard_info_p1 is not None
        has_p2_kb = self._keyboard_info_p2 is not None
        if has_p1_kb != has_p2_kb:
            issues.append("Both keyboards must be identified, or neither (one is configured, one is not)")

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

        # Save keyboard configuration (optional)
        if self._keyboard_info_p1:
            self.timeline.metadata['keyboard_device_1_path'] = self._keyboard_info_p1.device_path
            self.timeline.metadata['keyboard_device_1_name'] = self._keyboard_info_p1.device_name
        else:
            self.timeline.metadata.pop('keyboard_device_1_path', None)
            self.timeline.metadata.pop('keyboard_device_1_name', None)

        if self._keyboard_info_p2:
            self.timeline.metadata['keyboard_device_2_path'] = self._keyboard_info_p2.device_path
            self.timeline.metadata['keyboard_device_2_name'] = self._keyboard_info_p2.device_name
        else:
            self.timeline.metadata.pop('keyboard_device_2_path', None)
            self.timeline.metadata.pop('keyboard_device_2_name', None)

        # Save keyboard intercept setting
        self.timeline.metadata['intercept_keyboards'] = self._intercept_var.get()

        # Mark result as successful
        self.result = True

        # Cancel any in-progress identification before closing
        self._cancel_keyboard_identify()

        # Close dialog
        self.destroy()

    def _on_cancel(self):
        """Cancel and close dialog without saving"""
        self._cancel_keyboard_identify()
        self.result = False
        self.destroy()
