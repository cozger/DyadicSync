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
        STAGE 2: Prepare synchronization (called 150ms before execute()).

        This lightweight method calculates the sync timestamp and arms both
        players for instant execution. Should be called during the final 150ms
        of the previous phase (e.g., during last 150ms of fixation).

        Timing: Completes in <10ms (just calculations, no I/O)
        """
        if not self.player1 or not self.player2:
            raise RuntimeError(
                "VideoPhase STAGE 2 error: Resources not loaded. "
                "Must call prepare() (STAGE 1) first."
            )

        logger.info(f"VideoPhase STAGE 2: Preparing sync with {prep_time_ms}ms prep time")

        # Calculate future sync timestamp
        sync_timestamp = SyncEngine.calculate_sync_timestamp(prep_time_ms)

        # Arm both players with the sync timestamp (instant execution later)
        self.player1.arm_sync_timestamp(sync_timestamp)
        self.player2.arm_sync_timestamp(sync_timestamp)

        logger.info(f"VideoPhase STAGE 2: Players armed for t={sync_timestamp:.6f}")

    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute video playback with ZERO-ISI instant start.

        Players should already be prepared (STAGE 1) and armed (STAGE 2)
        by the time this method is called. This enables instant execution
        with <5ms onset delay.

        Args:
            device_manager: DeviceManager instance (for window access)
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for marker template resolution
                       (e.g., {'trial_index': 3, 'type': 'happy', ...})

        Returns:
            Dictionary with timing metrics including onset_delay_ms

        Events emitted:
            - video_start: When both videos begin playback
            - video_p1_end: When P1's video completes
            - video_p2_end: When P2's video completes
            - video_both_complete: When both videos have finished
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

        # Verify players are armed (should already be done 150ms ago)
        if not self.player1.armed_timestamp or not self.player2.armed_timestamp:
            raise RuntimeError(
                "VideoPhase execute() called without sync preparation! "
                "Players should be armed during STAGE 2 (150ms before execute). "
                "This indicates a problem with the late-stage preload timing."
            )

        logger.info(f"VideoPhase execute(): Players ready, triggering instant playback")

        # Get windows
        window1 = device_manager.window1
        window2 = device_manager.window2

        # Track completion
        completed_videos = {'count': 0}
        player1_ended = {'value': False}
        player2_ended = {'value': False}

        def mark_video_complete(player_num):
            """Mark a video as complete, send marker, and exit if both done."""
            completed_videos['count'] += 1
            logger.debug(f"Player {player_num} completed ({completed_videos['count']}/2)")

            # Send participant-specific end marker
            if player_num == 1:
                self.send_event_markers("video_p1_end", lsl_outlet, trial_data)
            elif player_num == 2:
                self.send_event_markers("video_p2_end", lsl_outlet, trial_data)

            # Exit when both complete
            if completed_videos['count'] >= 2:
                pyglet.app.exit()

        # Set up draw handlers to render video textures
        @window1.event
        def on_draw():
            window1.clear()
            texture = self.player1.get_texture()
            if texture:
                # Render texture to fill window
                texture.blit(0, 0, width=window1.width, height=window1.height)

        @window2.event
        def on_draw():
            window2.clear()
            texture = self.player2.get_texture()
            if texture:
                # Render texture to fill window
                texture.blit(0, 0, width=window2.width, height=window2.height)

        # Set up end-of-stream handlers
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
            if self.player1.player and self.player1.player.source:
                if self.player1.player.time >= self.player1.player.source.duration - 0.1:
                    if not player1_ended['value']:
                        player1_ended['value'] = True
                        mark_video_complete(1)
                        pyglet.clock.unschedule(check_player1_time)

        def check_player2_time(dt):
            if self.player2.player and self.player2.player.source:
                if self.player2.player.time >= self.player2.player.source.duration - 0.1:
                    if not player2_ended['value']:
                        player2_ended['value'] = True
                        mark_video_complete(2)
                        pyglet.clock.unschedule(check_player2_time)

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

        # Run Pyglet event loop (exits when both videos complete)
        pyglet.app.run()

        # Audio will continue playing until complete (managed by sounddevice)
        end_time = time.time()

        # Send video_both_complete event markers
        self.send_event_markers("video_both_complete", lsl_outlet, trial_data)

        # Cleanup
        pyglet.clock.unschedule(check_player1_time)
        pyglet.clock.unschedule(check_player2_time)
        self.player1.stop()
        self.player2.stop()

        # Clear player references for next trial
        self.player1 = None
        self.player2 = None

        # CRITICAL FIX: Reset preload state flags for next trial
        # Without this, second trial will skip preparation and crash
        self._is_prepared = False
        self._is_sync_prepared = False

        return {
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
        rendered = VideoPhase(
            name=self.name,
            participant_1_video=self._replace_template(self.participant_1_video, trial_data),
            participant_2_video=self._replace_template(self.participant_2_video, trial_data),
            auto_advance=self.auto_advance
        )
        # Copy marker bindings to rendered instance
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        """Extract variable names from templates."""
        variables = set()
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
