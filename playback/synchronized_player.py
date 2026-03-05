"""
SynchronizedPlayer class for DyadicSync Framework.

Handles synchronized video and audio playback for a single participant.
Ported from WithBaseline.py with improvements.
"""

import threading
import time
import os
import io
from typing import Optional
import sounddevice as sd
import soundfile as sf
import ffmpeg
import pyglet
from config.ffmpeg_config import get_ffmpeg_cmd


class SynchronizedPlayer:
    """
    Manages video playback and audio extraction for a single participant.

    Features:
    - Uses FFmpeg to extract audio to temporary WAV files
    - Routes audio to specific device via sounddevice
    - Pyglet handles video rendering with muted player
    - Threading: Audio plays in separate thread, video in main Pyglet loop
    """

    def __init__(self, video_path: str, audio_device_index: int, window: pyglet.window.Window):
        """
        Initialize synchronized player.

        Args:
            video_path: Path to video file
            audio_device_index: Audio device index for output
            window: Pyglet window for video rendering
        """
        self.video_path = video_path
        self.audio_device_index = audio_device_index
        self.window = window
        self.player: Optional[pyglet.media.Player] = None
        self.audio_data = None
        self.samplerate = None
        self.ready = threading.Event()  # Audio extraction complete
        self.player_ready = threading.Event()  # Pyglet player creation complete

        # Arm/trigger pattern for zero-ISI playback (Phase 3)
        self.armed_timestamp: Optional[float] = None

        # Track actual start time for sync verification
        self.actual_start_time: Optional[float] = None  # Video start time
        self.target_start_time: Optional[float] = None

        # Audio-video sync measurement
        self.actual_audio_start_time: Optional[float] = None  # When sd.play() was called
        self.target_audio_start_time: Optional[float] = None  # Target audio timestamp (with lead)

        # Audio thread for timestamp-based sync (tight audio-video sync)
        # Thread is created during arm_sync_timestamp() and busy-waits to
        # audio timestamp (slightly before video) to compensate for audio latency
        self._audio_thread: Optional[threading.Thread] = None

    def prepare(self):
        """
        Prepare audio for playback (BACKGROUND THREAD SAFE).

        Extracts audio via FFmpeg and validates video file.
        This method performs only file I/O operations, no OpenGL context operations.
        Must be called before create_player() and play_audio().

        Note: Player creation is deferred to create_player() which must run on main thread.

        Optimizations:
        - Streams audio directly to memory (no disk I/O)
        - Uses -vn flag to skip video processing
        - Uses -threads auto for parallel decoding
        - Typical extraction time: <300ms for 15-25 second clips (vs ~2000ms previously)
        """
        try:
            prep_start = time.time()
            print(f"[SyncPlayer] Preparing video: {self.video_path}")

            # Validate video file exists
            if not os.path.exists(self.video_path):
                raise FileNotFoundError(
                    f"Video file not found: {self.video_path}\n"
                    f"Please check that the video path is correct and the file exists."
                )

            try:
                # OPTIMIZED: Stream audio directly to memory (no disk I/O)
                # Extract audio using FFmpeg with optimization flags:
                #   -vn: Skip video processing entirely (audio only)
                #   -threads auto: Enable parallel decoding
                #   -map 0:a:0: Select first audio stream only
                # Output to pipe (stdout) instead of writing to disk
                stdout, stderr = (
                    ffmpeg
                    .input(self.video_path)
                    .output('pipe:', format='wav', acodec='pcm_s16le',
                           vn=None,  # Skip video processing
                           threads='auto',  # Multi-threaded decoding
                           map='0:a:0')  # First audio stream only
                    .run(cmd=get_ffmpeg_cmd(), capture_stdout=True, capture_stderr=True)
                )

                # Load audio data directly from memory buffer (no disk I/O)
                audio_buffer = io.BytesIO(stdout)
                self.audio_data, self.samplerate = sf.read(audio_buffer, dtype='float32')

                # Log audio extraction details for debugging
                audio_channels = self.audio_data.shape[1] if len(self.audio_data.shape) > 1 else 1
                audio_duration = len(self.audio_data) / self.samplerate
                print(f"[SyncPlayer] Audio extracted: {self.samplerate}Hz, {audio_channels} channel(s), "
                      f"duration={audio_duration:.2f}s, device={self.audio_device_index}")

            except ffmpeg.Error as e:
                # FFmpeg-specific error - show stderr details
                error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
                print(f"[SyncPlayer] FFmpeg error for {self.video_path}:")
                print(f"  Error details: {error_msg}")
                raise RuntimeError(f"FFmpeg failed to extract audio: {error_msg}")
            except Exception as e:
                print(f"[SyncPlayer] FFmpeg error for {self.video_path}: {e}")
                raise

            prep_duration = (time.time() - prep_start) * 1000  # Convert to ms

            # Set ready flag - audio is prepared
            # Note: Player creation happens later in create_player() on main thread
            self.ready.set()
            print(f"[SyncPlayer] Successfully prepared audio for: {self.video_path} "
                  f"(extraction took {prep_duration:.0f}ms)")

        except Exception as e:
            print(f"[SyncPlayer] Error in prepare for {self.video_path}: {e}")
            # DO NOT set ready flag on failure - let safety checks catch this
            # The ready flag should only be set when preparation succeeds
            raise  # Re-raise to handle in calling code

    def create_player(self):
        """
        Create Pyglet media player (MAIN THREAD ONLY).

        This method MUST be called on the main thread (Pyglet event loop thread).
        It performs OpenGL context operations and creates the video player.
        Can be called in parallel with prepare() - does not depend on audio extraction.

        Note:
            Sets player_ready flag when complete. This runs independently of
            audio extraction (ready flag), enabling parallel STAGE 1 + STAGE 2.
        """
        try:
            create_start = time.time()
            print(f"[SyncPlayer] Creating player on main thread: {self.video_path}")

            # CRITICAL: Switch to window's OpenGL context before creating player
            # This ensures textures and OpenGL resources are bound to the correct context
            # This MUST happen on the main thread (Pyglet event loop thread)
            self.window.switch_to()

            source = pyglet.media.load(self.video_path)
            if not source:
                print(f"[SyncPlayer] Failed to load video source: {self.video_path}")
                raise RuntimeError("Video source load failed")

            self.player = pyglet.media.Player()
            self.player.queue(source)
            self.player.volume = 0  # Mute video, audio plays separately

            # === DECODER WARM-UP: Prevent first-frame motion artifacts ===
            # seek(0) forces decoder to find first keyframe and fully initialize
            # reference buffers before playback starts.
            if source.video_format:
                self.player.seek(0)

            # Test duration access
            test_duration = source.duration

            create_duration = (time.time() - create_start) * 1000  # Convert to ms
            print(f"[SyncPlayer] Video duration: {test_duration:.2f}s")
            print(f"[SyncPlayer] Successfully created player: {self.video_path} "
                  f"(creation took {create_duration:.0f}ms)")

            # Set player_ready flag - Pyglet player is ready
            self.player_ready.set()

        except Exception as e:
            print(f"[SyncPlayer] Pyglet player creation error for {self.video_path}: {e}")
            # DO NOT set player_ready flag on failure
            raise

    def play_audio(self):
        """
        Play audio on the specified device.

        This method blocks until audio completes (uses sd.wait()).
        Designed to run in a separate thread.
        """
        try:
            # Make sure we have audio data
            if self.audio_data is None or self.samplerate is None:
                print(f"[SyncPlayer] No audio data available for device {self.audio_device_index}")
                return

            print(f"[SyncPlayer] Starting audio on device {self.audio_device_index}")

            # Play and wait to prevent the audio stream from being terminated
            sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
            sd.wait()  # This ensures the audio plays completely

            print(f"[SyncPlayer] Audio finished on device {self.audio_device_index}")

        except Exception as e:
            print(f"[SyncPlayer] Error playing audio on device {self.audio_device_index}: {e}")

    def _video_play_callback(self, dt):
        """
        Callback executed by Pyglet clock on main thread to start video playback.

        Args:
            dt: Delta time from Pyglet clock (not used but required by Pyglet)
        """
        try:
            # Start video playback on main thread (OpenGL context is active)
            if self.player:
                self.player.play()

            # Record actual start time
            self.actual_start_time = time.perf_counter()

            # Calculate drift
            if self.target_start_time:
                drift_ms = (self.actual_start_time - self.target_start_time) * 1000
                print(f"[SyncPlayer] Video started at {self.actual_start_time:.6f} "
                      f"(target: {self.target_start_time:.6f}, "
                      f"drift: {drift_ms:+.3f}ms)")
            else:
                print(f"[SyncPlayer] Video started at {self.actual_start_time:.6f}")

        except Exception as e:
            print(f"[SyncPlayer] Error in video play callback: {e}")
            self.actual_start_time = time.perf_counter()

    def schedule_play_at_timestamp(self, sync_timestamp: float):
        """
        Schedule video and audio playback at a precise timestamp using Pyglet clock.

        This method schedules a combined callback on the main thread via pyglet.clock
        that starts both video and audio together. This ensures OpenGL operations
        (video playback) happen on the main thread while audio starts from the same
        trigger point, eliminating timing race conditions.

        Args:
            sync_timestamp: Target timestamp (from time.perf_counter()) to start playback

        Note:
            - Combined video+audio callback scheduled via pyglet.clock (main thread)
            - Audio thread spawned from callback (starts immediately, no independent wait)
            - Actual start time recorded in self.actual_start_time
        """
        try:
            self.target_start_time = sync_timestamp
            self.actual_start_time = None

            # Calculate delay from now to sync timestamp
            now = time.perf_counter()
            delay = sync_timestamp - now

            # AUDIO-VIDEO SYNC FIX: Combined callback that starts both video and audio
            # This ensures they share the same trigger point (no race condition)
            def combined_play_callback(dt):
                """Combined callback that starts video and audio together."""
                try:
                    # Start video playback on main thread (OpenGL context is active)
                    if self.player:
                        self.player.play()

                    # Record actual start time
                    self.actual_start_time = time.perf_counter()

                    # Calculate drift
                    if self.target_start_time:
                        drift_ms = (self.actual_start_time - self.target_start_time) * 1000
                        print(f"[SyncPlayer] Video started at {self.actual_start_time:.6f} "
                              f"(target: {self.target_start_time:.6f}, "
                              f"drift: {drift_ms:+.3f}ms)")
                    else:
                        print(f"[SyncPlayer] Video started at {self.actual_start_time:.6f}")

                    # AUDIO-VIDEO SYNC FIX: Start audio immediately after video (same callback)
                    # No independent waiting - audio starts from the same trigger point
                    if self.audio_data is not None and self.samplerate is not None:
                        def audio_play_func():
                            """Audio thread: start playback immediately and block until complete."""
                            sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
                            print(f"[SyncPlayer] Audio started on device {self.audio_device_index}")

                            # CRITICAL: Block until audio completes before thread exits
                            sd.wait()
                            print(f"[SyncPlayer] Audio finished on device {self.audio_device_index}")

                        # Launch audio thread (non-daemon for proper cleanup)
                        audio_thread = threading.Thread(target=audio_play_func, daemon=False)
                        audio_thread.start()

                        # Store thread reference for cleanup in stop()
                        if not hasattr(self, '_audio_threads'):
                            self._audio_threads = []
                        self._audio_threads.append(audio_thread)

                except Exception as e:
                    print(f"[SyncPlayer] Error in combined play callback: {e}")
                    self.actual_start_time = time.perf_counter()

            if delay <= 0:
                # Target timestamp is in the past - execute immediately
                print(f"[SyncPlayer] WARNING: Target {sync_timestamp:.6f} is {abs(delay)*1000:.1f}ms "
                      f"in the past, executing immediately")
                combined_play_callback(0)  # Direct execution, no pyglet queue
            else:
                # Normal case: target is in the future - schedule via Pyglet clock
                print(f"[SyncPlayer] Scheduling playback in {delay*1000:.1f}ms "
                      f"(target: {sync_timestamp:.6f})")
                pyglet.clock.schedule_once(combined_play_callback, delay)

        except Exception as e:
            print(f"[SyncPlayer] Error in schedule_play_at_timestamp: {e}")
            self.actual_start_time = time.perf_counter()

    def get_actual_start_time(self) -> Optional[float]:
        """
        Get the actual start time after playback was triggered.

        Returns:
            Actual start timestamp or None if playback hasn't started yet
        """
        return self.actual_start_time

    def get_audio_video_delay(self) -> Optional[dict]:
        """
        Get the measured audio-video delay after playback started.

        Returns:
            Dictionary with timing metrics, or None if not yet available:
            {
                'audio_start': float,      # Actual audio start timestamp
                'video_start': float,      # Actual video start timestamp
                'delay_ms': float,         # Audio-to-video delay (positive = audio first)
                'audio_lead_ms': float,    # Configured audio lead time
                'effective_lead_ms': float # Actual measured lead (what we achieved)
            }
        """
        if self.actual_audio_start_time is None or self.actual_start_time is None:
            return None

        # Delay = video_start - audio_start
        # Positive = audio started first (desired)
        # Negative = video started first (audio behind)
        delay_ms = (self.actual_start_time - self.actual_audio_start_time) * 1000

        return {
            'audio_start': self.actual_audio_start_time,
            'video_start': self.actual_start_time,
            'delay_ms': delay_ms,
            'audio_lead_ms': self.DEFAULT_AUDIO_LEAD_MS,
            'effective_lead_ms': delay_ms  # What we actually achieved
        }

    def schedule_play_at_delay(self, target_timestamp: float, delay: float):
        """
        Schedule playback with pre-calculated delay (eliminates sequential drift).

        This method accepts a pre-calculated delay instead of recalculating 'now'.
        Used by SyncEngine to ensure all players calculate delays from the same
        baseline timestamp, eliminating 1-2ms asymmetry between Player 1 and Player 2.

        Args:
            target_timestamp: Target sync timestamp (for logging and audio sync)
            delay: Pre-calculated delay in seconds (target_timestamp - now)

        Note:
            - Combined video+audio callback scheduled via pyglet.clock with provided delay
            - Audio thread spawned from callback (starts immediately, no independent wait)
            - Ensures symmetric timing across all players
        """
        try:
            self.target_start_time = target_timestamp
            self.actual_start_time = None

            # AUDIO-VIDEO SYNC FIX: Combined callback that starts both video and audio
            # This ensures they share the same trigger point (no race condition)
            def combined_play_callback(dt):
                """Combined callback that starts video and audio together."""
                try:
                    # Start video playback on main thread (OpenGL context is active)
                    if self.player:
                        self.player.play()

                    # Record actual start time
                    self.actual_start_time = time.perf_counter()

                    # Calculate drift
                    if self.target_start_time:
                        drift_ms = (self.actual_start_time - self.target_start_time) * 1000
                        print(f"[SyncPlayer] Video started at {self.actual_start_time:.6f} "
                              f"(target: {self.target_start_time:.6f}, "
                              f"drift: {drift_ms:+.3f}ms)")
                    else:
                        print(f"[SyncPlayer] Video started at {self.actual_start_time:.6f}")

                    # AUDIO-VIDEO SYNC FIX: Start audio immediately after video (same callback)
                    # No independent waiting - audio starts from the same trigger point
                    if self.audio_data is not None and self.samplerate is not None:
                        def audio_play_func():
                            """Audio thread: start playback immediately and block until complete."""
                            sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
                            print(f"[SyncPlayer] Audio started on device {self.audio_device_index}")

                            # CRITICAL: Block until audio completes before thread exits
                            sd.wait()
                            print(f"[SyncPlayer] Audio finished on device {self.audio_device_index}")

                        # Launch audio thread (non-daemon for proper cleanup)
                        audio_thread = threading.Thread(target=audio_play_func, daemon=False)
                        audio_thread.start()

                        # Store thread reference for cleanup in stop()
                        if not hasattr(self, '_audio_threads'):
                            self._audio_threads = []
                        self._audio_threads.append(audio_thread)

                except Exception as e:
                    print(f"[SyncPlayer] Error in combined play callback: {e}")
                    self.actual_start_time = time.perf_counter()

            if delay <= 0:
                # Delay is negative/zero - execute immediately
                print(f"[SyncPlayer] WARNING: Pre-calculated delay {delay*1000:.1f}ms is ≤0, "
                      f"executing immediately")
                combined_play_callback(0)  # Direct execution
            else:
                # Normal case: schedule with pre-calculated delay
                print(f"[SyncPlayer] Scheduling playback with delay {delay*1000:.1f}ms "
                      f"(target: {target_timestamp:.6f})")
                pyglet.clock.schedule_once(combined_play_callback, delay)

        except Exception as e:
            print(f"[SyncPlayer] Error in schedule_play_at_delay: {e}")
            self.actual_start_time = time.perf_counter()

    def play_at_timestamp(self, sync_timestamp: float) -> float:
        """
        DEPRECATED: Use schedule_play_at_timestamp() instead.

        Legacy method kept for compatibility. Calls the new scheduling method
        and waits for playback to start before returning.

        Args:
            sync_timestamp: Target timestamp (from time.perf_counter()) to start playback

        Returns:
            Actual start timestamp (for sync quality verification)
        """
        # Call new scheduling method
        self.schedule_play_at_timestamp(sync_timestamp)

        # Wait for playback to actually start (with timeout)
        timeout = 5.0  # 5 second timeout
        start_wait = time.perf_counter()
        while self.actual_start_time is None:
            if time.perf_counter() - start_wait > timeout:
                print(f"[SyncPlayer] Warning: Timeout waiting for playback to start")
                return time.perf_counter()
            time.sleep(0.001)  # Small sleep to avoid busy-waiting

        return self.actual_start_time

    # Default audio lead time (ms) - compensates for audio path latency
    # (sd.play() init + PortAudio buffer fill + thread scheduling)
    DEFAULT_AUDIO_LEAD_MS = 500.0

    def arm_sync_timestamp(self, sync_timestamp: float, audio_lead_ms: float = None):
        """
        ARM PHASE: Pre-configure sync timestamp AND start audio thread with lead time.

        This is STAGE 2 of zero-ISI preparation. Call this 150ms before phase
        transition to prepare the player for instant execution.

        The audio thread busy-waits to (sync_timestamp - audio_lead_ms), giving
        audio a head start to compensate for:
        - sd.play() initialization latency
        - PortAudio buffer fill time
        - Any remaining thread scheduling overhead

        Args:
            sync_timestamp: Target timestamp for VIDEO playback
            audio_lead_ms: How many ms BEFORE video the audio should start.
                          Default: 5ms. Adjust if audio is still behind/ahead.

        Example:
            # During fixation (150ms before end)
            player.arm_sync_timestamp(target_timestamp)
            # ... fixation continues ...
            # When fixation ends, video callback fires and audio is already playing
        """
        if not self.ready.is_set():
            raise RuntimeError("Player not prepared - call prepare() first")

        # Use default if not specified
        if audio_lead_ms is None:
            audio_lead_ms = self.DEFAULT_AUDIO_LEAD_MS

        self.armed_timestamp = sync_timestamp

        # Calculate audio start timestamp (earlier than video to compensate for latency)
        audio_timestamp = sync_timestamp - (audio_lead_ms / 1000.0)
        self.target_audio_start_time = audio_timestamp

        if self.audio_data is not None and self.samplerate is not None:
            # Reference to self for closure
            player_self = self

            def audio_wait_and_play():
                """Audio thread: busy-wait to audio_timestamp, then play."""
                # Import here to avoid circular import
                from playback.sync_engine import SyncEngine

                # Precise busy-wait to audio timestamp (EARLIER than video)
                SyncEngine.wait_until_timestamp(audio_timestamp)

                # Record actual audio start time BEFORE sd.play() call
                player_self.actual_audio_start_time = time.perf_counter()

                # Start audio immediately after busy-wait completes
                sd.play(player_self.audio_data, player_self.samplerate, device=player_self.audio_device_index)

                # Log with timing info
                audio_drift_ms = (player_self.actual_audio_start_time - audio_timestamp) * 1000
                print(f"[SyncPlayer] Audio started on device {player_self.audio_device_index} "
                      f"at {player_self.actual_audio_start_time:.6f} "
                      f"(target: {audio_timestamp:.6f}, drift: {audio_drift_ms:+.3f}ms)")

                # Block until audio completes
                sd.wait()
                print(f"[SyncPlayer] Audio finished on device {self.audio_device_index}")

            self._audio_thread = threading.Thread(target=audio_wait_and_play, daemon=False)
            self._audio_thread.start()  # Thread starts busy-waiting immediately

            # Store for cleanup
            if not hasattr(self, '_audio_threads'):
                self._audio_threads = []
            self._audio_threads.append(self._audio_thread)

            print(f"[SyncPlayer] Armed: video at {sync_timestamp:.6f}, "
                  f"audio at {audio_timestamp:.6f} ({audio_lead_ms:.1f}ms lead), "
                  f"device {self.audio_device_index}")
        else:
            print(f"[SyncPlayer] Armed with timestamp {sync_timestamp:.6f} "
                  f"(device {self.audio_device_index}, no audio)")

    def trigger_playback(self):
        """
        TRIGGER PHASE: Schedule playback at armed timestamp using Pyglet clock.

        This completes the arm/trigger pattern, scheduling playback at the
        pre-configured sync timestamp. Video playback is scheduled on the main
        thread via pyglet.clock for OpenGL safety.

        Note:
            Returns immediately after scheduling. Use get_actual_start_time()
            to retrieve the actual start time after playback begins.

        Raises:
            RuntimeError: If player not armed (must call arm_sync_timestamp first)

        Example:
            # Player already prepared and armed during previous phase
            player.trigger_playback()  # Schedules playback, returns immediately
            # Later, retrieve actual start time:
            actual_start = player.get_actual_start_time()
        """
        if self.armed_timestamp is None:
            raise RuntimeError(
                "Player not armed - call arm_sync_timestamp() first "
                "(should happen during STAGE 2 of previous phase)"
            )

        # HIGH PRIORITY FIX #7: Validate player state before triggering
        if not self.ready.is_set():
            raise RuntimeError(
                "Player not ready - resources may have been deallocated "
                "between arm and trigger. Prepare() may have failed."
            )

        if not self.player or self.audio_data is None:
            raise RuntimeError(
                "Player resources invalid - video or audio not loaded. "
                "Check that prepare() completed successfully."
            )

        # Use new scheduling method (OpenGL-safe)
        self.schedule_play_at_timestamp(self.armed_timestamp)

        # Clear armed state (one-time use)
        self.armed_timestamp = None

    def start(self):
        """
        Verify player is ready for playback.

        Raises:
            RuntimeError: If player not prepared
        """
        if not self.ready.is_set():
            raise RuntimeError("Player not prepared")

        print(f"[SyncPlayer] Player ready for device {self.audio_device_index}")

    def stop(self):
        """
        Stop playback and cleanup resources.

        Releases video player and clears audio data from memory.

        CRITICAL: Waits for sounddevice audio completion before clearing buffers
        to prevent heap corruption (sounddevice reads from buffer in background thread).

        CRITICAL FIX: Explicitly stops sounddevice and joins audio threads to prevent
        DLL_INIT_FAILED (0xC0000141) caused by PortAudio DLL in inconsistent state.
        """
        try:
            # CRITICAL FIX: Join audio threads BEFORE calling sd.stop()
            # This allows threads to complete sd.wait() naturally without interruption
            # Prevents access violation when sd.stop() kills streams while threads are still running
            # Note: Audio threads now use busy-wait to timestamp, so they will complete
            # naturally after audio finishes (no Event signaling needed)
            if hasattr(self, '_audio_threads'):
                for thread in self._audio_threads:
                    if thread.is_alive():
                        # Wait for thread to complete naturally (thread will finish sd.wait() internally)
                        thread.join(timeout=10.0)  # Increased to 10s for longer audio clips
                        if thread.is_alive():
                            print(f"[SyncPlayer] WARNING: Audio thread did not terminate within 10s timeout")

                # Clear thread list after joining
                self._audio_threads = []

            # Clear thread reference
            self._audio_thread = None

            # NOTE: sd.stop() is NOT called here because it's a GLOBAL operation
            # that stops ALL sounddevice streams (all players, all devices).
            # Instead, the caller (e.g., finish_phase in video_phase.py) coordinates
            # stopping all players first, then calls sd.stop() ONCE after ALL audio
            # threads from ALL players have finished. This prevents interrupting
            # other players' audio threads that are still in sd.wait().

            # Stop and cleanup video player
            if self.player:
                # CRITICAL: Switch to correct OpenGL context before deleting player
                # OpenGL resources must be deleted in the same context they were created in
                # Without this, heap corruption (0xC0000374) occurs on subsequent trials
                self.window.switch_to()
                self.player.pause()
                self.player.delete()  # Properly releases resources
                self.player = None

            # NOW safe to clear audio data (sounddevice no longer referencing it)
            self.audio_data = None
            self.samplerate = None

            print(f"[SyncPlayer] Stopped player for video: {self.video_path}")

        except Exception as e:
            print(f"[SyncPlayer] Error in stop: {e}")

    def get_texture(self):
        """
        Get current video texture for rendering.

        Returns:
            Pyglet texture or None
        """
        if self.player and self.player.source:
            return self.player.texture
        return None

    def __repr__(self):
        return (
            f"SynchronizedPlayer("
            f"video='{os.path.basename(self.video_path)}', "
            f"audio_device={self.audio_device_index}, "
            f"ready={self.ready.is_set()})"
        )
