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

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize experiment from configuration file.

        Args:
            config_path: Path to JSON config, or None for empty experiment
        """
        self.name: str = "Untitled Experiment"
        self.description: str = ""
        self.version: str = "1.0"

        # Core components
        self.timeline: Timeline = Timeline()
        self.device_manager: DeviceManager = DeviceManager()
        self.lsl_outlet: Optional[StreamOutlet] = None
        self.data_collector: DataCollector = DataCollector()

        # Runtime state
        self.current_block_index: int = 0
        self.paused: threading.Event = threading.Event()
        self.aborted: threading.Event = threading.Event()

        # Load from file if provided
        if config_path:
            self.load(config_path)

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

        # Validate timeline
        timeline_errors = self.timeline.validate()
        errors.extend([f"Timeline: {e}" for e in timeline_errors])

        # Validate devices
        device_errors = self.device_manager.validate()
        errors.extend([f"Devices: {e}" for e in device_errors])

        return errors

    def run(self):
        """
        Execute the experiment timeline.

        Flow:
        1. Setup devices
        2. Initialize LSL
        3. For each block in timeline:
            a. Execute block
            b. Check for pause/abort
            c. Save intermediate data
        4. Cleanup and final save
        """
        try:
            print(f"[Experiment] Starting experiment: {self.name}")

            # Validate before running
            errors = self.validate()
            if errors:
                print(f"[Experiment] Validation errors:")
                for error in errors:
                    print(f"  - {error}")
                raise RuntimeError(f"Experiment validation failed with {len(errors)} errors")

            # Setup
            print("[Experiment] Initializing devices...")
            self.device_manager.initialize()

            print("[Experiment] Initializing LSL...")
            self.lsl_outlet = self._initialize_lsl()

            print("[Experiment] Starting timeline execution...")

            # Execute timeline
            for i, block in enumerate(self.timeline.blocks):
                if self.aborted.is_set():
                    print(f"[Experiment] Experiment aborted at block {i}")
                    break

                self.current_block_index = i
                print(f"[Experiment] Executing block {i+1}/{len(self.timeline.blocks)}: {block.name}")

                # Execute block
                block.execute(
                    device_manager=self.device_manager,
                    lsl_outlet=self.lsl_outlet,
                    data_collector=self.data_collector
                )

                # Handle pause
                while self.paused.is_set():
                    print(f"[Experiment] Paused at block {i}")
                    time.sleep(0.1)

            print("[Experiment] Timeline execution complete")

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
        Initialize LSL stream for markers.

        Returns:
            StreamOutlet instance
        """
        info = StreamInfo(
            name='ExpEvent_Markers',
            type='Markers',
            channel_count=1,
            channel_format='int32',
            source_id='dyadicsync_exp'
        )
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
