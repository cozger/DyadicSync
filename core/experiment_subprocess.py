"""
Experiment subprocess entry point.

This module runs in a SEPARATE PROCESS with its own main thread,
allowing Pyglet to create windows without conflicts with Tkinter.

CRITICAL: Pyglet must ONLY be imported in this subprocess, not in parent.
This is enforced by importing Pyglet inside functions, not at module level.
"""

import sys
import os
import traceback
import time
from multiprocessing import Queue, Event
from typing import Dict, Any

from core.experiment import Experiment
from core.ipc.messages import (
    MessageType, ProgressMessage, ErrorMessage, CompleteMessage,
    LogMessage, IPCMessage
)
from core.ipc.serialization import ExperimentConfig


def run_experiment_subprocess(
    config_dict: Dict[str, Any],
    command_queue: Queue,
    progress_queue: Queue,
    abort_event: Event
):
    """
    Main entry point for experiment subprocess.

    This function runs in a SEPARATE PROCESS with its own main thread.
    Pyglet windows can be created here without conflicts.

    Args:
        config_dict: Serialized ExperimentConfig
        command_queue: Queue for receiving commands from GUI
        progress_queue: Queue for sending updates to GUI
        abort_event: Shared Event for abort signal
    """
    # Import Pyglet ONLY in subprocess (not at module level!)
    import pyglet

    experiment = None
    start_time = time.time()

    try:
        print(f"[Subprocess] Starting experiment subprocess (PID: {os.getpid()})")

        # Deserialize configuration
        config = ExperimentConfig.from_dict(config_dict)
        print(f"[Subprocess] Configuration: {config}")

        # Create experiment from timeline
        # NOTE: This recreates LSL outlet, DeviceManager, DataCollector
        # All these objects are created fresh in THIS process
        experiment = Experiment(timeline=config.timeline, progress_queue=progress_queue)
        experiment.set_subject_info(config.subject_id, config.session)
        experiment.set_headset_selection(config.headset)

        # Override data collector output directory
        if config.output_dir:
            experiment.data_collector.output_directory = config.output_dir
            experiment.data_collector.output_dir = config.output_dir

        # Set up periodic command checking via Pyglet clock
        def check_commands_periodic(dt):
            """Periodically check for commands from GUI."""
            check_commands(command_queue, experiment, abort_event)

        # Schedule command checking every 0.1 seconds during Pyglet loop
        pyglet.clock.schedule_interval(check_commands_periodic, 0.1)

        # Set up progress callback
        def send_progress_update():
            """Send progress update to GUI."""
            try:
                prog = experiment.get_progress()
                msg = ProgressMessage(
                    current_block=prog['current_block'],
                    total_blocks=prog['total_blocks'],
                    block_name=prog['current_block_name']
                )
                progress_queue.put(msg.to_dict())
            except Exception as e:
                print(f"[Subprocess] Error sending progress: {e}")

        # Schedule progress updates every 0.5 seconds
        pyglet.clock.schedule_interval(lambda dt: send_progress_update(), 0.5)

        # Run experiment
        # This creates Pyglet windows in THIS process's main thread
        print("[Subprocess] Starting experiment.run()...")
        experiment.run()

        # Send completion message
        duration = time.time() - start_time
        msg = CompleteMessage(
            trial_count=experiment.data_collector.get_trial_count(),
            response_count=experiment.data_collector.get_response_count(),
            output_dir=experiment.data_collector.output_directory if experiment.data_collector.data_saving_enabled else None,
            duration_seconds=duration
        )
        progress_queue.put(msg.to_dict())

        print(f"[Subprocess] Experiment completed successfully in {duration:.1f}s")

    except Exception as e:
        # Send error to GUI
        error_msg = ErrorMessage(
            error=str(e),
            traceback=traceback.format_exc()
        )
        progress_queue.put(error_msg.to_dict())

        print(f"[Subprocess] Error during execution:")
        print(traceback.format_exc())

        # Re-raise for debugging if needed
        # raise

    finally:
        # Cleanup
        if experiment:
            try:
                print("[Subprocess] Cleaning up experiment...")
                experiment.device_manager.cleanup()
                experiment.data_collector.save_all()
                print("[Subprocess] Cleanup complete")
            except Exception as cleanup_error:
                print(f"[Subprocess] Cleanup error: {cleanup_error}")

        print("[Subprocess] Experiment subprocess exiting")


def check_commands(command_queue: Queue, experiment: 'Experiment', abort_event: Event):
    """
    Check for commands from GUI and handle them.

    This is called periodically during experiment execution
    via Pyglet clock scheduling.

    Args:
        command_queue: Queue with commands from GUI
        experiment: Experiment instance
        abort_event: Shared abort event
    """
    import pyglet

    try:
        # Check for abort event first (fastest)
        if abort_event.is_set():
            print("[Subprocess] Abort event detected - forcing Pyglet exit")
            experiment.abort()
            # Force immediate exit of Pyglet event loop
            pyglet.app.exit()
            return

        # Check for queued commands
        while not command_queue.empty():
            try:
                msg_dict = command_queue.get_nowait()
                msg = IPCMessage.from_dict(msg_dict)

                if msg.type == MessageType.PAUSE:
                    print("[Subprocess] Received PAUSE command")
                    experiment.pause()
                elif msg.type == MessageType.RESUME:
                    print("[Subprocess] Received RESUME command")
                    experiment.resume()
                elif msg.type == MessageType.ABORT:
                    print("[Subprocess] Received ABORT command - forcing Pyglet exit")
                    experiment.abort()
                    abort_event.set()
                    # Force immediate exit of Pyglet event loop
                    pyglet.app.exit()

            except Exception as msg_error:
                print(f"[Subprocess] Error processing message: {msg_error}")

    except Exception as e:
        print(f"[Subprocess] Command checking error: {e}")


# Main entry point for testing subprocess independently
if __name__ == '__main__':
    print("Experiment subprocess entry point")
    print("This module should be called via multiprocessing.Process, not directly")
    sys.exit(1)
