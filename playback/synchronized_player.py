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
from playback.sync_engine import SyncEngine
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
        self.actual_start_time: Optional[float] = None
        self.target_start_time: Optional[float] = None

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

        This method schedules video playback on the main thread via pyglet.clock
        and starts audio in a background thread. This ensures OpenGL operations
        (video playback) happen on the main thread while maintaining precise
        timestamp-based synchronization.

        Args:
            sync_timestamp: Target timestamp (from time.perf_counter()) to start playback

        Note:
            - Video playback scheduled via pyglet.clock (main thread)
            - Audio playback started in background thread (thread-safe)
            - Actual start time recorded in self.actual_start_time
        """
        try:
            self.target_start_time = sync_timestamp
            self.actual_start_time = None

            # Calculate delay from now to sync timestamp
            now = time.perf_counter()
            delay = sync_timestamp - now

            if delay <= 0:
                # Target timestamp is in the past - execute immediately
                # This shouldn't happen with STAGE 2 player creation, but provides safety
                print(f"[SyncPlayer] WARNING: Target {sync_timestamp:.6f} is {abs(delay)*1000:.1f}ms "
                      f"in the past, executing immediately")
                self._video_play_callback(0)  # Direct execution, no pyglet queue
            else:
                # Normal case: target is in the future - schedule via Pyglet clock
                print(f"[SyncPlayer] Scheduling playback in {delay*1000:.1f}ms "
                      f"(target: {sync_timestamp:.6f})")

                # Schedule video playback on main thread via Pyglet clock
                # The callback will be executed by Pyglet's event loop on the main thread
                pyglet.clock.schedule_once(self._video_play_callback, delay)

            # Start audio in background thread at the same timestamp
            # sounddevice is thread-safe, so this is OK
            def audio_thread_func():
                # Wait until sync timestamp
                SyncEngine.wait_until_timestamp(sync_timestamp)

                # Start audio
                if self.audio_data is not None and self.samplerate is not None:
                    sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
                    print(f"[SyncPlayer] Audio started on device {self.audio_device_index}")

            # Launch audio thread
            audio_thread = threading.Thread(target=audio_thread_func, daemon=True)
            audio_thread.start()

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
            - Video scheduled via pyglet.clock with provided delay
            - Audio syncs to target_timestamp (not affected by delay parameter)
            - Ensures symmetric timing across all players
        """
        try:
            self.target_start_time = target_timestamp
            self.actual_start_time = None

            if delay <= 0:
                # Delay is negative/zero - execute immediately
                print(f"[SyncPlayer] WARNING: Pre-calculated delay {delay*1000:.1f}ms is ≤0, "
                      f"executing immediately")
                self._video_play_callback(0)  # Direct execution
            else:
                # Normal case: schedule with pre-calculated delay
                print(f"[SyncPlayer] Scheduling playback with delay {delay*1000:.1f}ms "
                      f"(target: {target_timestamp:.6f})")
                pyglet.clock.schedule_once(self._video_play_callback, delay)

            # Start audio in background thread at target timestamp
            # Audio timing is independent of video delay - syncs to absolute timestamp
            def audio_thread_func():
                SyncEngine.wait_until_timestamp(target_timestamp)

                if self.audio_data is not None and self.samplerate is not None:
                    sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
                    print(f"[SyncPlayer] Audio started on device {self.audio_device_index}")

            # Launch audio thread
            audio_thread = threading.Thread(target=audio_thread_func, daemon=True)
            audio_thread.start()

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

    def arm_sync_timestamp(self, sync_timestamp: float):
        """
        ARM PHASE: Pre-configure sync timestamp without starting playback.

        This is STAGE 2 of zero-ISI preparation. Call this 150ms before phase
        transition to prepare the player for instant execution.

        Args:
            sync_timestamp: Target timestamp for synchronized playback

        Example:
            # During fixation (150ms before end)
            player.arm_sync_timestamp(target_timestamp)
            # ... fixation continues ...
            # When fixation ends:
            player.trigger_playback()  # Instant start
        """
        if not self.ready.is_set():
            raise RuntimeError("Player not prepared - call prepare() first")

        self.armed_timestamp = sync_timestamp
        print(f"[SyncPlayer] Armed with timestamp {sync_timestamp:.6f} "
              f"(device {self.audio_device_index})")

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
        """
        try:
            # CRITICAL FIX: Wait for sounddevice to finish with audio buffer
            # sounddevice plays in background thread - must wait before deallocating
            # Without this, clearing self.audio_data while sounddevice is reading it
            # causes heap corruption (exit code 0xC0000374 on Windows)
            if self.audio_data is not None:
                sd.wait()  # Blocks until sounddevice finishes reading the buffer

            # Stop and cleanup video player
            if self.player:
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
