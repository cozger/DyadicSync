"""
Execution progress dialog for running experiments.

Provides:
- Real-time progress display (block/trial counts)
- Estimated time remaining
- Pause/Abort controls
- Post-execution summary

Uses multiprocessing to run experiment in separate process,
solving the Pyglet main thread conflict with Tkinter.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any
import multiprocessing
import time


class ExecutionProgressDialog(tk.Toplevel):
    """
    Dialog that displays experiment execution progress.

    Features:
    - Real-time progress updates
    - Pause/Resume/Abort controls
    - Estimated time remaining
    - Post-execution summary
    - Runs experiment in separate process (multiprocessing)

    Uses multiprocessing to avoid Pyglet/Tkinter main thread conflicts.
    """

    def __init__(self, parent, timeline, subject_id, session, headset, output_dir, experiment_name="Experiment"):
        """
        Initialize execution progress dialog.

        Args:
            parent: Parent window
            timeline: Timeline object to execute
            subject_id: Subject identifier
            session: Session number
            headset: Headset selection ('B16' or 'B1A')
            output_dir: Output directory for data
            experiment_name: Name for display
        """
        super().__init__(parent)

        self.parent = parent
        self.timeline = timeline
        self.subject_id = subject_id
        self.session = session
        self.headset = headset
        self.output_dir = output_dir
        self.experiment_name = experiment_name

        # Multiprocessing primitives
        self.command_queue = multiprocessing.Queue()
        self.progress_queue = multiprocessing.Queue()
        self.abort_event = multiprocessing.Event()
        self.experiment_process: Optional[multiprocessing.Process] = None

        # State
        self.execution_error = None
        self.execution_complete = False
        self.completion_data = None
        self.start_time = None
        self.paused = False

        # LabRecorder controller and state
        self.labrecorder_controller = None
        self.labrecorder_started = False  # Track if LabRecorder has been started

        # Configure dialog
        self.title("Experiment Execution")
        self.geometry("500x100")  # Temporary height, will resize after content is built
        self.transient(parent)
        self.resizable(False, False)
        self.configure(bg="#F0F0F0")

        # Prevent closing during execution
        self.protocol("WM_DELETE_WINDOW", self._on_close_requested)

        # Build UI
        self._build_ui()

        # Modal behavior
        self.grab_set()
        self.focus_set()

        # Apply dynamic sizing now that dialog is shown
        self._apply_dynamic_size()

    def _build_ui(self):
        """Build the dialog UI."""
        # Title
        title_label = ttk.Label(
            self,
            text="Experiment in Progress",
            font=("Arial", 14, "bold")
        )
        title_label.pack(pady=(15, 10))

        # Experiment name
        exp_name_label = ttk.Label(
            self,
            text=f"Experiment: {self.experiment_name}",
            font=("Arial", 10)
        )
        exp_name_label.pack(pady=(0, 20))

        # Progress frame
        progress_frame = ttk.LabelFrame(self, text="Progress", padding=15)
        progress_frame.pack(fill=tk.X, expand=False, padx=20, pady=(0, 0))

        # Status label
        self.status_label = ttk.Label(
            progress_frame,
            text="Initializing...",
            font=("Arial", 11)
        )
        self.status_label.pack(pady=5)

        # Block progress
        self.block_label = ttk.Label(
            progress_frame,
            text="Block: --/--",
            font=("Arial", 10)
        )
        self.block_label.pack(pady=2)

        # Trial progress (within current block)
        self.trial_label = ttk.Label(
            progress_frame,
            text="",
            font=("Arial", 10),
            foreground="#666666"
        )
        self.trial_label.pack(pady=2)

        # Progress bar
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            length=400
        )
        self.progress_bar.pack(pady=10)

        # Time info
        self.time_label = ttk.Label(
            progress_frame,
            text="Elapsed: --:--",
            font=("Arial", 9),
            foreground="#555555"
        )
        self.time_label.pack(pady=5)

        # LabRecorder status
        self.labrecorder_label = ttk.Label(
            progress_frame,
            text="",
            font=("Arial", 9),
            foreground="#666666"
        )
        self.labrecorder_label.pack(pady=2)

        # Buttons frame
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=20, pady=(0, 15))

        # Pause button
        self.pause_button = ttk.Button(
            button_frame,
            text="⏸ Pause",
            command=self._on_pause,
            state=tk.DISABLED
        )
        self.pause_button.pack(side=tk.LEFT, padx=5)

        # Abort button
        self.abort_button = ttk.Button(
            button_frame,
            text="⏹ Abort",
            command=self._on_abort
        )
        self.abort_button.pack(side=tk.LEFT, padx=5)

        # Close button (hidden until execution complete)
        self.close_button = ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close
        )
        # Don't pack yet - will show after completion

    def _apply_dynamic_size(self):
        """Apply dynamic height based on content and center on parent."""
        self.update_idletasks()  # Calculate actual content size

        # Get required height from content
        required_height = self.winfo_reqheight()
        width = 500

        # Apply size with width and calculated height
        self.geometry(f"{width}x{required_height}")

        # Center on parent (use self.parent, not parent)
        x = self.parent.winfo_x() + (self.parent.winfo_width() // 2) - (width // 2)
        y = self.parent.winfo_y() + (self.parent.winfo_height() // 2) - (required_height // 2)
        self.geometry(f"{width}x{required_height}+{x}+{y}")

        # Set minimum size
        self.minsize(width, required_height)

    def start_execution(self):
        """Start experiment execution in separate process."""
        self.start_time = time.time()

        # Get LabRecorder settings from timeline metadata
        labrecorder_enabled = self.timeline.metadata.get('labrecorder_enabled', False)
        labrecorder_host = self.timeline.metadata.get('labrecorder_host', 'localhost')
        labrecorder_port = self.timeline.metadata.get('labrecorder_port', 22345)

        # Store LabRecorder settings (will be started after LSL_READY signal)
        self.labrecorder_enabled = labrecorder_enabled
        self.labrecorder_host = labrecorder_host
        self.labrecorder_port = labrecorder_port

        # Serialize configuration for subprocess
        from core.ipc.serialization import ExperimentConfig
        config = ExperimentConfig(
            timeline=self.timeline,
            subject_id=self.subject_id,
            session=self.session,
            headset=self.headset,
            output_dir=self.output_dir,
            labrecorder_enabled=labrecorder_enabled,
            labrecorder_host=labrecorder_host,
            labrecorder_port=labrecorder_port
        )
        config_dict = config.to_dict()

        # Import subprocess entry point
        from core.experiment_subprocess import run_experiment_subprocess

        # Start experiment in SEPARATE PROCESS
        self.experiment_process = multiprocessing.Process(
            target=run_experiment_subprocess,
            args=(config_dict, self.command_queue, self.progress_queue, self.abort_event),
            name="ExperimentProcess"
        )
        self.experiment_process.start()

        print(f"[GUI] Experiment subprocess started (PID: {self.experiment_process.pid})")

        # Start live previews if available
        if hasattr(self.parent, 'preview_panel'):
            try:
                # Screen indices: 1=P1, 2=P2 (dxcam 0-based indexing)
                self.parent.preview_panel.start_live_previews(
                    screen_index_p1=1,
                    screen_index_p2=2
                )
                print("[GUI] Started live preview captures")
            except Exception as e:
                print(f"[GUI] Failed to start previews: {e}")

        # Start polling for updates
        self.after(100, self._check_progress)

        # Enable pause button after initialization
        self.after(1000, lambda: self.pause_button.configure(state=tk.NORMAL))

    def _check_progress(self):
        """Poll progress queue for updates from subprocess."""
        # Check for messages from subprocess
        while not self.progress_queue.empty():
            try:
                msg_dict = self.progress_queue.get_nowait()
                from core.ipc.messages import IPCMessage, MessageType

                msg = IPCMessage.from_dict(msg_dict)

                if msg.type == MessageType.PROGRESS:
                    self._update_progress(msg.data)
                elif msg.type == MessageType.ERROR:
                    self._handle_error(msg.data)
                elif msg.type == MessageType.COMPLETE:
                    self._handle_completion(msg.data)
                elif msg.type == MessageType.LOG:
                    print(f"[Subprocess] {msg.data['message']}")
                elif msg.type == MessageType.LSL_READY:
                    # Subprocess LSL outlet is ready - NOW start LabRecorder
                    print("[GUI] Received LSL_READY signal - subprocess LSL outlet created")
                    
                    # Start LabRecorder if enabled and not already started
                    if (hasattr(self, 'labrecorder_enabled') and self.labrecorder_enabled and 
                        self.subject_id != 0 and self.session != 0):
                        if not hasattr(self, 'labrecorder_started') or not self.labrecorder_started:
                            print("[GUI] Starting LabRecorder now that LSL outlet exists...")
                            self._start_labrecorder(self.labrecorder_host, self.labrecorder_port)
                            self.labrecorder_started = True

            except Exception as e:
                print(f"[GUI] Progress check error: {e}")

        # Check if process died unexpectedly
        if self.experiment_process and not self.experiment_process.is_alive() and not self.execution_complete:
            exit_code = self.experiment_process.exitcode
            if exit_code != 0:
                self._handle_error({
                    'error': f'Experiment process crashed (exit code {exit_code})',
                    'traceback': 'Process terminated unexpectedly'
                })

        # Update elapsed time and estimated remaining time
        if self.start_time and not self.execution_complete:
            elapsed = time.time() - self.start_time
            elapsed_minutes = int(elapsed // 60)
            elapsed_seconds = int(elapsed % 60)

            # Calculate total estimated duration using accurate durations if available
            total_duration = 0.0
            for block in self.timeline.blocks:
                if hasattr(block, '_cached_duration') and block._cached_duration is not None:
                    total_duration += block._cached_duration
                else:
                    block_duration = block.get_estimated_duration()
                    if block_duration >= 0:
                        total_duration += block_duration

            # Calculate remaining time based on progress
            # Try to get progress from progress_bar value
            progress_percent = self.progress_bar['value']
            if total_duration > 0 and progress_percent > 0:
                # Estimate remaining time based on current pace
                estimated_total_time = elapsed / (progress_percent / 100)
                remaining = max(0, estimated_total_time - elapsed)
                remaining_minutes = int(remaining // 60)
                remaining_seconds = int(remaining % 60)
                self.time_label.config(
                    text=f"Elapsed: {elapsed_minutes:02d}:{elapsed_seconds:02d} | Remaining: ~{remaining_minutes:02d}:{remaining_seconds:02d}"
                )
            else:
                # No progress yet or no duration estimate
                self.time_label.config(text=f"Elapsed: {elapsed_minutes:02d}:{elapsed_seconds:02d}")

        # Continue polling if not complete
        if not self.execution_complete:
            self.after(100, self._check_progress)

    def _update_progress(self, data: Dict[str, Any]):
        """Update GUI with progress data from subprocess."""
        # Update block label
        block_text = f"Block: {data['current_block']}/{data['total_blocks']}"
        if data.get('block_name'):
            block_text += f" - {data['block_name']}"
        self.block_label.config(text=block_text)

        # Update progress bar
        if data['total_blocks'] > 0:
            percent = (data['current_block'] / data['total_blocks']) * 100
            self.progress_bar['value'] = percent

        # Update status
        if self.paused:
            self.status_label.config(text="⏸ Paused", foreground="orange")
        else:
            self.status_label.config(text="▶ Running", foreground="green")

    def _handle_error(self, data: Dict[str, Any]):
        """Handle error from subprocess."""
        self.execution_error = data['error']
        self.execution_complete = True
        self._on_execution_complete()

    def _handle_completion(self, data: Dict[str, Any]):
        """Handle successful completion from subprocess."""
        self.execution_complete = True
        self.completion_data = data
        self._on_execution_complete()

    def _on_pause(self):
        """Handle pause button click."""
        from core.ipc.messages import pause_command, resume_command

        if self.paused:
            # Resume
            self.command_queue.put(resume_command())
            self.pause_button.config(text="⏸ Pause")
            self.paused = False
        else:
            # Pause
            self.command_queue.put(pause_command())
            self.pause_button.config(text="▶ Resume")
            self.paused = True

    def _on_abort(self):
        """Handle abort button click."""
        result = messagebox.askyesno(
            "Abort Experiment",
            "Are you sure you want to abort the experiment?\n\n"
            "Partial data will be saved.",
            parent=self
        )

        if result:
            # Stop LabRecorder immediately
            self._stop_labrecorder()

            # Signal subprocess to abort
            from core.ipc.messages import abort_command
            self.command_queue.put(abort_command())
            self.abort_event.set()
            self.abort_button.config(state=tk.DISABLED)
            self.pause_button.config(state=tk.DISABLED)

    def _on_close_requested(self):
        """Handle window close request during execution."""
        if not self.execution_complete:
            messagebox.showwarning(
                "Experiment Running",
                "Please use the Abort button to stop the experiment first.",
                parent=self
            )
        else:
            self._on_close()

    def _on_close(self):
        """Close the dialog and cleanup subprocess."""
        # Stop LabRecorder if still recording
        self._stop_labrecorder()

        # Ensure previews are stopped
        if hasattr(self.parent, 'preview_panel'):
            try:
                self.parent.preview_panel.stop_live_previews()
            except Exception as e:
                print(f"[GUI] Error stopping previews on close: {e}")

        # Wait for process to finish (with timeout)
        if self.experiment_process and self.experiment_process.is_alive():
            print("[GUI] Waiting for experiment process to finish...")
            self.experiment_process.join(timeout=2.0)
            if self.experiment_process.is_alive():
                # Force terminate if still running
                print("[GUI] Force terminating experiment process...")
                self.experiment_process.terminate()
                self.experiment_process.join()

        self.grab_release()
        self.destroy()

    def _start_labrecorder(self, host: str, port: int):
        """
        Start LabRecorder recording.

        Args:
            host: LabRecorder RCS host
            port: LabRecorder RCS port
        """
        try:
            # Connect to LabRecorder
            # NOTE: LSL outlet is created by subprocess, not here
            # LabRecorder will discover it after LSL_READY signal
            from core.labrecorder_control import LabRecorderController

            self.labrecorder_controller = LabRecorderController(host=host, port=port, timeout=3.0)

            # Try to connect
            if not self.labrecorder_controller.connect():
                self.labrecorder_label.config(
                    text="⚠️ LabRecorder: Connection failed (continuing without)",
                    foreground="orange"
                )
                print("[GUI] LabRecorder connection failed - experiment will continue without recording")
                self.labrecorder_controller = None
                return

            # Start recording with formatted filename
            task_name = self.timeline.metadata.get('name', 'Experiment').replace(' ', '_')
            success = self.labrecorder_controller.start_recording(
                subject_id=self.subject_id,
                session=self.session,
                task_name=task_name,
                output_dir=self.output_dir
            )

            if success:
                self.labrecorder_label.config(
                    text="⏳ LabRecorder: Initializing recording...",
                    foreground="orange"
                )
                self.labrecorder_label.update_idletasks()  # Force GUI update
                print(f"[GUI] LabRecorder started: sub-{self.subject_id:03d}_ses-{self.session:02d}_{task_name}.xdf")

                # Wait for LabRecorder to fully initialize recording
                # This ensures the recording is stable before headset marker (9161/9162) is sent
                # The start_recording() method already waited for stream discovery
                import time
                time.sleep(2.5)

                self.labrecorder_label.config(
                    text="🔴 LabRecorder: Recording all streams",
                    foreground="green"
                )
                self.labrecorder_label.update_idletasks()  # Force GUI update
                print("[GUI] LabRecorder initialization complete")
            else:
                self.labrecorder_label.config(
                    text="⚠️ LabRecorder: Failed to start (continuing without)",
                    foreground="orange"
                )
                print("[GUI] LabRecorder failed to start - experiment will continue without recording")
                self.labrecorder_controller = None

        except Exception as e:
            self.labrecorder_label.config(
                text="⚠️ LabRecorder: Error (continuing without)",
                foreground="orange"
            )
            print(f"[GUI] LabRecorder error: {e}")
            self.labrecorder_controller = None

    def _stop_labrecorder(self):
        """Stop LabRecorder recording."""
        if self.labrecorder_controller:
            try:
                # Attempt to stop recording and check if it succeeded
                success = self.labrecorder_controller.stop_recording()

                if success:
                    self.labrecorder_controller.close()
                    self.labrecorder_label.config(
                        text="⏹ LabRecorder: Stopped",
                        foreground="gray"
                    )
                    print("[GUI] LabRecorder stopped successfully")
                else:
                    # Stop failed (socket error, not connected, etc.)
                    self.labrecorder_label.config(
                        text="⚠️ LabRecorder: Stop failed (check console)",
                        foreground="red"
                    )
                    print("[GUI] ERROR: LabRecorder stop command failed!")
                    print("[GUI] Recording may still be active - please stop LabRecorder manually")

                    # Try to close socket anyway
                    try:
                        self.labrecorder_controller.close()
                    except:
                        pass

            except Exception as e:
                self.labrecorder_label.config(
                    text="⚠️ LabRecorder: Error (check console)",
                    foreground="red"
                )
                print(f"[GUI] ERROR stopping LabRecorder: {e}")
                print("[GUI] Recording may still be active - please stop LabRecorder manually")
            finally:
                self.labrecorder_controller = None


    def _on_execution_complete(self):
        """Handle experiment completion or error."""
        # Stop LabRecorder
        self._stop_labrecorder()

        # Stop live previews
        if hasattr(self.parent, 'preview_panel'):
            try:
                self.parent.preview_panel.stop_live_previews()
                print("[GUI] Stopped live preview captures")
            except Exception as e:
                print(f"[GUI] Error stopping previews: {e}")

        # Update UI for completion
        self.pause_button.pack_forget()
        self.abort_button.pack_forget()
        self.close_button.pack(side=tk.RIGHT, padx=5)

        if self.execution_error:
            # Show error
            self.status_label.config(text="❌ Error", foreground="red")
            self.progress_bar['value'] = 0

            error_text = tk.Text(
                self,
                height=6,
                width=50,
                wrap=tk.WORD,
                font=("Courier", 9)
            )
            error_text.pack(padx=20, pady=10)
            error_text.insert("1.0", f"Error: {self.execution_error}")
            error_text.config(state=tk.DISABLED, bg="#FFE6E6")

            messagebox.showerror(
                "Execution Failed",
                f"Experiment execution failed:\n\n{self.execution_error}",
                parent=self
            )
        else:
            # Show success summary
            self.status_label.config(text="✓ Complete", foreground="green")
            self.progress_bar['value'] = 100

            # Get data from completion message
            if self.completion_data:
                trial_count = self.completion_data.get('trial_count', 0)
                response_count = self.completion_data.get('response_count', 0)
                output_dir = self.completion_data.get('output_dir')
                duration = self.completion_data.get('duration_seconds', 0)

                # Show summary
                summary_text = f"Experiment completed successfully!\n\n"
                summary_text += f"Trials: {trial_count}\n"
                summary_text += f"Responses: {response_count}\n"
                summary_text += f"Duration: {duration:.1f}s\n"

                if output_dir:
                    summary_text += f"\nData saved to:\n{output_dir}"
                else:
                    summary_text += "\nData saving was disabled (subject/session = 0)"

                self.trial_label.config(text=summary_text, font=("Arial", 9))
            else:
                self.trial_label.config(text="Experiment completed!", font=("Arial", 9))

        # Release grab so user can interact with editor
        self.grab_release()

    @classmethod
    def run_experiment(cls, parent, timeline, subject_id, session, headset, output_dir):
        """
        Show dialog and run experiment.

        Args:
            parent: Parent window
            timeline: Timeline to execute
            subject_id: Subject identifier
            session: Session number
            headset: Headset selection
            output_dir: Output directory for data
        """
        experiment_name = timeline.metadata.get('name', 'Experiment')
        dialog = cls(parent, timeline, subject_id, session, headset, output_dir, experiment_name)
        dialog.start_execution()
        # Don't wait for dialog - subprocess will run independently
