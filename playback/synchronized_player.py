"""
SynchronizedPlayer class for DyadicSync Framework.

Handles synchronized video and audio playback for a single participant.
Ported from WithBaseline.py with improvements.
"""

import threading
import time
import os
import tempfile
from typing import Optional
import sounddevice as sd
import soundfile as sf
import ffmpeg
import pyglet
from playback.sync_engine import SyncEngine


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
        self.ready = threading.Event()
        self.temp_audio_path: Optional[str] = None

        # Arm/trigger pattern for zero-ISI playback (Phase 3)
        self.armed_timestamp: Optional[float] = None

    def prepare(self):
        """
        Prepare video and audio for playback.

        Extracts audio via FFmpeg and loads video via Pyglet.
        Must be called before play_audio() or starting video playback.
        """
        try:
            print(f"[SyncPlayer] Preparing video: {self.video_path}")

            # Extract audio first
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                self.temp_audio_path = temp_file.name

                try:
                    # Extract audio using ffmpeg
                    ffmpeg.input(self.video_path).output(
                        self.temp_audio_path,
                        format='wav',
                        acodec='pcm_s16le',
                        y=None
                    ).run(quiet=True, capture_stdout=True, capture_stderr=True)

                except Exception as e:
                    print(f"[SyncPlayer] FFmpeg error for {self.video_path}: {e}")
                    raise

                try:
                    # Load audio data
                    self.audio_data, self.samplerate = sf.read(self.temp_audio_path, dtype='float32')
                except Exception as e:
                    print(f"[SyncPlayer] Soundfile read error for {self.video_path}: {e}")
                    raise

            # Prepare video
            try:
                source = pyglet.media.load(self.video_path)
                if not source:
                    print(f"[SyncPlayer] Failed to load video source: {self.video_path}")
                    raise RuntimeError("Video source load failed")

                self.player = pyglet.media.Player()
                self.player.queue(source)
                self.player.volume = 0  # Mute video, audio plays separately

                # Test duration access
                test_duration = source.duration
                print(f"[SyncPlayer] Video duration: {test_duration:.2f}s")

                self.ready.set()
                print(f"[SyncPlayer] Successfully prepared video: {self.video_path}")

            except Exception as e:
                print(f"[SyncPlayer] Pyglet video load error for {self.video_path}: {e}")
                raise

        except Exception as e:
            print(f"[SyncPlayer] Error in prepare for {self.video_path}: {e}")
            self.ready.set()  # Set ready even on failure so we don't hang
            raise  # Re-raise to handle in calling code

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

    def play_at_timestamp(self, sync_timestamp: float) -> float:
        """
        Start both video and audio playback at a precise timestamp.

        This method enables timestamp-based synchronization across multiple players.
        It waits until the specified timestamp, then starts both audio and video
        playback simultaneously, returning the actual start time for verification.

        Args:
            sync_timestamp: Target timestamp (from time.perf_counter()) to start playback

        Returns:
            Actual start timestamp (for sync quality verification)

        Example:
            >>> sync_ts = SyncEngine.calculate_sync_timestamp(prep_time_ms=100)
            >>> actual = player.play_at_timestamp(sync_ts)
            >>> drift_ms = (actual - sync_ts) * 1000
            >>> print(f"Started with {drift_ms:.3f}ms drift")
        """
        try:
            # Wait until sync timestamp using hybrid sleep approach
            SyncEngine.wait_until_timestamp(sync_timestamp)

            # Start both audio and video as close together as possible
            # Audio first (non-blocking start)
            if self.audio_data is not None and self.samplerate is not None:
                sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)

            # Start video immediately after
            if self.player:
                self.player.play()

            # Capture actual start time
            actual_start = time.perf_counter()

            print(f"[SyncPlayer] Started at timestamp {actual_start:.6f} "
                  f"(target: {sync_timestamp:.6f}, "
                  f"drift: {(actual_start - sync_timestamp) * 1000:+.3f}ms)")

            return actual_start

        except Exception as e:
            print(f"[SyncPlayer] Error in play_at_timestamp: {e}")
            # Return current time even on failure
            return time.perf_counter()

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

    def trigger_playback(self) -> float:
        """
        TRIGGER PHASE: Start playback at armed timestamp (INSTANT execution).

        This completes the arm/trigger pattern, starting playback at the
        pre-configured sync timestamp. No calculation needed - just trigger.

        Returns:
            Actual start timestamp (for sync quality verification)

        Raises:
            RuntimeError: If player not armed (must call arm_sync_timestamp first)

        Example:
            # Player already prepared and armed during previous phase
            actual_start = player.trigger_playback()  # <1ms execution time
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

        # Use existing play_at_timestamp logic
        actual_start = self.play_at_timestamp(self.armed_timestamp)

        # Clear armed state (one-time use)
        self.armed_timestamp = None

        return actual_start

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

        Releases video player and cleans up temporary audio files.
        """
        try:
            # Stop and cleanup video player
            if self.player:
                self.player.pause()
                self.player.delete()  # Properly releases resources
                self.player = None

            # Clear audio data
            self.audio_data = None
            self.samplerate = None

            # Remove temporary audio file
            if self.temp_audio_path and os.path.exists(self.temp_audio_path):
                os.remove(self.temp_audio_path)
                self.temp_audio_path = None

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
            return self.player.get_texture()
        return None

    def __repr__(self):
        return (
            f"SynchronizedPlayer("
            f"video='{os.path.basename(self.video_path)}', "
            f"audio_device={self.audio_device_index}, "
            f"ready={self.ready.is_set()})"
        )
