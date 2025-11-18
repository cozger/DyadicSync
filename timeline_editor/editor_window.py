"""
Main timeline editor window with split layout - Procedural Version.

This version works directly with Timeline/Block/Procedure/Phase objects
instead of the legacy ExperimentConfig format.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import sys
import time
import json

sys.path.append(str(Path(__file__).parent.parent))

from core.execution.timeline import Timeline
from core.execution.block import Block
from timeline_editor.timeline_canvas import TimelineCanvas
from timeline_editor.property_panel import PropertyPanel
from gui.preview_panel import PreviewPanel
from timeline_editor.dialogs.device_setup_dialog import DeviceSetupDialog


def create_default_timeline() -> Timeline:
    """
    Create a default timeline with welcome and baseline blocks.

    Returns:
        Timeline with default blocks
    """
    from core.execution.procedure import Procedure
    from core.execution.phases.instruction_phase import InstructionPhase
    from core.execution.phases.baseline_phase import BaselinePhase

    timeline = Timeline(name="New Experiment")

    # Welcome block (renamed to "Text" as default)
    welcome_block = Block(name="Text", block_type='simple')
    welcome_proc = Procedure("Welcome Screen")
    welcome_proc.add_phase(InstructionPhase(
        text="Welcome to the experiment!\n\nPress SPACE to continue.",
        wait_for_key=True,
        continue_key='space'
    ))
    welcome_block.procedure = welcome_proc
    timeline.add_block(welcome_block)

    # Baseline block
    baseline_block = Block(name="Baseline", block_type='simple')
    baseline_proc = Procedure("Baseline Recording")
    baseline_proc.add_phase(BaselinePhase(duration=240))
    baseline_block.procedure = baseline_proc
    timeline.add_block(baseline_block)

    return timeline


class EditorWindow(tk.Tk):
    """
    Main timeline editor window - Procedural Mode.

    Works directly with Timeline objects (Block/Procedure/Phase hierarchy).

    Layout:
    - Top half (60%): Timeline canvas (left 70%) + Property panel (right 30%)
    - Bottom half (40%): Dual monitor previews
    """

    def __init__(self, timeline: Timeline = None):
        """
        Initialize the editor window.

        Args:
            timeline: Timeline to edit (creates default if None)
        """
        print(f"[DEBUG {time.time():.3f}] EditorWindow.__init__ START")
        super().__init__()

        print(f"[DEBUG {time.time():.3f}] Creating timeline...")
        self.timeline = timeline if timeline else create_default_timeline()
        self.current_file = None
        self.modified = False

        print(f"[DEBUG {time.time():.3f}] Setting window properties...")
        self.title("DyadicSync Timeline Editor - Procedural Mode")
        self.geometry("1400x900")

        # Set minimum size
        self.minsize(1000, 600)

        # E-Prime style colors
        self.configure(bg="#F0F0F0")

        print(f"[DEBUG {time.time():.3f}] Setting up menubar...")
        self._setup_menubar()
        print(f"[DEBUG {time.time():.3f}] Setting up toolbar...")
        self._setup_toolbar()
        print(f"[DEBUG {time.time():.3f}] Setting up main layout...")
        self._setup_main_layout()
        print(f"[DEBUG {time.time():.3f}] Setting up statusbar...")
        self._setup_statusbar()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        print(f"[DEBUG {time.time():.3f}] EditorWindow.__init__ COMPLETE")

    def _setup_menubar(self):
        """Create the menu bar."""
        menubar = tk.Menu(self)
        self.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New", command=self._new_timeline, accelerator="Ctrl+N")
        file_menu.add_command(label="Open...", command=self._open_timeline, accelerator="Ctrl+O")
        file_menu.add_command(label="Save", command=self._save_timeline, accelerator="Ctrl+S")
        file_menu.add_command(label="Save As...", command=self._save_timeline_as, accelerator="Ctrl+Shift+S")
        file_menu.add_separator()
        file_menu.add_command(label="Import Legacy Config...", command=self._import_legacy_config)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_closing)

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Add Block", command=self._add_block, accelerator="Ctrl+B")
        edit_menu.add_command(label="Duplicate Block", command=self._duplicate_block, accelerator="Ctrl+D")
        edit_menu.add_command(label="Delete Block", command=self._delete_block, accelerator="Del")

        # Experiment menu
        exp_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Experiment", menu=exp_menu)
        exp_menu.add_command(label="Device Setup...", command=self._show_device_setup)
        exp_menu.add_command(label="Settings...", command=self._show_experiment_settings)
        exp_menu.add_command(label="Marker Catalog...", command=self._show_marker_catalog)
        exp_menu.add_command(label="Validate", command=self._validate_timeline)
        exp_menu.add_separator()
        exp_menu.add_command(label="Run Experiment", command=self._run_experiment, accelerator="F5")

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

        # Keyboard shortcuts
        self.bind("<Control-n>", lambda e: self._new_timeline())
        self.bind("<Control-o>", lambda e: self._open_timeline())
        self.bind("<Control-s>", lambda e: self._save_timeline())
        self.bind("<Control-Shift-S>", lambda e: self._save_timeline_as())
        self.bind("<Control-b>", lambda e: self._add_block())
        self.bind("<Control-d>", lambda e: self._duplicate_block())
        self.bind("<Delete>", lambda e: self._delete_block())
        self.bind("<F5>", lambda e: self._run_experiment())

    def _setup_toolbar(self):
        """Create the toolbar."""
        toolbar = ttk.Frame(self, relief=tk.RAISED)
        toolbar.pack(side=tk.TOP, fill=tk.X)

        # File operations
        ttk.Button(toolbar, text="New", command=self._new_timeline).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Open", command=self._open_timeline).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Save", command=self._save_timeline).pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Block operations
        # Add dropdown menu for block types
        add_block_button = ttk.Menubutton(toolbar, text="Add Block ▼")
        add_block_button.pack(side=tk.LEFT, padx=2, pady=2)

        add_block_menu = tk.Menu(add_block_button, tearoff=0)
        add_block_button.config(menu=add_block_menu)
        add_block_menu.add_command(label="Standard Block (with trials)", command=lambda: self._add_block('standard'))
        add_block_menu.add_command(label="Baseline Block", command=lambda: self._add_block('baseline'))
        add_block_menu.add_command(label="Instruction Block", command=lambda: self._add_block('instruction'))
        add_block_menu.add_command(label="Empty Block", command=lambda: self._add_block('empty'))

        ttk.Button(toolbar, text="Duplicate", command=self._duplicate_block).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_block).pack(side=tk.LEFT, padx=2, pady=2)

        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # Experiment operations
        ttk.Button(toolbar, text="Device Setup", command=self._show_device_setup).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Settings", command=self._show_experiment_settings).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="Validate", command=self._validate_timeline).pack(side=tk.LEFT, padx=2, pady=2)
        ttk.Button(toolbar, text="▶ Run", command=self._run_experiment, style="Accent.TButton").pack(side=tk.LEFT, padx=2, pady=2)

    def _setup_main_layout(self):
        """Create the main split layout."""
        print(f"[DEBUG {time.time():.3f}] _setup_main_layout START")
        # Main container
        print(f"[DEBUG {time.time():.3f}] Creating PanedWindow containers...")
        main_container = ttk.PanedWindow(self, orient=tk.VERTICAL)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Top pane (timeline + properties)
        top_pane = ttk.PanedWindow(main_container, orient=tk.HORIZONTAL)
        main_container.add(top_pane, weight=3)

        # Timeline canvas (left, 70%)
        print(f"[DEBUG {time.time():.3f}] Creating TimelineCanvas...")
        self.timeline_canvas = TimelineCanvas(
            top_pane,
            self.timeline,
            on_block_select=self._on_block_select,
            on_block_edit=self._on_block_edit
        )
        print(f"[DEBUG {time.time():.3f}] TimelineCanvas created, adding to pane...")
        top_pane.add(self.timeline_canvas, weight=7)

        # Property panel (right, 30%)
        print(f"[DEBUG {time.time():.3f}] Creating PropertyPanel...")
        self.property_panel = PropertyPanel(
            top_pane,
            timeline=self.timeline,
            on_change=self._on_property_change
        )
        print(f"[DEBUG {time.time():.3f}] PropertyPanel created, adding to pane...")
        top_pane.add(self.property_panel, weight=3)

        # Bottom pane (preview panel)
        print(f"[DEBUG {time.time():.3f}] Creating PreviewPanel...")
        self.preview_panel = PreviewPanel(main_container)
        print(f"[DEBUG {time.time():.3f}] PreviewPanel created, adding to container...")
        main_container.add(self.preview_panel, weight=2)
        print(f"[DEBUG {time.time():.3f}] _setup_main_layout COMPLETE")

    def _setup_statusbar(self):
        """Create the status bar."""
        self.statusbar = ttk.Frame(self, relief=tk.SUNKEN)
        self.statusbar.pack(side=tk.BOTTOM, fill=tk.X)

        self.status_label = ttk.Label(self.statusbar, text="Ready")
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.trial_count_label = ttk.Label(self.statusbar, text=f"Blocks: {len(self.timeline.blocks)}")
        self.trial_count_label.pack(side=tk.RIGHT, padx=5)

        self.duration_label = ttk.Label(self.statusbar, text="Duration: 00:00")
        self.duration_label.pack(side=tk.RIGHT, padx=5)

        self._update_statusbar()

    def _update_statusbar(self):
        """Update status bar information."""
        block_count = len(self.timeline.blocks)
        total_trials = self.timeline.get_total_trials()

        self.trial_count_label.config(
            text=f"Blocks: {block_count} | Trials: {total_trials}"
        )

        # Calculate total duration, using accurate durations if available
        total_duration = 0.0
        has_accurate = False
        has_estimated = False

        for block in self.timeline.blocks:
            # Check if block has calculated accurate duration
            if hasattr(block, '_cached_duration') and block._cached_duration is not None:
                total_duration += block._cached_duration
                has_accurate = True
            else:
                # Fall back to estimated duration
                block_duration = block.get_estimated_duration()
                if block_duration >= 0:
                    total_duration += block_duration
                    has_estimated = True
                else:
                    # Unknown duration, skip but mark as estimated
                    has_estimated = True

        # Format duration display
        mins = int(total_duration // 60)
        secs = int(total_duration % 60)

        # Show ~ prefix if any blocks use estimated duration
        prefix = "~" if has_estimated or not has_accurate else ""
        self.duration_label.config(text=f"Duration: {prefix}{mins:02d}:{secs:02d}")

    def _set_modified(self, modified: bool = True):
        """Mark timeline as modified."""
        self.modified = modified
        title = "DyadicSync Timeline Editor - Procedural Mode"
        if self.current_file:
            title += f" - {Path(self.current_file).name}"
        if self.modified:
            title += " *"
        self.title(title)

    def _on_block_select(self, block: Block):
        """Handle block selection."""
        self.property_panel.load_block(block)
        # TODO: Update preview panel for block
        # self.preview_panel.load_block(block)
        self.status_label.config(text=f"Selected: {block.name}")

    def _on_block_edit(self, block: Block):
        """Handle block double-click for editing."""
        self._on_block_select(block)

        # Open procedure editor dialog
        from timeline_editor.dialogs.procedure_editor_dialog import ProcedureEditorDialog

        if block.procedure is None:
            messagebox.showwarning("No Procedure", "This block has no procedure to edit.")
            return

        dialog = ProcedureEditorDialog(self, block.procedure, block.block_type)
        result = dialog.show()

        if result and result.get('modified'):
            # Procedure was modified
            self._set_modified(True)
            self.timeline_canvas.refresh()
            self._update_statusbar()
            self.status_label.config(text=f"Updated procedure for '{block.name}'")

    def _on_property_change(self):
        """Handle property change."""
        self._set_modified(True)
        self.timeline_canvas.refresh()
        self._update_statusbar()

    def _new_timeline(self):
        """Create a new timeline."""
        if self._check_save_modified():
            self.timeline = create_default_timeline()
            self.current_file = None
            self.modified = False
            self.timeline_canvas.timeline = self.timeline
            self.property_panel.timeline = self.timeline  # Update timeline reference for validation
            self.timeline_canvas.refresh()
            self.property_panel.clear()
            self.preview_panel.clear()
            self._update_statusbar()
            self._set_modified(False)
            self.status_label.config(text="New experiment created")

    def _open_timeline(self):
        """Open an existing timeline file."""
        if not self._check_save_modified():
            return

        filename = filedialog.askopenfilename(
            title="Open Timeline",
            filetypes=[("Timeline JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'r') as f:
                    data = json.load(f)

                timeline = Timeline.from_dict(data)
                self.timeline = timeline
                self.current_file = filename
                self.modified = False
                self.timeline_canvas.timeline = timeline
                self.property_panel.timeline = timeline  # Update timeline reference for validation

                # Calculate accurate durations for all blocks with CSV trial lists
                print("[TIMELINE_LOAD] Calculating durations for blocks with CSV trial lists...")
                for block in timeline.blocks:
                    if block.trial_list and block.trial_list.source and block.trial_list.source_type == 'csv':
                        print(f"[TIMELINE_LOAD] Calculating duration for block: {block.name}")
                        block.calculate_accurate_duration()

                self.timeline_canvas.refresh()
                self.property_panel.clear()
                self.preview_panel.clear()
                self._update_statusbar()
                self._set_modified(False)
                self.status_label.config(text=f"Loaded: {Path(filename).name}")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load timeline file:\n\n{str(e)}")
                import traceback
                traceback.print_exc()

    def _save_timeline(self):
        """Save the current timeline."""
        if self.current_file:
            try:
                with open(self.current_file, 'w') as f:
                    json.dump(self.timeline.to_dict(), f, indent=2)

                self._set_modified(False)
                self.status_label.config(text=f"Saved: {Path(self.current_file).name}")
                return True
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save timeline:\n\n{str(e)}")
                return False
        else:
            return self._save_timeline_as()

    def _save_timeline_as(self):
        """Save timeline to a new file."""
        filename = filedialog.asksaveasfilename(
            title="Save Timeline",
            defaultextension=".json",
            filetypes=[("Timeline JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'w') as f:
                    json.dump(self.timeline.to_dict(), f, indent=2)

                self.current_file = filename
                self._set_modified(False)
                self.status_label.config(text=f"Saved: {Path(filename).name}")
                return True
            except Exception as e:
                messagebox.showerror("Error", f"Failed to save timeline:\n\n{str(e)}")
                return False
        return False

    def _generate_unique_block_name(self, base_name: str) -> str:
        """
        Generate a unique block name by appending a number if needed.

        Args:
            base_name: Base name to use (e.g., "Baseline")

        Returns:
            Unique name (e.g., "Baseline" or "Baseline2" if "Baseline" exists)
        """
        existing_names = {block.name for block in self.timeline.blocks}

        # If base name doesn't exist, use it as-is
        if base_name not in existing_names:
            return base_name

        # Find next available number
        counter = 2
        while f"{base_name}{counter}" in existing_names:
            counter += 1

        return f"{base_name}{counter}"

    def _import_legacy_config(self):
        """Import a legacy ExperimentConfig and convert to Timeline."""
        if not self._check_save_modified():
            return

        filename = filedialog.askopenfilename(
            title="Import Legacy Configuration",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            try:
                from config.experiment import ExperimentConfig
                from core.adapters.experiment_config_adapter import ExperimentConfigAdapter

                # Load legacy config
                with open(filename, 'r') as f:
                    config_data = json.load(f)

                config = ExperimentConfig.from_dict(config_data)

                # Convert to timeline
                timeline = ExperimentConfigAdapter.to_timeline(config)

                self.timeline = timeline
                self.current_file = None  # Force save as
                self.timeline_canvas.timeline = timeline
                self.property_panel.timeline = timeline  # Update timeline reference for validation
                self.timeline_canvas.refresh()
                self._update_statusbar()
                self._set_modified(True)
                self.status_label.config(text=f"Imported legacy config: {len(timeline.blocks)} blocks created")

                messagebox.showinfo(
                    "Import Successful",
                    f"Legacy configuration imported successfully!\n\n"
                    f"Blocks created: {len(timeline.blocks)}\n"
                    f"Total trials: {timeline.get_total_trials()}\n\n"
                    f"Please save as a new Timeline file."
                )

            except Exception as e:
                messagebox.showerror("Error", f"Failed to import legacy config:\n\n{str(e)}")
                import traceback
                traceback.print_exc()

    def _add_block(self, block_type: str = 'empty'):
        """
        Add a new block to the timeline.

        Args:
            block_type: Type of block to create ('standard', 'baseline', 'instruction', 'empty')
        """
        try:
            # TODO: Open block creation dialog (Phase 1.4)
            # For now, create a simple block
            from core.execution.procedure import Procedure

            if block_type == 'baseline':
                from core.execution.phases.baseline_phase import BaselinePhase
                unique_name = self._generate_unique_block_name("Baseline")
                block = Block(name=unique_name, block_type='simple')
                proc = Procedure("Baseline")
                proc.add_phase(BaselinePhase(duration=self.timeline.metadata.get('baseline_duration', 240)))
                block.procedure = proc

            elif block_type == 'instruction':
                from core.execution.phases.instruction_phase import InstructionPhase
                unique_name = self._generate_unique_block_name("Instruction")
                block = Block(name=unique_name, block_type='simple')
                proc = Procedure("Instruction")
                proc.add_phase(InstructionPhase(
                    text="Instruction text here...",
                    wait_for_key=True,
                    continue_key='space'
                ))
                block.procedure = proc

            elif block_type == 'standard':
                from core.execution.phases.fixation_phase import FixationPhase
                from core.execution.phases.video_phase import VideoPhase
                from core.execution.phases.rating_phase import RatingPhase
                from core.execution.trial_list import TrialList

                unique_name = self._generate_unique_block_name("Video Trials")
                block = Block(name=unique_name, block_type='trial_based')
                proc = Procedure("Standard Trial")
                proc.add_phase(FixationPhase(duration=3.0))
                proc.add_phase(VideoPhase(participant_1_video="{video1}", participant_2_video="{video2}"))
                proc.add_phase(RatingPhase(question="How did you feel?"))
                block.procedure = proc

                # Initialize empty manual trial list (prevents block from disappearing)
                block.trial_list = TrialList(source="", source_type='manual')

            else:  # empty
                unique_name = self._generate_unique_block_name("New Block")
                block = Block(name=unique_name, block_type='simple')
                block.procedure = Procedure("Empty Procedure")

            self.timeline.add_block(block)
            self._set_modified(True)
            self._update_statusbar()
            self.timeline_canvas.refresh()
            self.status_label.config(text=f"Block added: {block.name}")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to add block:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _duplicate_block(self):
        """Duplicate the selected block."""
        try:
            selected_index = self.timeline_canvas.selected_block_index
            if selected_index is not None:
                # Get the selected block
                original_block = self.timeline.blocks[selected_index]

                # Serialize and deserialize to create a deep copy
                block_data = original_block.to_dict()
                new_block = Block.from_dict(block_data)

                # Generate unique name for the duplicate
                new_block.name = self._generate_unique_block_name(original_block.name)

                # Insert after the selected block
                self.timeline.add_block(new_block, index=selected_index + 1)

                self._set_modified(True)
                self._update_statusbar()
                self.timeline_canvas.refresh()
                self.status_label.config(text="Block duplicated")
            else:
                messagebox.showinfo("No Selection", "Please select a block to duplicate")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to duplicate block:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _delete_block(self):
        """Delete the selected block."""
        try:
            selected_index = self.timeline_canvas.selected_block_index
            if selected_index is not None:
                block_name = self.timeline.blocks[selected_index].name
                if messagebox.askyesno("Confirm Delete", f"Delete block '{block_name}'?"):
                    self.timeline.remove_block(selected_index)
                    self.property_panel.clear()
                    self.preview_panel.clear()
                    self._set_modified(True)
                    self._update_statusbar()
                    self.timeline_canvas.refresh()
                    self.status_label.config(text="Block deleted")
            else:
                messagebox.showinfo("No Selection", "Please select a block to delete")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete block:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def _show_device_setup(self):
        """Show device setup dialog."""
        dialog = DeviceSetupDialog(self, self.timeline)
        self.wait_window(dialog)

        if dialog.result:
            # Device configuration was saved to timeline metadata
            self._set_modified(True)
            self.status_label.config(text="Device configuration updated")
            # Auto-save after device setup
            if self.current_file:
                self._save_timeline()
            else:
                # Prompt to save if no file yet
                if messagebox.askyesno(
                    "Save Configuration",
                    "Device setup complete. Would you like to save this timeline now?"
                ):
                    self._save_timeline_as()

    def _show_experiment_settings(self):
        """Show experiment settings dialog."""
        from timeline_editor.dialogs.experiment_settings_dialog import ExperimentSettingsDialog

        dialog = ExperimentSettingsDialog(self, self.timeline.metadata)
        result = dialog.show()

        if result:
            # Update timeline metadata
            self.timeline.metadata.update(result)
            self._set_modified(True)
            self.status_label.config(text="Experiment settings updated")

            # Update baseline blocks if baseline duration changed
            old_duration = self.timeline.metadata.get('baseline_duration', 240)
            new_duration = result.get('baseline_duration', 240)

            if old_duration != new_duration:
                # Ask if user wants to update existing baseline blocks
                if messagebox.askyesno(
                    "Update Baseline Blocks",
                    f"Baseline duration changed from {old_duration}s to {new_duration}s.\n\n"
                    f"Update all existing baseline blocks?"
                ):
                    self._update_baseline_durations(new_duration)

    def _show_marker_catalog(self):
        """Show marker catalog manager dialog."""
        from timeline_editor.dialogs.marker_catalog_dialog import MarkerCatalogDialog

        dialog = MarkerCatalogDialog(self)
        # Dialog is modal and handles its own save operations
        dialog.wait_window()

    def _update_baseline_durations(self, new_duration: float):
        """Update all baseline blocks with new duration."""
        from core.execution.phases.baseline_phase import BaselinePhase

        updated_count = 0
        for block in self.timeline.blocks:
            if block.procedure:
                for phase in block.procedure.phases:
                    if isinstance(phase, BaselinePhase):
                        phase.duration = new_duration
                        updated_count += 1

        if updated_count > 0:
            self.timeline_canvas.refresh()
            self.status_label.config(text=f"Updated {updated_count} baseline phase(s)")
            self._set_modified(True)

    def _validate_timeline(self):
        """Validate the current timeline."""
        errors = self.timeline.validate()

        if not errors:
            messagebox.showinfo("Validation", "Timeline is valid!")
        else:
            error_msg = "Validation errors:\n\n" + "\n".join(f"• {err}" for err in errors[:10])
            if len(errors) > 10:
                error_msg += f"\n\n... and {len(errors) - 10} more errors"
            messagebox.showerror("Validation Errors", error_msg)

    def _run_experiment(self):
        """Run the experiment with current timeline."""
        # Validate
        errors = self.timeline.validate()

        if errors:
            messagebox.showerror(
                "Cannot Run",
                "Please fix validation errors before running:\n\n" + "\n".join(errors[:5])
            )
            return

        # Save if modified
        if self.modified:
            if not messagebox.askyesno("Save Changes", "Save changes before running?"):
                return
            if not self._save_timeline():
                return

        # Show execution dialog
        self._show_execution_dialog()

    def _show_execution_dialog(self):
        """Show execution preview/confirmation dialog."""
        # Create execution dialog
        dialog = tk.Toplevel(self)
        dialog.title("Run Experiment")
        dialog.geometry("600x500")
        dialog.transient(self)
        dialog.grab_set()

        # Title
        title_label = ttk.Label(
            dialog,
            text="Experiment Ready to Run",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=10)

        # Summary frame
        summary_frame = ttk.LabelFrame(dialog, text="Summary")
        summary_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Display timeline info
        info_text = tk.Text(summary_frame, height=15, width=70, wrap=tk.WORD)
        info_text.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # Build summary text
        total_trials = self.timeline.get_total_trials()
        duration = self.timeline.get_estimated_duration()
        mins = int(duration // 60)
        secs = int(duration % 60)

        summary = f"Experiment: {self.timeline.metadata['name']}\n"
        summary += f"Description: {self.timeline.metadata.get('description', 'N/A')}\n\n"
        summary += f"Blocks: {len(self.timeline.blocks)}\n"
        summary += f"Total Trials: {total_trials}\n"
        summary += f"Estimated Duration: {mins}:{secs:02d}\n\n"

        summary += "Block Breakdown:\n"
        for i, block in enumerate(self.timeline.blocks):
            block_duration = block.get_estimated_duration()
            block_mins = int(block_duration // 60)
            block_secs = int(block_duration % 60)
            trial_count = block.get_trial_count()
            summary += f"  {i+1}. {block.name} ({block.block_type}): "
            summary += f"{trial_count} trial{'s' if trial_count != 1 else ''}, {block_mins}:{block_secs:02d}\n"

        summary += "\n\nConfiguration:\n"
        summary += f"  Audio Device 1: {self.timeline.metadata.get('audio_device_1', 'Not set')}\n"
        summary += f"  Audio Device 2: {self.timeline.metadata.get('audio_device_2', 'Not set')}\n"
        summary += f"  LSL Enabled: {self.timeline.metadata.get('lsl_enabled', True)}\n"
        summary += f"  LSL Stream: {self.timeline.metadata.get('lsl_stream_name', 'ExpEvent_Markers')}\n"

        summary += "\n\nREADY TO RUN\n"
        summary += "Click 'Run' to start the experiment.\n\n"
        summary += "NOTE: This requires:\n"
        summary += "  - 3 displays connected (control + 2 participant)\n"
        summary += "  - 2 audio devices configured\n"
        summary += "  - EEG systems running (if using LSL)\n"
        summary += "  - LabRecorder running (to record LSL markers)\n"

        info_text.insert("1.0", summary)
        info_text.config(state=tk.DISABLED)

        # Button frame
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=10)

        def run_now():
            """Launch the experiment execution."""
            dialog.destroy()

            # 1. Check output directory configuration
            output_dir = self.timeline.metadata.get('output_directory')
            if not output_dir:
                messagebox.showerror(
                    "Configuration Error",
                    "No output directory configured.\n\n"
                    "Please set an output directory in Experiment > Settings before running."
                )
                return

            # Validate output directory
            import os
            if not os.path.exists(output_dir):
                messagebox.showerror(
                    "Configuration Error",
                    f"Output directory does not exist:\n{output_dir}\n\n"
                    "Please check your settings."
                )
                return

            # 2. Prompt for subject/session info
            from timeline_editor.dialogs.pre_execution_dialog import SubjectSessionDialog
            subject_session = SubjectSessionDialog.prompt(self)
            if subject_session is None:  # User cancelled
                return

            subject_id, session = subject_session

            # 3. Prompt for headset selection
            from timeline_editor.dialogs.pre_execution_dialog import HeadsetSelectionDialog
            headset = HeadsetSelectionDialog.prompt(self)
            if headset is None:  # User cancelled
                return

            # 4. Show progress dialog and run in subprocess
            try:
                from timeline_editor.dialogs.execution_dialog import ExecutionProgressDialog

                # Pass timeline and config to dialog
                # Dialog will serialize and pass to subprocess
                ExecutionProgressDialog.run_experiment(
                    self,
                    timeline=self.timeline,
                    subject_id=subject_id,
                    session=session,
                    headset=headset,
                    output_dir=output_dir
                )

            except Exception as e:
                messagebox.showerror(
                    "Execution Error",
                    f"Failed to start experiment:\n\n{str(e)}"
                )

        def cancel():
            dialog.destroy()

        ttk.Button(button_frame, text="▶ Run Now", command=run_now, style="Accent.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel).pack(side=tk.LEFT, padx=5)

    def _show_about(self):
        """Show about dialog."""
        messagebox.showinfo(
            "About",
            "DyadicSync Timeline Editor - Procedural Mode\n\n"
            "Visual timeline editor for designing dyadic video synchronization experiments.\n\n"
            "Works directly with Timeline/Block/Procedure/Phase architecture.\n\n"
            "Phase 1 Implementation - Data Model Complete"
        )

    def _check_save_modified(self) -> bool:
        """
        Check if timeline is modified and prompt to save.

        Returns:
            True to proceed, False to cancel
        """
        if self.modified:
            result = messagebox.askyesnocancel(
                "Save Changes",
                "Do you want to save changes to the current timeline?"
            )
            if result is None:  # Cancel
                return False
            elif result:  # Yes
                return self._save_timeline()
        return True

    def _on_closing(self):
        """Handle window close event."""
        if self._check_save_modified():
            self.destroy()


def main():
    """Run the editor."""
    # Create and run editor
    app = EditorWindow()
    app.mainloop()


if __name__ == "__main__":
    # CRITICAL for Windows multiprocessing:
    # Must call freeze_support() and set start method before any other imports
    import multiprocessing

    # Required for Windows (enables multiprocessing in frozen executables)
    multiprocessing.freeze_support()

    # Use 'spawn' start method (required on Windows, prevents Pyglet import in parent)
    # This ensures Pyglet is only imported in the subprocess, not the GUI process
    multiprocessing.set_start_method('spawn', force=True)

    # Now safe to run the editor
    main()
