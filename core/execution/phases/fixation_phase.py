"""
FixationPhase implementation for DyadicSync Framework.

Displays a fixation cross on one or both participant screens.
When display_target is "p1" or "p2", the non-viewer sees observer_text (or blank).

Preload scheduling:
- STAGE 2 (sync prep) scheduled at T-150ms before phase end
- STAGE 1 (resource loading) handled externally by ContinuousPreloader
"""

from typing import Dict, List, Set, Any, Optional
import time
import logging
import pyglet
from ..phase import Phase

logger = logging.getLogger(__name__)


class FixationPhase(Phase):
    """
    Displays a fixation cross for a specified duration.

    display_target controls who sees the cross:
      "both" — both participants see the cross
      "p1"   — P1 sees cross, P2 sees observer_text (or blank)
      "p2"   — P2 sees cross, P1 sees observer_text (or blank)
    """

    def __init__(
        self,
        name: str = "Fixation",
        duration: float = 3.0,
        display_target: str = "both",
        observer_text: Optional[str] = None
    ):
        super().__init__(name, display_target=display_target)
        self.duration = duration
        self.observer_text = observer_text

    # ------------------------------------------------------------------
    # Execute
    # ------------------------------------------------------------------

    def execute(self, device_manager, lsl_outlet,
                trial_data: Optional[Dict[str, Any]] = None,
                on_complete=None) -> None:
        """Non-blocking execution. Schedules visuals and calls on_complete after duration."""
        self.send_event_markers("phase_start", lsl_outlet, trial_data)
        start_time = time.time()

        window1 = device_manager.window1
        window2 = device_manager.window2

        # Decide what each window shows
        p1_gets_cross = self.display_target in ("both", "p1")
        p2_gets_cross = self.display_target in ("both", "p2")

        # Observer text goes to the OTHER participant
        p1_text = self.observer_text if (not p1_gets_cross and self.observer_text) else None
        p2_text = self.observer_text if (not p2_gets_cross and self.observer_text) else None

        logger.info(
            f"FixationPhase '{self.name}': display_target={self.display_target}, "
            f"observer_text={self.observer_text!r}, "
            f"p1={'cross' if p1_gets_cross else (repr(p1_text) or 'blank')}, "
            f"p2={'cross' if p2_gets_cross else (repr(p2_text) or 'blank')}"
        )

        # Build visuals for Window 1 (P1)
        window1.switch_to()
        self._w1_cross = self._make_cross(window1) if p1_gets_cross else None
        self._w1_label = self._make_label(window1, p1_text) if p1_text else None

        # Build visuals for Window 2 (P2)
        window2.switch_to()
        self._w2_cross = self._make_cross(window2) if p2_gets_cross else None
        self._w2_label = self._make_label(window2, p2_text) if p2_text else None

        # Draw handlers — capture refs via default args to avoid closure issues
        @window1.event
        def on_draw(cross=self._w1_cross, label=self._w1_label):
            window1.clear()
            if cross:
                cross.draw()
            elif label:
                label.draw()

        @window2.event
        def on_draw(cross=self._w2_cross, label=self._w2_label):
            window2.clear()
            if cross:
                cross.draw()
            elif label:
                label.draw()

        # Preload scheduling for next phase
        self._stage2_cb = None
        if hasattr(self, '_next_phase') and self._next_phase:
            self._stage2_cb = self._schedule_stage2(time.time() + self.duration)

        # Phase completion
        def finish(dt):
            if self._stage2_cb:
                try:
                    pyglet.clock.unschedule(self._stage2_cb)
                except Exception:
                    pass
            self.send_event_markers("phase_end", lsl_outlet, trial_data)
            if on_complete:
                on_complete({
                    'duration': time.time() - start_time,
                    'start_time': start_time,
                    'end_time': time.time()
                })

        pyglet.clock.schedule_once(finish, self.duration)

    # ------------------------------------------------------------------
    # Visual helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_cross(window):
        """Create a white fixation cross centered in *window*. Returns a drawable."""
        batch = pyglet.graphics.Batch()
        length = min(window.width, window.height) * 0.2
        thickness = length * 0.1
        cx, cy = window.width // 2, window.height // 2

        # Store shapes so they aren't garbage-collected
        vert = pyglet.shapes.Rectangle(
            x=cx - thickness / 2, y=cy - length / 2,
            width=thickness, height=length,
            color=(255, 255, 255), batch=batch
        )
        horiz = pyglet.shapes.Rectangle(
            x=cx - length / 2, y=cy - thickness / 2,
            width=length, height=thickness,
            color=(255, 255, 255), batch=batch
        )

        class _Cross:
            def __init__(self):
                self.batch = batch
                self._vert = vert
                self._horiz = horiz

            def draw(self):
                self.batch.draw()

        return _Cross()

    @staticmethod
    def _make_label(window, text):
        """Create a white centered text label in *window*. Returns a drawable."""
        batch = pyglet.graphics.Batch()

        # CRITICAL: store the Label reference so it isn't garbage-collected.
        # Without this, the batch has no vertices to draw.
        label = pyglet.text.Label(
            text,
            font_name='Arial',
            font_size=24,
            color=(255, 255, 255, 255),
            x=window.width // 2,
            y=window.height // 2,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=int(window.width * 0.8),
            batch=batch
        )

        class _Text:
            def __init__(self):
                self.batch = batch
                self._label = label  # prevent GC

            def draw(self):
                self.batch.draw()

        return _Text()

    # ------------------------------------------------------------------
    # Preload scheduling (STAGE 2 only — STAGE 1 is external)
    # ------------------------------------------------------------------

    def _schedule_stage2(self, end_time_target: float):
        """Schedule sync-prep callback at T-150ms before phase end."""
        next_phase = self._next_phase
        delay = (end_time_target - 0.150) - time.time()

        def stage2(dt):
            try:
                if hasattr(next_phase, 'prepare_sync') and callable(next_phase.prepare_sync):
                    logger.info(f"FixationPhase STAGE 2: prepare_sync() for {next_phase.name}")
                    next_phase.prepare_sync(prep_time_ms=150)
            except Exception as e:
                logger.error(f"FixationPhase STAGE 2 error: {e}", exc_info=True)

        if delay > 0:
            pyglet.clock.schedule_once(stage2, delay)
        else:
            stage2(0)

        return stage2

    # ------------------------------------------------------------------
    # Validation / estimation
    # ------------------------------------------------------------------

    def validate(self) -> List[str]:
        errors = []
        if self.duration <= 0:
            errors.append(f"Duration must be positive, got {self.duration}")
        errors.extend(self._validate_display_target())
        return errors

    def get_estimated_duration(self) -> float:
        return self.duration

    # ------------------------------------------------------------------
    # Template rendering
    # ------------------------------------------------------------------

    def render(self, trial_data: Dict[str, Any]) -> 'FixationPhase':
        """Return a new instance with template variables resolved."""
        duration_str = str(self.duration)
        duration = (
            float(self._replace_template(duration_str, trial_data))
            if self._is_template(duration_str) else self.duration
        )

        display_target = self.display_target
        if self._is_template(display_target):
            display_target = self._replace_template(display_target, trial_data)

        obs_text = self.observer_text
        if obs_text and self._is_template(str(obs_text)):
            obs_text = self._replace_template(str(obs_text), trial_data)

        rendered = FixationPhase(
            name=self.name,
            duration=duration,
            display_target=display_target,
            observer_text=obs_text
        )
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        variables = super().get_required_variables()

        duration_str = str(self.duration)
        if self._is_template(duration_str):
            variables.update(self._extract_variables(duration_str))
        if self._is_template(self.display_target):
            variables.update(self._extract_variables(self.display_target))
        if self.observer_text and self._is_template(str(self.observer_text)):
            variables.update(self._extract_variables(str(self.observer_text)))

        return variables

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        data = {
            'type': 'FixationPhase',
            'name': self.name,
            'duration': self.duration,
            'display_target': self.display_target,
            'marker_bindings': [b.to_dict() for b in self.marker_bindings]
        }
        if self.observer_text:
            data['observer_text'] = self.observer_text
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FixationPhase':
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Fixation'),
            duration=data.get('duration', 3.0),
            display_target=data.get('display_target', 'both'),
            observer_text=data.get('observer_text')
        )
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(d) for d in data['marker_bindings']
            ]
        return phase
