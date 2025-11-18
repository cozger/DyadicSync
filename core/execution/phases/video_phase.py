"""
VideoPhase implementation for DyadicSync Framework.

Plays synchronized videos to two participants with zero-ISI preloading.

Phase 3 Enhancement:
- Two-stage prepare: Resource loading (STAGE 1) + Sync preparation (STAGE 2)
- Eliminates ISI gaps by preloading during previous phase
- Instant execution via arm/trigger pattern
"""

from typing import Dict, List, Set, Any, Optional
import time
import os
import concurrent.futures
import pyglet
import logging
from ..phase import Phase
from playback.sync_engine import SyncEngine

logger = logging.getLogger(__name__)


class VideoPhase(Phase):
    """
    Phase for playing synchronized videos to two participants.

    Features:
    - Timestamp-based synchronization (to be implemented with SyncEngine)
    - Per-participant video selection
    - Automatic duration detection
    - LSL markers for video start/end
    - Template variable support ({video1}, {video2})
    """

    def __init__(
        self,
        name: str = "Video Playback",
        participant_1_video: str = "",
        participant_2_video: str = "",
        auto_advance: bool = True
    ):
        """
        Initialize video phase.

        Args:
            name: Phase name
            participant_1_video: Path to P1 video (or "{column}" template)
            participant_2_video: Path to P2 video (or "{column}" template)
            auto_advance: Automatically proceed when videos finish

        Note:
            Markers are configured via marker_bindings list.
            Common events: video_start, video_p1_end, video_p2_end, video_both_complete
        """
        super().__init__(name)
        self.participant_1_video = participant_1_video
        self.participant_2_video = participant_2_video
        self.auto_advance = auto_advance

        # Pre-loaded players (Phase 3: Zero-ISI feature)
        # These are created during _prepare_impl() and used during execute()
        self.player1 = None
        self.player2 = None

    def needs_preload(self) -> bool:
        """Videos require preloading to eliminate ISI."""
        return True

    def _prepare_impl(self, device_manager):
        """
        STAGE 1: Load video and audio resources (called during PREVIOUS phase).

        This method runs in a background thread during the previous phase
        (fixation or rating), loading both videos and extracting audio to
        eliminate the ~2 second ISI gap.

        Timing: Should complete within 2 seconds (parallelized loading)
        """
        logger.info(f"VideoPhase STAGE 1: Loading resources for {os.path.basename(self.participant_1_video)}")

        # Debug logging to track video paths in prepare
        print(f"[VideoPhase._prepare_impl] DEBUG Preparation:")
        print(f"  Phase name: {self.name}")
        print(f"  P1 video path: '{self.participant_1_video}'")
        print(f"  P2 video path: '{self.participant_2_video}'")

        # Create synchronized players
        self.player1 = device_manager.create_video_player(
            video_path=self.participant_1_video,
            display_id=0,
            audio_device_id=device_manager.audio_device_p1
        )
        self.player2 = device_manager.create_video_player(
            video_path=self.participant_2_video,
            display_id=1,
            audio_device_id=device_manager.audio_device_p2
        )

        # Prepare both players IN PARALLEL (halves loading time)
        prep_start = time.time()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(self.player1.prepare)
            future2 = executor.submit(self.player2.prepare)
            # Wait for both to complete
            concurrent.futures.wait([future1, future2])

        prep_duration = time.time() - prep_start
        logger.info(f"VideoPhase STAGE 1: Resources loaded in {prep_duration:.2f}s")

    def _prepare_sync_impl(self, prep_time_ms: int):
        """
        STAGE 2: Create Pyglet players and prepare synchronization (called 150ms before execute()).

        This method creates the Pyglet video players on the main thread (OpenGL context required),
        then calculates the sync timestamp and arms both players for instant execution.
        Must be called during the final 150ms of the previous phase (e.g., during fixation).

        CRITICAL: Player creation happens HERE (not in execute()) to ensure sync timestamp
        is calculated AFTER all overhead, guaranteeing timestamp is always in the future.

        PARALLEL EXECUTION: This method runs concurrently with STAGE 1 (audio extraction).
        Both audio and video loading happen in parallel for maximum efficiency.

        Timing: Completes in ~100ms (Pyglet player creation + calculations)
        """
        if not self.player1 or not self.player2:
            raise RuntimeError(
                "VideoPhase STAGE 2 error: Resources not loaded. "
                "Must call prepare() (STAGE 1) first."
            )

        logger.info(f"VideoPhase STAGE 2: Creating Pyglet players on main thread...")

        # CRITICAL: Create Pyglet players on main thread (OpenGL context required)
        # This MUST happen on the main thread, not in background preparation
        # Moving this to STAGE 2 ensures sync timestamp accounts for creation time
        # NOTE: Player creation is INDEPENDENT of audio extraction - runs in parallel!
        try:
            self.player1.create_player()
            self.player2.create_player()
            logger.info(f"VideoPhase STAGE 2: Pyglet players created successfully")
        except Exception as e:
            raise RuntimeError(f"Failed to create Pyglet players in STAGE 2: {e}")

        # NOW verify both audio extraction AND player creation completed
        # Wait for BOTH flags to be set (with timeout for safety)
        import time
        timeout = 5.0  # 5 second timeout (should be <500ms typically)
        wait_start = time.time()

        while True:
            audio_ready = self.player1.ready.is_set() and self.player2.ready.is_set()
            players_ready = self.player1.player_ready.is_set() and self.player2.player_ready.is_set()

            if audio_ready and players_ready:
                logger.info(f"VideoPhase STAGE 2: Both audio and players ready")
                break

            if time.time() - wait_start > timeout:
                # Timeout - provide detailed error message
                p1_audio = "ready" if self.player1.ready.is_set() else "NOT READY"
                p2_audio = "ready" if self.player2.ready.is_set() else "NOT READY"
                p1_player = "ready" if self.player1.player_ready.is_set() else "NOT READY"
                p2_player = "ready" if self.player2.player_ready.is_set() else "NOT READY"

                raise RuntimeError(
                    f"VideoPhase STAGE 2 error: Timeout waiting for preparation.\n"
                    f"  P1 audio: {p1_audio}, P1 player: {p1_player}\n"
                    f"  P2 audio: {p2_audio}, P2 player: {p2_player}\n"
                    f"  This indicates STAGE 1 audio extraction is taking too long (>{timeout}s)"
                )

            time.sleep(0.01)  # Small sleep to avoid busy-waiting

        logger.info(f"VideoPhase STAGE 2: Calculating sync timestamp with {prep_time_ms}ms prep time")

        # Calculate future sync timestamp (AFTER player creation overhead)
        # This ensures timestamp is always in the future when trigger_playback() is called
        sync_timestamp = SyncEngine.calculate_sync_timestamp(prep_time_ms)

        # Arm both players with the sync timestamp (instant execution later)
        self.player1.arm_sync_timestamp(sync_timestamp)
        self.player2.arm_sync_timestamp(sync_timestamp)

        logger.info(f"VideoPhase STAGE 2: Players created and armed for t={sync_timestamp:.6f}")

    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None,
                on_complete=None) -> None:
        """
        Execute video playback with ZERO-ISI instant start (non-blocking, callback-based).

        Players should already be prepared (STAGE 1) and armed (STAGE 2)
        by the time this method is called. This enables instant execution
        with <5ms onset delay.

        Args:
            device_manager: DeviceManager instance (for window access)
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for marker template resolution
                       (e.g., {'trial_index': 3, 'type': 'happy', ...})
            on_complete: Callback function(result_dict) called when phase completes

        Events emitted:
            - video_start: When both videos begin playback
            - video_p1_end: When P1's video completes
            - video_p2_end: When P2's video completes
            - video_both_complete: When both videos have finished

        Note:
            This method is non-blocking. It schedules video playback and returns immediately.
            Results are passed to on_complete callback when both videos finish.
        """
        scheduled_start = time.time()

        # Verify players are prepared (should already be done during previous phase)
        if not self.player1 or not self.player2:
            raise RuntimeError(
                "VideoPhase execute() called without preparation! "
                "Players should be loaded during STAGE 1 (previous phase). "
                "This indicates a problem with the preloading orchestration."
            )

        # HIGH PRIORITY FIX #4: Verify players are in ready state
        if not self.player1.ready.is_set() or not self.player2.ready.is_set():
            raise RuntimeError(
                "VideoPhase execute() called but players not ready! "
                "Player 1 ready: {}, Player 2 ready: {}. "
                "Preparation may have failed - check logs for errors during prepare().".format(
                    self.player1.ready.is_set(), self.player2.ready.is_set()
                )
            )

        # Verify Pyglet players were created in STAGE 2
        if not self.player1.player or not self.player2.player:
            raise RuntimeError(
                "VideoPhase execute() called but Pyglet players not created! "
                "Players should be created during STAGE 2 (150ms before execute). "
                "This indicates STAGE 2 preparation was skipped or failed."
            )

        # Verify players are armed (should already be done in STAGE 2)
        if not self.player1.armed_timestamp or not self.player2.armed_timestamp:
            raise RuntimeError(
                "VideoPhase execute() called without sync preparation! "
                "Players should be armed during STAGE 2 (150ms before execute). "
                "This indicates a problem with the late-stage preload timing."
            )

        logger.info(f"VideoPhase execute(): Players created and armed in STAGE 2, triggering instant playback")

        # Get windows
        window1 = device_manager.window1
        window2 = device_manager.window2

        # Track completion
        completed_videos = {'count': 0}
        player1_ended = {'value': False}
        player2_ended = {'value': False}

        # Fallback timer references for cleanup
        check_player1_time_func = None
        check_player2_time_func = None

        def finish_phase():
            """Cleanup and complete phase."""
            end_time = time.time()

            # Send video_both_complete event markers
            self.send_event_markers("video_both_complete", lsl_outlet, trial_data)

            # Cleanup
            if check_player1_time_func:
                pyglet.clock.unschedule(check_player1_time_func)
            if check_player2_time_func:
                pyglet.clock.unschedule(check_player2_time_func)

            self.player1.stop()
            self.player2.stop()

            # Clear player references for next trial
            self.player1 = None
            self.player2 = None

            # CRITICAL FIX: Reset preload state flags for next trial
            # Without this, second trial will skip preparation and crash
            self._is_prepared = False
            self._is_sync_prepared = False

            # Prepare result
            result = {
                'duration': end_time - scheduled_start,
                'video1_path': self.participant_1_video,
                'video2_path': self.participant_2_video,
                'scheduled_start': scheduled_start,
                'actual_start': actual_start,
                'end_time': end_time,
                'onset_delay_ms': onset_delay_ms,  # Phase 3: ISI metric (target: <5ms)
                'sync_quality': {
                    'max_drift_ms': sync_result['max_drift_ms'],
                    'spread_ms': sync_result['spread_ms'],
                    'success': sync_result['success'],
                    'sync_timestamp': sync_result['sync_timestamp']
                }
            }

            # Call completion callback
            if on_complete:
                on_complete(result)

        def mark_video_complete(player_num):
            """Mark a video as complete, send marker, and finish if both done."""
            completed_videos['count'] += 1
            logger.debug(f"Player {player_num} completed ({completed_videos['count']}/2)")

            # Send participant-specific end marker
            if player_num == 1:
                self.send_event_markers("video_p1_end", lsl_outlet, trial_data)
            elif player_num == 2:
                self.send_event_markers("video_p2_end", lsl_outlet, trial_data)

            # Finish phase when both complete
            if completed_videos['count'] >= 2:
                finish_phase()

        # Set up draw handlers to render video textures
        @window1.event
        def on_draw():
            window1.clear()
            # Check if player exists (may be None after cleanup during sd.wait() blocking)
            if self.player1:
                texture = self.player1.get_texture()
                if texture:
                    # Render texture to fill window
                    texture.blit(0, 0, width=window1.width, height=window1.height)

        @window2.event
        def on_draw():
            window2.clear()
            # Check if player exists (may be None after cleanup during sd.wait() blocking)
            if self.player2:
                texture = self.player2.get_texture()
                if texture:
                    # Render texture to fill window
                    texture.blit(0, 0, width=window2.width, height=window2.height)

        # Set up end-of-stream handlers
        # Defensive check: Verify player objects are valid before registering events
        if not self.player1.player:
            raise RuntimeError(
                f"Player 1 internal player is None - video preparation failed!\n"
                f"Video path: {self.participant_1_video}\n"
                f"Check FFmpeg errors above for details."
            )
        if not self.player2.player:
            raise RuntimeError(
                f"Player 2 internal player is None - video preparation failed!\n"
                f"Video path: {self.participant_2_video}\n"
                f"Check FFmpeg errors above for details."
            )

        @self.player1.player.event
        def on_eos():
            if not player1_ended['value']:
                player1_ended['value'] = True
                mark_video_complete(1)

        @self.player2.player.event
        def on_eos():
            if not player2_ended['value']:
                player2_ended['value'] = True
                mark_video_complete(2)

        # Fallback timers in case EOS doesn't fire
        def check_player1_time(dt):
            if self.player1 and self.player1.player and self.player1.player.source:
                if self.player1.player.time >= self.player1.player.source.duration - 0.1:
                    if not player1_ended['value']:
                        player1_ended['value'] = True
                        mark_video_complete(1)
                        pyglet.clock.unschedule(check_player1_time)

        def check_player2_time(dt):
            if self.player2 and self.player2.player and self.player2.player.source:
                if self.player2.player.time >= self.player2.player.source.duration - 0.1:
                    if not player2_ended['value']:
                        player2_ended['value'] = True
                        mark_video_complete(2)
                        pyglet.clock.unschedule(check_player2_time)

        check_player1_time_func = check_player1_time
        check_player2_time_func = check_player2_time

        # ⚡ INSTANT TRIGGER - Players already armed, just trigger playback
        logger.info("[VideoPhase] Triggering pre-armed synchronized playback")
        sync_result = SyncEngine.trigger_synchronized_playback([self.player1, self.player2])

        actual_start = time.time()
        onset_delay_ms = (actual_start - scheduled_start) * 1000

        # Send video_start event markers (after videos actually started)
        self.send_event_markers("video_start", lsl_outlet, trial_data)

        # Log sync quality and onset delay
        logger.info(
            f"VideoPhase: Onset delay={onset_delay_ms:.1f}ms, "
            f"Sync drift={sync_result['max_drift_ms']:.3f}ms, "
            f"Spread={sync_result['spread_ms']:.3f}ms"
        )

        # Schedule fallback completion checks
        pyglet.clock.schedule_interval(check_player1_time, 0.1)
        pyglet.clock.schedule_interval(check_player2_time, 0.1)

    def validate(self) -> List[str]:
        """Validate video paths."""
        errors = []

        # Check if videos are templates or actual paths
        if not self._is_template(self.participant_1_video):
            if not os.path.exists(self.participant_1_video):
                errors.append(f"Participant 1 video not found: {self.participant_1_video}")

        if not self._is_template(self.participant_2_video):
            if not os.path.exists(self.participant_2_video):
                errors.append(f"Participant 2 video not found: {self.participant_2_video}")

        return errors

    def get_estimated_duration(self) -> float:
        """
        Estimate duration (from video file metadata).

        Returns:
            Duration in seconds (or -1 if template/unknown)
        """
        if self._is_template(self.participant_1_video):
            return -1  # Variable (depends on trial)

        # Get duration from video file
        try:
            import pyglet
            source = pyglet.media.load(self.participant_1_video)
            return source.duration
        except:
            return -1

    def render(self, trial_data: Dict[str, Any]) -> 'VideoPhase':
        """Replace template variables with trial data."""
        # Debug logging for template resolution
        p1_original = self.participant_1_video
        p2_original = self.participant_2_video
        p1_rendered = self._replace_template(self.participant_1_video, trial_data)
        p2_rendered = self._replace_template(self.participant_2_video, trial_data)

        print(f"[VideoPhase.render] DEBUG Template Resolution:")
        print(f"  Trial data keys: {list(trial_data.keys()) if trial_data else 'None'}")
        print(f"  P1: '{p1_original}' → '{p1_rendered}'")
        print(f"  P2: '{p2_original}' → '{p2_rendered}'")

        rendered = VideoPhase(
            name=self.name,
            participant_1_video=p1_rendered,
            participant_2_video=p2_rendered,
            auto_advance=self.auto_advance
        )
        # Copy marker bindings to rendered instance
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        """Extract variable names from video path templates and marker bindings."""
        # Get marker template variables from parent
        variables = super().get_required_variables()

        # Add video path template variables
        variables.update(self._extract_variables(self.participant_1_video))
        variables.update(self._extract_variables(self.participant_2_video))

        return variables

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'VideoPhase',
            'name': self.name,
            'participant_1_video': self.participant_1_video,
            'participant_2_video': self.participant_2_video,
            'auto_advance': self.auto_advance,
            'marker_bindings': [binding.to_dict() for binding in self.marker_bindings]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VideoPhase':
        """Deserialize from dictionary."""
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Video Playback'),
            participant_1_video=data.get('participant_1_video', ''),
            participant_2_video=data.get('participant_2_video', ''),
            auto_advance=data.get('auto_advance', True)
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
