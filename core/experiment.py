"""
Experiment class for DyadicSync Framework.

Top-level experiment orchestrator.
"""

from typing import List, Optional, Dict, Any
import threading
import time
from pylsl import StreamInfo, StreamOutlet
from .execution.timeline import Timeline
from .device_manager import DeviceManager
from .data_collector import DataCollector


class Experiment:
    """
    Top-level experiment orchestrator.

    Responsibilities:
    - Manage timeline of blocks
    - Initialize devices and LSL
    - Coordinate data collection
    - Handle global experiment events (pause, abort)

    Lifecycle:
    1. __init__: Load configuration
    2. validate: Check all resources exist
    3. run: Execute timeline
    4. save_data: Write collected data to disk
    """

    def __init__(self, timeline: Optional[Timeline] = None, config_path: Optional[str] = None, progress_queue=None):
        """
        Initialize experiment from Timeline object or configuration file.

        Args:
            timeline: Timeline object (for direct editor integration)
            config_path: Path to JSON config, or None for empty experiment
            progress_queue: IPC queue for sending messages to GUI (optional)
        """
        self.name: str = "Untitled Experiment"
        self.description: str = ""
        self.version: str = "1.0"

        # Core components
        self.timeline: Timeline = timeline if timeline is not None else Timeline()
        self.device_manager: DeviceManager = DeviceManager()
        self.lsl_outlet: Optional[StreamOutlet] = None
        self.data_collector: DataCollector = DataCollector()
        
        # IPC queue for sending messages to GUI
        self.progress_queue = progress_queue

        # Runtime state
        self.current_block_index: int = 0
        self.paused: threading.Event = threading.Event()
        self.aborted: threading.Event = threading.Event()

        # Subject/session info for data collection
        self.subject_id: Optional[int] = None
        self.session: Optional[int] = None
        self.headset_selection: Optional[str] = None  # 'B16' or 'B1A'

        # Configure from timeline if provided directly
        if timeline is not None:
            self._configure_from_timeline_metadata()
        # Otherwise load from file if provided
        elif config_path:
            self.load(config_path)

    def _configure_from_timeline_metadata(self):
        """
        Configure experiment from timeline metadata.

        Maps timeline metadata fields to device manager configuration.
        """
        metadata = self.timeline.metadata

        # Update experiment info
        self.name = metadata.get('name', 'Untitled Experiment')
        self.description = metadata.get('description', '')

        # Configure device manager from timeline metadata
        if metadata.get('audio_device_1') is not None:
            self.device_manager.audio_device_p1 = metadata['audio_device_1']
        if metadata.get('audio_device_2') is not None:
            self.device_manager.audio_device_p2 = metadata['audio_device_2']
        if metadata.get('participant_1_monitor') is not None:
            self.device_manager.display_p1 = metadata['participant_1_monitor']
        if metadata.get('participant_2_monitor') is not None:
            self.device_manager.display_p2 = metadata['participant_2_monitor']

        # Configure data collector output directory
        output_dir = metadata.get('output_directory')
        if output_dir:
            self.data_collector.output_directory = output_dir

    def set_subject_info(self, subject_id: int, session: int):
        """
        Set subject and session information for data collection.

        Args:
            subject_id: Subject identifier (0 to disable data saving)
            session: Session number (0 to disable data saving)
        """
        self.subject_id = subject_id
        self.session = session

        # Configure data collector
        self.data_collector.set_subject_info(subject_id, session)

    def set_headset_selection(self, headset: str):
        """
        Set EEG headset selection for Participant 1.

        Args:
            headset: 'B16' or 'B1A'
        """
        self.headset_selection = headset

    def validate(self) -> List[str]:
        """
        Validate experiment configuration.

        Returns:
            List of error messages (empty if valid)

        Checks:
        - All video files exist
        - All audio devices available
        - All displays available
        - Procedures reference valid trial list columns
        - LSL stream name is unique
        """
        errors = []

        # Validate timeline (use execution validation for full checks)
        timeline_errors = self.timeline.validate_for_execution()
        errors.extend([f"Timeline: {e}" for e in timeline_errors])

        # Validate devices
        device_errors = self.device_manager.validate()
        errors.extend([f"Devices: {e}" for e in device_errors])

        return errors

    def run(self):
        """
        Execute the experiment timeline with single Pyglet event loop.

        Flow:
        1. Setup devices
        2. Initialize LSL
        3. Schedule blocks sequentially via callbacks
        4. Run single pyglet.app.run() for entire experiment
        5. Cleanup and final save

        This method uses the WithBaseline.py pattern: one continuous event loop
        with pyglet.clock.schedule() for block transitions.
        """
        try:
            print(f"[Experiment] Starting experiment: {self.name}")

            # Initialize devices first (scans displays and audio)
            print("[Experiment] Initializing devices...")
            self.device_manager.initialize()

            # Validate after devices are scanned
            print("[Experiment] Validating configuration...")
            errors = self.validate()
            if errors:
                print(f"[Experiment] Validation errors:")
                for error in errors:
                    print(f"  - {error}")
                raise RuntimeError(f"Experiment validation failed with {len(errors)} errors")

            # Initialize LSL
            print("[Experiment] Initializing LSL...")
            self.lsl_outlet = self._initialize_lsl()
            
            # Signal GUI that LSL outlet is ready (for discovery outlet cleanup)
            if self.progress_queue:
                from core.ipc.messages import IPCMessage, MessageType
                msg = IPCMessage(type=MessageType.LSL_READY, data={})
                self.progress_queue.put(msg.to_dict())
                print("[Experiment] Sent LSL_READY signal to GUI")

            # Headset assignment stored in LSL stream metadata (see _initialize_lsl)
            # Markers 9161/9162 are deprecated - metadata cannot be missed like time-series markers
            if self.headset_selection:
                print(f"[Experiment] Headset assignment: P1={self.headset_selection} (stored in LSL metadata)")

            print("[Experiment] Starting timeline execution...")

            # Recursive function to execute blocks sequentially
            def execute_block_at_index(index):
                """Execute block at given index, then schedule next block."""
                if index >= len(self.timeline.blocks):
                    # All blocks complete - exit event loop
                    print("[Experiment] Timeline execution complete")
                    import pyglet
                    pyglet.app.exit()
                    return

                if self.aborted.is_set():
                    print(f"[Experiment] Experiment aborted at block {index}")
                    import pyglet
                    pyglet.app.exit()
                    return

                block = self.timeline.blocks[index]
                self.current_block_index = index
                print(f"[Experiment] Executing block {index+1}/{len(self.timeline.blocks)}: {block.name}")

                # Define completion callback for this block
                def on_block_complete():
                    """Called when current block completes."""
                    # Handle pause (check in callback for non-blocking pause)
                    if self.paused.is_set():
                        print(f"[Experiment] Paused at block {index}")
                        # Schedule pause check every 100ms
                        import pyglet
                        def check_resume(dt):
                            if not self.paused.is_set():
                                pyglet.clock.unschedule(check_resume)
                                # Resume by scheduling next block
                                pyglet.clock.schedule_once(lambda dt: execute_block_at_index(index + 1), 0.0)
                        pyglet.clock.schedule_interval(check_resume, 0.1)
                    else:
                        # Schedule next block (use pyglet.clock to avoid deep recursion)
                        import pyglet
                        pyglet.clock.schedule_once(lambda dt: execute_block_at_index(index + 1), 0.0)

                # Execute block (non-blocking, will call on_block_complete when done)
                block.execute(
                    device_manager=self.device_manager,
                    lsl_outlet=self.lsl_outlet,
                    data_collector=self.data_collector,
                    on_complete=on_block_complete
                )

            # Start executing blocks from index 0
            import pyglet
            pyglet.clock.schedule_once(lambda dt: execute_block_at_index(0), 0.0)

            # Run single Pyglet event loop for entire experiment
            # (This is the key change - ONE run instead of multiple)
            print("[Experiment] Starting Pyglet event loop...")
            pyglet.app.run()
            print("[Experiment] Pyglet event loop exited")

        except Exception as e:
            print(f"[Experiment] Error during execution: {e}")
            raise

        finally:
            # Cleanup
            print("[Experiment] Cleaning up...")
            self.device_manager.cleanup()
            self.data_collector.save_all()
            print("[Experiment] Experiment finished")

    def pause(self):
        """Pause experiment between blocks."""
        self.paused.set()
        print("[Experiment] Pause requested")

    def resume(self):
        """Resume paused experiment."""
        self.paused.clear()
        print("[Experiment] Resuming")

    def abort(self):
        """Abort experiment (save partial data)."""
        self.aborted.set()
        print("[Experiment] Abort requested - will save partial data")

    def save(self, filepath: str):
        """
        Save experiment configuration to JSON.

        Args:
            filepath: Path to save JSON file
        """
        import json

        config = {
            'experiment': {
                'name': self.name,
                'description': self.description,
                'version': self.version
            },
            'devices': self.device_manager.get_config(),
            'timeline': self.timeline.to_dict()
        }

        with open(filepath, 'w') as f:
            json.dump(config, f, indent=2)

        print(f"[Experiment] Saved to {filepath}")

    def load(self, filepath: str):
        """
        Load experiment configuration from JSON.

        Args:
            filepath: Path to JSON config file
        """
        import json

        with open(filepath, 'r') as f:
            config = json.load(f)

        # Load experiment metadata
        exp_config = config.get('experiment', {})
        self.name = exp_config.get('name', 'Untitled Experiment')
        self.description = exp_config.get('description', '')
        self.version = exp_config.get('version', '1.0')

        # Load device configuration
        device_config = config.get('devices', {})
        self.device_manager.configure(device_config)

        # Load timeline
        timeline_data = config.get('timeline', {})
        self.timeline = Timeline.from_dict(timeline_data)

        print(f"[Experiment] Loaded from {filepath}")

    def _initialize_lsl(self) -> StreamOutlet:
        """
        Initialize LSL stream for markers with metadata.

        Adds headset assignment to stream metadata (instead of using markers 9161/9162).
        Metadata is stored in XDF file header and cannot be missed like time-series markers.

        Returns:
            StreamOutlet instance
        """
        info = StreamInfo(
            name='ExpEvent_Markers',
            type='Markers',
            channel_count=1,
            channel_format='string',
            source_id='dyadicsync_exp'
        )

        # Add experiment metadata to stream description
        desc = info.desc()
        desc.append_child_value('experiment_system', 'DyadicSync')
        desc.append_child_value('version', '2.0')

        # Add headset assignment metadata (replaces markers 9161/9162)
        if self.headset_selection:
            # Participant 1 headset
            p1 = desc.append_child('participant_1')
            p1.append_child_value('headset_id', self.headset_selection)  # 'B16' or 'B1A'

            # Participant 2 headset (opposite of P1)
            p2 = desc.append_child('participant_2')
            p2_headset = 'B1A' if self.headset_selection == 'B16' else 'B16'
            p2.append_child_value('headset_id', p2_headset)

            print(f"[Experiment] LSL metadata: P1={self.headset_selection}, P2={p2_headset}")

        outlet = StreamOutlet(info)
        print("[Experiment] LSL stream initialized: ExpEvent_Markers")
        return outlet

    def get_progress(self) -> Dict[str, Any]:
        """
        Get current experiment progress.

        Returns:
            Dictionary with progress information
        """
        total_blocks = len(self.timeline.blocks)
        current_block = self.current_block_index + 1 if self.current_block_index < total_blocks else total_blocks

        return {
            'current_block': current_block,
            'total_blocks': total_blocks,
            'current_block_name': self.timeline.blocks[self.current_block_index].name if total_blocks > 0 else '',
            'paused': self.paused.is_set(),
            'aborted': self.aborted.is_set()
        }

    def __repr__(self):
        return (
            f"Experiment(name='{self.name}', "
            f"blocks={len(self.timeline.blocks)}, "
            f"total_trials={self.timeline.get_total_trials()})"
        )
