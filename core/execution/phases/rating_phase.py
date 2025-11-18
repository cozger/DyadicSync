"""
RatingPhase implementation for DyadicSync Framework.

Collects ratings from both participants simultaneously with early preload support.

Phase 3 Enhancement:
- Early preload scheduling (STAGE 1): Triggers next phase resource loading at T+200ms
- Variable duration rating period provides ample time for resource loading
- STAGE 2 (sync prep) handled by subsequent FixationPhase
"""

from typing import Dict, List, Set, Any, Optional
import time
import threading
import logging
import pyglet
from pyglet.window import key
from ..phase import Phase

logger = logging.getLogger(__name__)


class RatingPhase(Phase):
    """
    Phase for collecting participant ratings.

    Displays a question and waits for both participants to respond using
    keyboard input. Supports different scale types (7-point Likert, etc.).
    """

    def __init__(
        self,
        name: str = "Rating Collection",
        question: str = "How did the video make you feel?",
        scale_min: int = 1,
        scale_max: int = 7,
        scale_labels: Optional[List[str]] = None,
        timeout: Optional[float] = None
    ):
        """
        Initialize rating phase.

        Args:
            name: Phase name
            question: Question to display
            scale_min: Minimum scale value (e.g., 1)
            scale_max: Maximum scale value (e.g., 7)
            scale_labels: Labels for scale endpoints (e.g., ["Awful", "Neutral", "Amazing"])
            timeout: Maximum time to wait for responses (None = wait indefinitely)

        Note:
            Markers are configured via marker_bindings list.
            Common events: p1_response, p2_response
            Use template "300#0$" for P1 ratings, "500#0$" for P2 ratings
        """
        super().__init__(name)
        self.question = question
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.scale_labels = scale_labels or ["Awful", "Neutral", "Amazing"]
        self.timeout = timeout

        # Default key mappings (1-7 for P1, Q-U for P2)
        self.participant_1_keys = {
            key._1: 1, key._2: 2, key._3: 3, key._4: 4,
            key._5: 5, key._6: 6, key._7: 7
        }
        self.participant_2_keys = {
            key.Q: 1, key.W: 2, key.E: 3, key.R: 4,
            key.T: 5, key.Y: 6, key.U: 7
        }

    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None,
                on_complete=None) -> None:
        """
        Execute rating collection (non-blocking, callback-based).

        Args:
            device_manager: DeviceManager instance
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for marker template resolution
            on_complete: Callback function(result_dict) called when phase completes

        Events emitted:
            - p1_response: When participant 1 provides a rating (with response_value)
            - p2_response: When participant 2 provides a rating (with response_value)

        Note:
            This method is non-blocking. It schedules rating collection and returns immediately.
            Results are passed to on_complete callback when both participants respond or timeout occurs.
        """
        start_time = time.time()

        # Get windows from device manager
        window1 = device_manager.window1
        window2 = device_manager.window2

        # Response tracking
        responses = {
            'p1_response': None,
            'p1_rt': None,
            'p2_response': None,
            'p2_rt': None
        }
        p1_responded = threading.Event()
        p2_responded = threading.Event()

        # CRITICAL: Switch to window1's OpenGL context before creating its graphics
        window1.switch_to()
        self.instruction_batch1 = pyglet.graphics.Batch()

        # Instructions for Participant 1
        self.instruction1 = pyglet.text.Label(
            f'{self.question}\n\n'
            f'Participant 1: Use number keys {self.scale_min}-{self.scale_max}\n'
            f'{self.scale_min} = {self.scale_labels[0]}, {self.scale_max} = {self.scale_labels[-1]}',
            font_name='Arial',
            font_size=24,
            x=window1.width // 2,
            y=window1.height // 2 + 100,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=600,
            batch=self.instruction_batch1
        )

        self.response1_label = pyglet.text.Label(
            'Waiting for response...',
            font_name='Arial',
            font_size=24,
            x=window1.width // 2,
            y=window1.height // 2 - 100,
            anchor_x='center',
            anchor_y='center',
            batch=self.instruction_batch1
        )

        # CRITICAL: Switch to window2's OpenGL context before creating its graphics
        window2.switch_to()
        self.instruction_batch2 = pyglet.graphics.Batch()

        # Instructions for Participant 2
        self.instruction2 = pyglet.text.Label(
            f'{self.question}\n\n'
            f'Participant 2: Use keys Q-U\n'
            f'Q = {self.scale_labels[0]}, U = {self.scale_labels[-1]}',
            font_name='Arial',
            font_size=24,
            x=window2.width // 2,
            y=window2.height // 2 + 100,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=600,
            batch=self.instruction_batch2
        )

        self.response2_label = pyglet.text.Label(
            'Waiting for response...',
            font_name='Arial',
            font_size=24,
            x=window2.width // 2,
            y=window2.height // 2 - 100,
            anchor_x='center',
            anchor_y='center',
            batch=self.instruction_batch2
        )

        # Set up draw handlers (reference INSTANCE variables)
        @window1.event
        def on_draw():
            window1.clear()
            self.instruction_batch1.draw()

        @window2.event
        def on_draw():
            window2.clear()
            self.instruction_batch2.draw()

        # Timeout check function reference for cleanup
        self.check_timeout_func = None
        self.phase_finished = False

        def finish_phase():
            """Cleanup and complete phase."""
            # Prevent multiple calls
            if self.phase_finished:
                return
            self.phase_finished = True

            # Clean up: Remove keyboard handlers from both windows
            window1.remove_handlers(on_key_press=on_key_press_handler)
            window2.remove_handlers(on_key_press=on_key_press_handler)

            if self.check_timeout_func:
                pyglet.clock.unschedule(self.check_timeout_func)

            # Call completion callback
            if on_complete:
                on_complete(responses)

        # Define key press handler (will be attached to both visible windows)
        def on_key_press_handler(symbol, modifiers):
            # Handle Participant 1 input
            if symbol in self.participant_1_keys and not p1_responded.is_set():
                rating = self.participant_1_keys[symbol]
                rt = time.time() - start_time
                responses['p1_response'] = rating
                responses['p1_rt'] = rt

                # Send p1_response event marker (with response_value for template resolution)
                self.send_event_markers("p1_response", lsl_outlet, trial_data, response_value=rating)

                self.response1_label.text = f"Response recorded: {rating}"
                p1_responded.set()

            # Handle Participant 2 input
            elif symbol in self.participant_2_keys and not p2_responded.is_set():
                rating = self.participant_2_keys[symbol]
                rt = time.time() - start_time
                responses['p2_response'] = rating
                responses['p2_rt'] = rt

                # Send p2_response event marker (with response_value for template resolution)
                self.send_event_markers("p2_response", lsl_outlet, trial_data, response_value=rating)

                self.response2_label.text = f"Response recorded: {rating}"
                p2_responded.set()

            # Check if both responded
            if p1_responded.is_set() and p2_responded.is_set():
                finish_phase()

        # Attach handler to BOTH visible windows (not hidden window)
        window1.push_handlers(on_key_press=on_key_press_handler)
        window2.push_handlers(on_key_press=on_key_press_handler)

        # Run event loop with timeout
        def check_timeout(dt):
            if self.timeout and (time.time() - start_time) >= self.timeout:
                finish_phase()

        if self.timeout:
            self.check_timeout_func = check_timeout
            pyglet.clock.schedule_interval(self.check_timeout_func, 0.1)

        # Phase 3: Schedule early preload for next phase (if available)
        # STAGE 1 only - rating duration is variable, so STAGE 2 handled by next Fixation
        if hasattr(self, '_next_phase') and self._next_phase:
            if self._next_phase.needs_preload():
                # Schedule preload 200ms from now (during participant thinking/response time)
                logger.info(
                    f"RatingPhase: Next phase ({self._next_phase.name}) needs preload "
                    f"- should be handled by ContinuousPreloader during rating period"
                )
                # Note: Actual STAGE 1 orchestration handled by ContinuousPreloader at Block level
                # STAGE 2 (sync prep) will be handled by subsequent FixationPhase

    def validate(self) -> List[str]:
        """Validate rating phase configuration."""
        errors = []

        if self.scale_min >= self.scale_max:
            errors.append(f"Scale min ({self.scale_min}) must be less than max ({self.scale_max})")

        if self.timeout and self.timeout <= 0:
            errors.append(f"Timeout must be positive, got {self.timeout}")

        return errors

    def get_estimated_duration(self) -> float:
        """Return timeout or -1 if no timeout."""
        return self.timeout if self.timeout else -1

    def render(self, trial_data: Dict[str, Any]) -> 'RatingPhase':
        """
        Render phase with trial data (replace template variables).

        Args:
            trial_data: Dictionary of trial variables

        Returns:
            New RatingPhase instance with variables replaced

        Supports template variables:
            {question} - Question text
            {scale_min} - Minimum scale value
            {scale_max} - Maximum scale value
        """
        # Replace templates in question
        question = self._replace_template(str(self.question), trial_data) if self._is_template(str(self.question)) else self.question

        # Replace templates in scale_min/max
        scale_min_str = str(self.scale_min)
        scale_max_str = str(self.scale_max)

        scale_min = int(self._replace_template(scale_min_str, trial_data)) if self._is_template(scale_min_str) else self.scale_min
        scale_max = int(self._replace_template(scale_max_str, trial_data)) if self._is_template(scale_max_str) else self.scale_max

        # Create new instance with replaced values
        rendered = RatingPhase(
            name=self.name,
            question=question,
            scale_min=scale_min,
            scale_max=scale_max,
            scale_labels=self.scale_labels,
            timeout=self.timeout
        )
        # Copy marker bindings to rendered instance
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        """
        Get template variables required by this phase.

        Returns:
            Set of variable names (e.g., {'question'})
        """
        # Get marker template variables from parent
        variables = super().get_required_variables()

        # Check question
        if self._is_template(str(self.question)):
            variables.update(self._extract_variables(str(self.question)))

        # Check scale_min
        if self._is_template(str(self.scale_min)):
            variables.update(self._extract_variables(str(self.scale_min)))

        # Check scale_max
        if self._is_template(str(self.scale_max)):
            variables.update(self._extract_variables(str(self.scale_max)))

        return variables

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'RatingPhase',
            'name': self.name,
            'question': self.question,
            'scale_min': self.scale_min,
            'scale_max': self.scale_max,
            'scale_labels': self.scale_labels,
            'timeout': self.timeout,
            'marker_bindings': [binding.to_dict() for binding in self.marker_bindings]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RatingPhase':
        """Deserialize from dictionary."""
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Rating Collection'),
            question=data.get('question', 'How did the video make you feel?'),
            scale_min=data.get('scale_min', 1),
            scale_max=data.get('scale_max', 7),
            scale_labels=data.get('scale_labels'),
            timeout=data.get('timeout')
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
