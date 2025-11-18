"""
LabRecorder Remote Control Module

Provides programmatic control of LabRecorder via Remote Control Socket (RCS).
Allows automatic start/stop of LSL recording synchronized with experiment execution.

LabRecorder must be running with RCS enabled (default port 22345).
"""

import socket
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LabRecorderController:
    """
    Remote control client for LabRecorder via TCP socket.

    Connects to LabRecorder's Remote Control Socket (RCS) to programmatically
    start/stop recording and configure output filenames.

    Attributes:
        host: Hostname/IP of LabRecorder RCS (default: 'localhost')
        port: Port number of LabRecorder RCS (default: 22345)
        timeout: Socket connection timeout in seconds (default: 5.0)
    """

    def __init__(self, host: str = 'localhost', port: int = 22345, timeout: float = 5.0):
        """
        Initialize LabRecorder controller.

        Args:
            host: LabRecorder RCS hostname (default: 'localhost')
            port: LabRecorder RCS port (default: 22345)
            timeout: Connection timeout in seconds (default: 5.0)
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.socket: Optional[socket.socket] = None
        self._is_recording = False

    def connect(self) -> bool:
        """
        Establish connection to LabRecorder RCS.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            logger.info(f"Connected to LabRecorder at {self.host}:{self.port}")
            print(f"[LabRecorder] ✓ Connected to LabRecorder RCS at {self.host}:{self.port}")
            print(f"[LabRecorder] Make sure all LSL streams are running BEFORE starting experiment")
            return True
        except (socket.timeout, ConnectionRefusedError, OSError) as e:
            logger.warning(f"Could not connect to LabRecorder: {e}")
            logger.warning("Make sure LabRecorder is running with RCS enabled")
            print(f"[LabRecorder] ✗ Connection failed: {e}")
            print(f"[LabRecorder] Make sure LabRecorder is running with RCS enabled")
            self.socket = None
            return False

    def is_connected(self) -> bool:
        """
        Check if currently connected to LabRecorder.

        Returns:
            True if socket is connected, False otherwise
        """
        return self.socket is not None

    def send_command(self, command: str, expect_response: bool = True) -> bool:
        """
        Send command to LabRecorder and optionally read response.

        CRITICAL: LabRecorder sends "OK" response after every command.
        This response MUST be read from the socket to prevent buffer pollution
        and protocol desynchronization.

        Args:
            command: Command string (e.g., 'start', 'stop', 'select all')
            expect_response: If True, wait for and validate "OK" response (default: True)

        Returns:
            True if command sent successfully (and response validated if expected)
        """
        if not self.is_connected():
            logger.error("Cannot send command: not connected to LabRecorder")
            print(f"[LabRecorder] ERROR: Cannot send command '{command}' - not connected")
            return False

        try:
            # Send command with newline terminator
            self.socket.sendall(f"{command}\n".encode('ascii'))
            logger.debug(f"Sent command to LabRecorder: {command}")

            # Read "OK" response to prevent socket buffer pollution
            if expect_response:
                # Save original timeout and set read timeout
                original_timeout = self.socket.gettimeout()
                self.socket.settimeout(3.0)

                try:
                    # Read response from LabRecorder (should be "OK")
                    response = self.socket.recv(1024).decode('ascii').strip()

                    if response == "OK":
                        logger.debug(f"✓ Command '{command}' acknowledged by LabRecorder")
                        print(f"[LabRecorder] ✓ '{command}' acknowledged")
                        return True
                    else:
                        logger.warning(f"Unexpected response for '{command}': {response}")
                        print(f"[LabRecorder] Unexpected response: {response}")
                        # Command was sent, just got unexpected response
                        return True

                except socket.timeout:
                    logger.warning(f"Timeout waiting for response to '{command}'")
                    print(f"[LabRecorder] WARNING: No response to '{command}' (timeout)")
                    # Command was sent, just didn't get response in time
                    return True

                finally:
                    # Restore original timeout
                    self.socket.settimeout(original_timeout)

            return True

        except (socket.error, OSError) as e:
            logger.error(f"Failed to send command '{command}': {e}")
            print(f"[LabRecorder] ERROR: Socket error sending '{command}': {e}")
            print(f"[LabRecorder] The socket connection may be broken. LabRecorder may have been closed or restarted.")
            return False

    def update_streams(self) -> bool:
        """
        Trigger LabRecorder stream discovery refresh.

        Equivalent to clicking the "Update" button in LabRecorder GUI.
        LabRecorder will scan the network for LSL streams (~2 seconds).

        This command tells LabRecorder to actively search for LSL streams
        on the network. Without this, LabRecorder only shows streams that
        were available when it first started.

        IMPORTANT: Wait ~2.5 seconds after calling this before selecting
        streams to allow discovery to complete.

        Returns:
            True if command sent successfully, False otherwise
        """
        success = self.send_command("update")
        if success:
            logger.info("Triggered LabRecorder stream discovery refresh")
            print("[LabRecorder] Triggering stream discovery refresh...")
            print("[LabRecorder] 'update' command sent - LabRecorder scanning for LSL streams")
        else:
            logger.error("Failed to send 'update' command")
            print("[LabRecorder] ERROR: Failed to send 'update' command")
        return success

    def select_all_streams(self) -> bool:
        """
        Select all available LSL streams for recording.

        This will capture ALL LSL streams on the network, including:
        - EEG streams (multiple headsets)
        - Marker streams (experiment events)
        - Face synchrony streams
        - Video streams
        - Any other active LSL streams

        IMPORTANT: This command only selects streams that LabRecorder
        has already discovered. Call this AFTER update_streams() and
        waiting for stream discovery!

        Returns:
            True if command sent successfully, False otherwise
        """
        success = self.send_command("select all")
        if success:
            logger.info("Selected all available LSL streams for recording")
            print("[LabRecorder] 'select all' command sent successfully")
            print("[LabRecorder] Check LabRecorder UI - streams should be selected now")
        else:
            logger.error("Failed to send 'select all' command")
            print("[LabRecorder] ERROR: Failed to send 'select all' command")
        return success

    def start_recording(
        self,
        subject_id: int,
        session: int,
        task_name: str,
        output_dir: str,
        discovery_wait: float = 6.0,
        verify_streams: bool = True
    ) -> bool:
        """
        Configure filename and start LabRecorder recording.

        IMPORTANT: Pre-verifies LSL streams exist before attempting recording.
        This prevents empty recordings caused by LabRecorder not finding any streams.

        Filename format: sub-{ID:03d}_ses-{session:02d}_{task}.xdf
        Example: sub-001_ses-01_DyadicVideoSync.xdf

        Args:
            subject_id: Subject/participant pair ID (e.g., 1, 2, 3)
            session: Session number (e.g., 1, 2, 3)
            task_name: Task/experiment name (e.g., 'DyadicVideoSync')
            output_dir: Directory path for output file
            discovery_wait: Seconds to wait for stream discovery (default: 6.0)
            verify_streams: Pre-check that LSL streams exist (default: True)

        Returns:
            True if recording started successfully, False otherwise
        """
        import time

        if not self.is_connected():
            logger.error("Cannot start recording: not connected to LabRecorder")
            return False

        # Step 0: Pre-verify LSL streams exist (CRITICAL!)
        # Without this check, LabRecorder will start recording with 0 streams
        if verify_streams:
            try:
                import pylsl
                print("[LabRecorder] Step 0/5: Pre-verifying LSL streams exist...")
                logger.info("Pre-checking for LSL streams using pylsl")

                # Scan for streams with 2-second timeout
                streams = pylsl.resolve_streams(2.0)

                if len(streams) == 0:
                    logger.error("No LSL streams found! Cannot start recording.")
                    print("[LabRecorder] ✗ ERROR: No LSL streams detected!")
                    print("[LabRecorder] ")
                    print("[LabRecorder] This is why LabRecorder has nothing to record!")
                    print("[LabRecorder] ")
                    print("[LabRecorder] Troubleshooting:")
                    print("[LabRecorder]   1. Make sure Emotiv software is running with LSL enabled")
                    print("[LabRecorder]   2. Verify experiment creates LSL marker outlet")
                    print("[LabRecorder]   3. Run utilities/lsl_stream_scanner.py to diagnose")
                    print("[LabRecorder]   4. Check firewall isn't blocking LSL multicast")
                    print("[LabRecorder] ")
                    return False
                else:
                    logger.info(f"Pre-check passed: Found {len(streams)} LSL stream(s)")
                    print(f"[LabRecorder] ✓ Pre-check: Found {len(streams)} LSL stream(s):")
                    for stream in streams:
                        print(f"[LabRecorder]   - {stream.name()} ({stream.type()}, {stream.channel_count()} ch)")

            except ImportError:
                logger.warning("pylsl not available - skipping stream pre-check")
                print("[LabRecorder] WARNING: pylsl not installed - cannot pre-verify streams")
                print("[LabRecorder] Install with: pip install pylsl")
            except Exception as e:
                logger.warning(f"Stream pre-check failed: {e}")
                print(f"[LabRecorder] WARNING: Stream pre-check failed: {e}")

        # Step 1: Trigger LabRecorder stream discovery refresh with retry logic
        # Retry up to 3 times with shorter waits (2.5s each) instead of one long wait (6s)
        # This is faster and more reliable for stream discovery
        max_attempts = 3
        retry_wait = 2.5  # Reduced from 6.0s for faster feedback
        
        for attempt in range(1, max_attempts + 1):
            print(f"[LabRecorder] Step 1/5 (attempt {attempt}/{max_attempts}): Triggering stream discovery...")
            if not self.update_streams():
                print("[LabRecorder] WARNING: Failed to send 'update' command")
                print("[LabRecorder] Continuing anyway - streams may not be discovered")
            
            # Step 2: Wait for LabRecorder to discover LSL streams
            print(f"[LabRecorder] Step 2/5: Waiting {retry_wait}s for stream discovery to complete...")
            logger.info(f"Waiting {retry_wait}s for LabRecorder to discover LSL streams (attempt {attempt}/{max_attempts})")
            time.sleep(retry_wait)
            
            # Verify streams were discovered using pylsl
            try:
                import pylsl
                streams = pylsl.resolve_streams(1.0)  # Quick 1s check
                if len(streams) > 0:
                    print(f"[LabRecorder] ✓ Stream discovery confirmed: {len(streams)} stream(s) found")
                    logger.info(f"Stream discovery successful after {attempt} attempt(s)")
                    break  # Success - exit retry loop
                else:
                    if attempt < max_attempts:
                        print(f"[LabRecorder] ⚠ No streams found yet (attempt {attempt}/{max_attempts})")
                        print(f"[LabRecorder] Retrying stream discovery...")
                        logger.warning(f"No streams discovered after {retry_wait}s wait - retrying")
                    else:
                        print(f"[LabRecorder] ✗ WARNING: No streams found after {max_attempts} attempts!")
                        print(f"[LabRecorder] Recording may be empty - verify LSL streams are running")
                        logger.error(f"Stream discovery failed after {max_attempts} attempts")
            except ImportError:
                logger.warning("pylsl not available - cannot verify stream discovery")
                print("[LabRecorder] WARNING: pylsl not installed - cannot verify stream discovery")
                break  # Can't verify, so just proceed after first attempt
            except Exception as e:
                logger.warning(f"Stream verification failed: {e}")
                print(f"[LabRecorder] WARNING: Stream verification failed: {e}")
                break  # Error in verification, proceed anyway

        # Format filename using LabRecorder template syntax
        filename_cmd = (
            f"filename {{root:{output_dir}}} "
            f"{{participant:sub-{subject_id:03d}}} "
            f"{{session:ses-{session:02d}}} "
            f"{{task:{task_name}}}"
        )

        # Step 3: Select all discovered streams
        print("[LabRecorder] Step 3/5: Selecting all available LSL streams...")
        if not self.select_all_streams():
            return False

        time.sleep(1.0)  # Wait for UI to update checkboxes (increased from 0.5s)

        # Step 4: Configure output filename
        print("[LabRecorder] Step 4/5: Configuring output filename...")
        if not self.send_command(filename_cmd):
            return False

        time.sleep(0.3)  # Brief pause between commands

        # Step 5: Start recording
        print("[LabRecorder] Step 5/5: Starting recording...")
        if not self.send_command("start"):
            return False

        self._is_recording = True
        logger.info(
            f"LabRecorder recording started: "
            f"sub-{subject_id:03d}_ses-{session:02d}_{task_name}.xdf"
        )
        print(f"[LabRecorder] ✓ Recording started successfully!")
        print(f"[LabRecorder] Output file: sub-{subject_id:03d}_ses-{session:02d}_{task_name}.xdf")
        print(f"[LabRecorder] Verify LabRecorder UI shows selected streams (should not be empty!)")
        return True

    def stop_recording(self) -> bool:
        """
        Stop current LabRecorder recording.

        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.is_connected():
            logger.warning("Cannot stop recording: not connected to LabRecorder")
            print("[LabRecorder] WARNING: Cannot stop - not connected to LabRecorder")
            return False

        if not self._is_recording:
            logger.warning("Cannot stop recording: not currently recording")
            print("[LabRecorder] WARNING: Not currently recording (already stopped?)")
            return True  # Not an error, just already stopped

        success = self.send_command("stop")
        if success:
            self._is_recording = False
            logger.info("LabRecorder recording stopped")
            print("[LabRecorder] Recording stopped successfully")
        else:
            logger.error("Failed to send stop command to LabRecorder")
            print("[LabRecorder] ERROR: Failed to send stop command")
        return success

    def close(self):
        """
        Close connection to LabRecorder.

        Automatically stops recording if currently active.
        """
        if self._is_recording:
            self.stop_recording()

        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass  # Socket already closed
            self.socket = None
            logger.debug("Closed connection to LabRecorder")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
