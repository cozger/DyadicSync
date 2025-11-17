"""
FixationPhase implementation for DyadicSync Framework.

Displays a fixation cross on both participant screens with zero-ISI preload scheduling.

Phase 3 Enhancement:
- Early preload scheduling (STAGE 1): Triggers next phase resource loading at T+200ms
- Late sync prep scheduling (STAGE 2): Triggers sync preparation at T-150ms before end
- Enables seamless transition to next phase with <5ms ISI
"""

from typing import Dict, List, Set, Any, Optional
import time
import threading
import logging
import pyglet
from ..phase import Phase

logger = logging.getLogger(__name__)


class FixationPhase(Phase):
    """
    Phase for displaying a fixation cross.

    Displays a white fixation cross on both participant screens for a specified duration.
    """

    def __init__(
        self,
        name: str = "Fixation",
        duration: float = 3.0
    ):
        """
        Initialize fixation phase.

        Args:
            name: Phase name
            duration: Duration in seconds

        Note:
            Markers are configured via marker_bindings list.
            Common events: phase_start, phase_end
        """
        super().__init__(name)
        self.duration = duration

    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute fixation phase.

        Args:
            device_manager: DeviceManager instance
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for marker template resolution

        Returns:
            {'duration': float, 'start_time': float, 'end_time': float}

        Events emitted:
            - phase_start: At beginning of fixation display
            - phase_end: At end of fixation display
        """
        # Send phase_start event markers
        self.send_event_markers("phase_start", lsl_outlet, trial_data)

        start_time = time.time()
        cross1 = None
        cross2 = None
        check_time_func = None
        stage2_callback = None  # MEDIUM PRIORITY FIX #6: Track STAGE 2 callback for cleanup

        try:
            # Get windows from device manager
            window1 = device_manager.window1
            window2 = device_manager.window2

            # Create cross displays
            cross1 = self._create_cross_display(window1)
            cross2 = self._create_cross_display(window2)

            # Activate crosses
            cross1.active = True
            cross2.active = True

            # Set up draw handlers
            @window1.event
            def on_draw():
                window1.clear()
                cross1.draw()

            @window2.event
            def on_draw():
                window2.clear()
                cross2.draw()

            # Run for specified duration
            end_time_target = time.time() + self.duration

            def check_time(dt):
                if time.time() >= end_time_target:
                    pyglet.clock.unschedule(check_time)
                    pyglet.app.exit()

            check_time_func = check_time
            pyglet.clock.schedule_interval(check_time_func, 0.01)

            # Phase 3: Schedule preloading of next phase (if available)
            # STAGE 1 (early): Load resources at T+200ms
            # STAGE 2 (late): Prepare sync at T-150ms before end
            if hasattr(self, '_next_phase') and self._next_phase:
                stage2_callback = self._schedule_preload_stages(start_time, end_time_target)

            pyglet.app.run()

            end_time = time.time()

        finally:
            # Cleanup: Deactivate crosses
            if cross1:
                cross1.active = False
            if cross2:
                cross2.active = False

            # Unschedule clock callback
            if check_time_func:
                try:
                    pyglet.clock.unschedule(check_time_func)
                except:
                    pass

            # MEDIUM PRIORITY FIX #6: Unschedule STAGE 2 callback on interruption
            if stage2_callback:
                try:
                    pyglet.clock.unschedule(stage2_callback)
                    logger.debug("FixationPhase: Unscheduled STAGE 2 callback during cleanup")
                except:
                    pass

            # Remove event handlers (Pyglet doesn't have easy way to remove specific handlers)
            # They will be replaced on next execution

        # Send phase_end event markers
        self.send_event_markers("phase_end", lsl_outlet, trial_data)

        return {
            'duration': end_time - start_time if 'end_time' in locals() else 0,
            'start_time': start_time,
            'end_time': end_time if 'end_time' in locals() else time.time()
        }

    def _create_cross_display(self, window):
        """
        Create a cross display object for a window.

        Args:
            window: Pyglet window

        Returns:
            CrossDisplay object
        """
        class CrossDisplay:
            def __init__(self, window):
                self.window = window
                self.active = False
                self.batch = pyglet.graphics.Batch()

                self.cross_length = min(window.width, window.height) * 0.2
                self.cross_thickness = self.cross_length * 0.1

                center_x = window.width // 2
                center_y = window.height // 2

                self.vertical = pyglet.shapes.Rectangle(
                    x=center_x - self.cross_thickness/2,
                    y=center_y - self.cross_length/2,
                    width=self.cross_thickness,
                    height=self.cross_length,
                    color=(255, 255, 255),
                    batch=self.batch
                )

                self.horizontal = pyglet.shapes.Rectangle(
                    x=center_x - self.cross_length/2,
                    y=center_y - self.cross_thickness/2,
                    width=self.cross_length,
                    height=self.cross_thickness,
                    color=(255, 255, 255),
                    batch=self.batch
                )

            def draw(self):
                if self.active:
                    self.batch.draw()

        return CrossDisplay(window)

    def _schedule_preload_stages(self, start_time: float, end_time_target: float):
        """
        Schedule STAGE 2 (late sync prep) for next phase during fixation display.

        CRITICAL FIX: STAGE 1 (resource loading) is handled by Procedure.execute()
        via ContinuousPreloader. This method ONLY handles STAGE 2 (sync preparation).

        STAGE 2 (Late): Prepare sync at T-150ms before end

        Args:
            start_time: Fixation start timestamp
            end_time_target: Fixation end timestamp
        """
        next_phase = self._next_phase

        # Timing calculation for STAGE 2 only
        late_sync_prep_time = end_time_target - 0.150  # 150ms before end

        logger.debug(
            f"FixationPhase: Scheduling STAGE 2 (sync prep) for {next_phase.name} "
            f"at T-150ms before fixation ends"
        )

        # STAGE 2: Late sync preparation (scheduled via pyglet clock)
        def stage2_late_sync_prep(dt):
            """Pyglet clock callback for STAGE 2 sync preparation."""
            try:
                # HIGH PRIORITY FIX #6: Verify STAGE 1 completed before STAGE 2
                if hasattr(next_phase, '_is_prepared') and not next_phase._is_prepared:
                    logger.warning(
                        f"FixationPhase STAGE 2: STAGE 1 (resource loading) not yet complete "
                        f"for {next_phase.name}. Sync prep may fail if resources not ready."
                    )
                    # Still attempt STAGE 2 - VideoPhase.execute() will validate and fail gracefully

                # Check if next phase supports sync preparation
                if hasattr(next_phase, 'prepare_sync') and callable(next_phase.prepare_sync):
                    logger.info(f"FixationPhase STAGE 2: Triggering prepare_sync() for {next_phase.name}")
                    next_phase.prepare_sync(prep_time_ms=150)
                else:
                    logger.debug(f"FixationPhase STAGE 2: {next_phase.name} does not need sync prep")

                # Unschedule this callback (one-time execution)
                pyglet.clock.unschedule(stage2_late_sync_prep)

            except Exception as e:
                logger.error(f"FixationPhase STAGE 2 error: {e}", exc_info=True)

        # Schedule STAGE 2 (late sync prep) via pyglet clock
        delay_until_stage2 = late_sync_prep_time - time.time()
        if delay_until_stage2 > 0:
            pyglet.clock.schedule_once(stage2_late_sync_prep, delay_until_stage2)
            logger.debug(f"FixationPhase: STAGE 2 scheduled for {delay_until_stage2:.3f}s from now")
        else:
            # CRITICAL FIX: If not enough time, execute STAGE 2 immediately
            logger.warning(
                f"FixationPhase: Not enough time for scheduled STAGE 2 "
                f"(need 150ms, only {delay_until_stage2*1000:.1f}ms remaining) - executing immediately"
            )
            stage2_late_sync_prep(0)  # Execute with dt=0

        # Return callback for cleanup (MEDIUM PRIORITY FIX #6)
        return stage2_late_sync_prep

    def validate(self) -> List[str]:
        """Validate fixation phase configuration."""
        errors = []

        if self.duration <= 0:
            errors.append(f"Duration must be positive, got {self.duration}")

        return errors

    def get_estimated_duration(self) -> float:
        """Return duration in seconds."""
        return self.duration

    def render(self, trial_data: Dict[str, Any]) -> 'FixationPhase':
        """
        Render phase with trial data (replace template variables).

        Args:
            trial_data: Dictionary of trial variables

        Returns:
            New FixationPhase instance with variables replaced

        Supports template variables:
            {duration} - Duration in seconds
        """
        # Convert duration to string for template replacement
        duration_str = str(self.duration)

        # Check if duration is a template
        if self._is_template(duration_str):
            duration_replaced = self._replace_template(duration_str, trial_data)
            duration = float(duration_replaced)
        else:
            duration = self.duration

        # Create new instance with replaced values
        rendered = FixationPhase(
            name=self.name,
            duration=duration
        )
        # Copy marker bindings to rendered instance
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        """
        Get template variables required by this phase.

        Returns:
            Set of variable names (e.g., {'duration'})
        """
        variables = set()

        # Check if duration is a template
        duration_str = str(self.duration)
        if self._is_template(duration_str):
            variables.update(self._extract_variables(duration_str))

        return variables

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'FixationPhase',
            'name': self.name,
            'duration': self.duration,
            'marker_bindings': [binding.to_dict() for binding in self.marker_bindings]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FixationPhase':
        """Deserialize from dictionary."""
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Fixation'),
            duration=data.get('duration', 3.0)
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
