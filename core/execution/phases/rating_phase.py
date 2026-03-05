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
import numpy as np
import sounddevice as sd
import pyglet
from pyglet.window import key
from ..phase import Phase

logger = logging.getLogger(__name__)


class RatingPhase(Phase):
    """
    Phase for collecting participant ratings.

    Displays a question and waits for participants to respond using
    keyboard input. Supports different scale types (7-point Likert, etc.).
    Use display_target to control which participants are asked for ratings.
    """

    # Observer beep parameters
    BEEP_FREQUENCY = 1000   # Hz
    BEEP_DURATION = 0.5     # seconds
    BEEP_AMPLITUDE = 0.3    # volume (0.0-1.0)
    BEEP_SAMPLE_RATE = 44100

    def __init__(
        self,
        name: str = "Rating Collection",
        question: str = "How did the video make you feel?",
        scale_min: int = 1,
        scale_max: int = 7,
        scale_labels: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        # Per-participant questions (implicit individualization)
        participant_1_question: Optional[str] = None,
        participant_2_question: Optional[str] = None,
        # Display target
        display_target: str = "both",
        # Key bindings (configurable)
        p1_keys: str = "1234567",
        p2_keys: str = "QWERTYU",
        # Observer beep
        observer_beep: bool = False
    ):
        """
        Initialize rating phase.

        Args:
            name: Phase name
            question: Question to display (default for both participants)
            scale_min: Minimum scale value (e.g., 1)
            scale_max: Maximum scale value (e.g., 7)
            scale_labels: Labels for scale endpoints (e.g., ["Awful", "Neutral", "Amazing"])
            timeout: Maximum time to wait for responses (None = wait indefinitely)
            participant_1_question: Override question for P1 (None = use default question)
            participant_2_question: Override question for P2 (None = use default question)
            display_target: Which participants see rating screen:
                - "p1": Only P1 sees/responds; P2 sees blank screen
                - "p2": Only P2 sees/responds; P1 sees blank screen
                - "both": Both see rating screen and respond (default)
            p1_keys: Key characters for P1 ratings, one per scale point (default: "1234567")
            p2_keys: Key characters for P2 ratings, one per scale point (default: "QWERTYU")
            observer_beep: If True, play a short audio beep for the observer participant
                at the start of the rating phase (turn-taking conditions only)

        Note:
            Markers are configured via marker_bindings list.
            Common events: p1_response, p2_response
            Use template "300#0$" for P1 ratings, "500#0$" for P2 ratings

        Turn-Taking Support:
            For turn-taking conditions, use display_target to control who rates.
            Set different participant_X_question values for viewer vs observer:
            - Viewer question: "How did the video make you feel?" (self-report)
            - Observer question: "How do you think they felt?" (empathic inference)
        """
        super().__init__(name, display_target=display_target)
        self.question = question
        self.scale_min = scale_min
        self.scale_max = scale_max
        self.scale_labels = scale_labels or ["Awful", "Neutral", "Amazing"]
        self.timeout = timeout

        # Per-participant questions (implicit individualization)
        self.participant_1_question = participant_1_question
        self.participant_2_question = participant_2_question

        # Configurable key bindings (stored as strings)
        self.p1_keys = p1_keys
        self.p2_keys = p2_keys

        # Observer beep (turn-taking only)
        self.observer_beep = observer_beep

        # Build pyglet key maps from key strings
        self.participant_1_keys = self._build_key_map(self.p1_keys, scale_min, scale_max)
        self.participant_2_keys = self._build_key_map(self.p2_keys, scale_min, scale_max)

    def _determine_observer(self, trial_data: Optional[Dict[str, Any]]) -> Optional[int]:
        """
        Determine which participant is the observer from trial context.

        Uses _variant_name (set by BranchBlock) to infer viewer/observer roles.
        Falls back to trial_data 'viewer' field if available.

        Returns:
            1 if P1 is observer, 2 if P2 is observer, None if not a turn-taking trial.
        """
        if not trial_data:
            return None

        # Primary: check _variant_name set by BranchBlock during execution
        variant_name = trial_data.get('_variant_name', '')
        if variant_name:
            variant_lower = variant_name.lower()
            if 'p1' in variant_lower and 'viewer' in variant_lower:
                return 2  # P1 is viewer → P2 is observer
            elif 'p2' in variant_lower and 'viewer' in variant_lower:
                return 1  # P2 is viewer → P1 is observer

        # Fallback: check 'viewer' field from CSV trial data
        viewer = trial_data.get('viewer')
        if viewer is not None:
            try:
                viewer_int = int(viewer)
                if viewer_int == 1:
                    return 2  # P1 is viewer → P2 is observer
                elif viewer_int == 2:
                    return 1  # P2 is viewer → P1 is observer
            except (ValueError, TypeError):
                pass

        return None  # Joint condition or no viewer info

    def _play_observer_beep(self, device_manager, observer_participant: int):
        """
        Play a short beep on the observer's audio device.

        Uses sd.play() — the same API as video audio and the device setup test —
        to ensure consistent behavior. Safe to use here because no video audio
        is active during the rating phase (sd.stop() already called in finish_phase).

        Args:
            device_manager: DeviceManager instance (for audio device IDs)
            observer_participant: 1 for P1, 2 for P2
        """
        # Select audio device for the observer
        if observer_participant == 1:
            device_id = device_manager.audio_device_p1
        elif observer_participant == 2:
            device_id = device_manager.audio_device_p2
        else:
            return

        # Generate sine wave beep (stereo for maximum device compatibility)
        num_samples = int(self.BEEP_SAMPLE_RATE * self.BEEP_DURATION)
        t = np.linspace(0, self.BEEP_DURATION, num_samples, endpoint=False)
        mono = (self.BEEP_AMPLITUDE * np.sin(2 * np.pi * self.BEEP_FREQUENCY * t)).astype(np.float32)
        # Stack to stereo (N, 2)
        stereo = np.column_stack([mono, mono])

        def _beep_thread():
            """Play beep in background thread to avoid blocking the Pyglet event loop."""
            try:
                sd.play(stereo, self.BEEP_SAMPLE_RATE, device=device_id)
                sd.wait()
                logger.info(f"RatingPhase: Observer beep finished on P{observer_participant}")
            except Exception as e:
                logger.warning(f"RatingPhase: Failed to play observer beep: {e}")
                print(f"[RatingPhase] WARNING: Observer beep failed on device {device_id}: {e}")

        try:
            beep = threading.Thread(target=_beep_thread, daemon=True)
            beep.start()
            logger.info(f"RatingPhase: Observer beep started on P{observer_participant} "
                        f"(device {device_id}, {self.BEEP_DURATION}s @ {self.BEEP_FREQUENCY}Hz)")
        except Exception as e:
            logger.warning(f"RatingPhase: Failed to start observer beep thread: {e}")

    @staticmethod
    def _char_to_pyglet_key(char: str):
        """Convert a character to a pyglet key constant."""
        char = char.upper()
        if char.isdigit():
            return getattr(key, f'_{char}', None)
        elif char.isalpha():
            return getattr(key, char, None)
        return None

    @staticmethod
    def _build_key_map(key_string: str, scale_min: int, scale_max: int) -> dict:
        """Build a pyglet key -> rating value map from a key string."""
        key_map = {}
        for i, char in enumerate(key_string):
            value = scale_min + i
            if value > scale_max:
                break
            pyglet_key = RatingPhase._char_to_pyglet_key(char)
            if pyglet_key is not None:
                key_map[pyglet_key] = value
        return key_map

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

        # Determine which participants see the rating based on display_target
        show_p1 = self.should_show_to_p1()
        show_p2 = self.should_show_to_p2()

        # Response tracking
        responses = {
            'p1_response': None,
            'p1_rt': None,
            'p2_response': None,
            'p2_rt': None,
            'display_target': self.display_target
        }
        p1_responded = threading.Event()
        p2_responded = threading.Event()

        # If participant is not visible, pre-mark them as responded
        if not show_p1:
            p1_responded.set()
        if not show_p2:
            p2_responded.set()

        # Determine question for each visible participant (use per-participant override if set)
        p1_question = self.participant_1_question if self.participant_1_question else self.question
        p2_question = self.participant_2_question if self.participant_2_question else self.question

        logger.info(f"RatingPhase: display_target={self.display_target}, P1 visible={show_p1}, P2 visible={show_p2}")

        # Create UI only for visible participants
        self.instruction_batch1 = None
        self.instruction_batch2 = None
        self.response1_label = None
        self.response2_label = None

        if show_p1:
            # CRITICAL: Switch to window1's OpenGL context before creating its graphics
            window1.switch_to()
            self.instruction_batch1 = pyglet.graphics.Batch()

            self.instruction1 = pyglet.text.Label(
                p1_question,
                font_name='Arial',
                font_size=24,
                x=window1.width // 2,
                y=window1.height // 2 + 50,
                anchor_x='center',
                anchor_y='center',
                multiline=True,
                width=window1.width * 0.8,
                batch=self.instruction_batch1
            )

            self.response1_label = pyglet.text.Label(
                '',
                font_name='Arial',
                font_size=24,
                x=window1.width // 2,
                y=window1.height // 2 - 100,
                anchor_x='center',
                anchor_y='center',
                batch=self.instruction_batch1
            )

        if show_p2:
            # CRITICAL: Switch to window2's OpenGL context before creating its graphics
            window2.switch_to()
            self.instruction_batch2 = pyglet.graphics.Batch()

            self.instruction2 = pyglet.text.Label(
                p2_question,
                font_name='Arial',
                font_size=24,
                x=window2.width // 2,
                y=window2.height // 2 + 50,
                anchor_x='center',
                anchor_y='center',
                multiline=True,
                width=window2.width * 0.8,
                batch=self.instruction_batch2
            )

            self.response2_label = pyglet.text.Label(
                '',
                font_name='Arial',
                font_size=24,
                x=window2.width // 2,
                y=window2.height // 2 - 100,
                anchor_x='center',
                anchor_y='center',
                batch=self.instruction_batch2
            )

        # Play observer beep if enabled (before UI draws, non-blocking)
        if self.observer_beep:
            observer = self._determine_observer(trial_data)
            if observer is not None:
                self._play_observer_beep(device_manager, observer)
            else:
                logger.debug("RatingPhase: observer_beep enabled but no observer detected (joint condition?)")

        # Set up draw handlers (reference INSTANCE variables)
        @window1.event
        def on_draw():
            window1.clear()
            if self.instruction_batch1:
                self.instruction_batch1.draw()
            # Non-visible: just show cleared (black) screen

        @window2.event
        def on_draw():
            window2.clear()
            if self.instruction_batch2:
                self.instruction_batch2.draw()
            # Non-visible: just show cleared (black) screen

        # Timeout check function reference for cleanup
        self.check_timeout_func = None
        self.phase_finished = False

        # Check for keyboard router (per-keyboard input routing)
        keyboard_router = getattr(device_manager, 'keyboard_router', None)

        # Build unified key map for routed input (both use P1's key layout)
        unified_keys = self._build_key_map(self.p1_keys, self.scale_min, self.scale_max) if keyboard_router else None

        def finish_phase():
            """Cleanup and complete phase. MUST run on main (Pyglet) thread."""
            # Prevent multiple calls
            if self.phase_finished:
                return
            self.phase_finished = True

            # Clean up input handlers
            if keyboard_router:
                keyboard_router.unregister_handler(on_routed_key)
            else:
                if show_p1:
                    window1.remove_handlers(on_key_press=on_key_press_handler)
                if show_p2:
                    window2.remove_handlers(on_key_press=on_key_press_handler)

            if self.check_timeout_func:
                pyglet.clock.unschedule(self.check_timeout_func)

            # Call completion callback
            if on_complete:
                on_complete(responses)

        def _handle_response_on_main(participant_id, rating):
            """Handle response on the main Pyglet thread (safe for OpenGL ops)."""
            rt = time.time() - start_time

            if participant_id == 1:
                responses['p1_response'] = rating
                responses['p1_rt'] = rt
                self.send_event_markers("p1_response", lsl_outlet, trial_data, response_value=rating)
                if self.response1_label:
                    self.response1_label.text = f"Response recorded: {rating}"
                p1_responded.set()
            elif participant_id == 2:
                responses['p2_response'] = rating
                responses['p2_rt'] = rt
                self.send_event_markers("p2_response", lsl_outlet, trial_data, response_value=rating)
                if self.response2_label:
                    self.response2_label.text = f"Response recorded: {rating}"
                p2_responded.set()

            if p1_responded.is_set() and p2_responded.is_set():
                finish_phase()

        if keyboard_router:
            # UNIFIED KEY MODE: Both participants use same keys, routed by device.
            # Callback fires on background thread — schedule all Pyglet/OpenGL work
            # on the main thread via pyglet.clock.schedule_once.
            def on_routed_key(participant_id, pyglet_key, is_key_down):
                if not is_key_down:
                    return
                if pyglet_key not in unified_keys:
                    return
                rating = unified_keys[pyglet_key]
                if participant_id == 1 and show_p1 and not p1_responded.is_set():
                    pyglet.clock.schedule_once(lambda dt: _handle_response_on_main(1, rating), 0)
                elif participant_id == 2 and show_p2 and not p2_responded.is_set():
                    pyglet.clock.schedule_once(lambda dt: _handle_response_on_main(2, rating), 0)

            keyboard_router.register_handler(on_routed_key)
        else:
            # FALLBACK: Separate key maps via Pyglet window handlers (already on main thread)
            def on_key_press_handler(symbol, modifiers):
                if show_p1 and symbol in self.participant_1_keys and not p1_responded.is_set():
                    _handle_response_on_main(1, self.participant_1_keys[symbol])
                elif show_p2 and symbol in self.participant_2_keys and not p2_responded.is_set():
                    _handle_response_on_main(2, self.participant_2_keys[symbol])

            if show_p1:
                window1.push_handlers(on_key_press=on_key_press_handler)
            if show_p2:
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

        # Validate display_target
        errors.extend(self._validate_display_target())

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
            {participant_1_question} - P1-specific question
            {participant_2_question} - P2-specific question
        """
        # Replace templates in question
        question = self._replace_template(str(self.question), trial_data) if self._is_template(str(self.question)) else self.question

        # Replace templates in scale_min/max
        scale_min_str = str(self.scale_min)
        scale_max_str = str(self.scale_max)

        scale_min = int(self._replace_template(scale_min_str, trial_data)) if self._is_template(scale_min_str) else self.scale_min
        scale_max = int(self._replace_template(scale_max_str, trial_data)) if self._is_template(scale_max_str) else self.scale_max

        # Replace templates in per-participant questions
        p1_question = None
        if self.participant_1_question:
            p1_question = self._replace_template(str(self.participant_1_question), trial_data) if self._is_template(str(self.participant_1_question)) else self.participant_1_question

        p2_question = None
        if self.participant_2_question:
            p2_question = self._replace_template(str(self.participant_2_question), trial_data) if self._is_template(str(self.participant_2_question)) else self.participant_2_question

        # Replace display_target template if needed
        display_target = self.display_target
        if self._is_template(display_target):
            display_target = self._replace_template(display_target, trial_data)

        # Create new instance with replaced values
        rendered = RatingPhase(
            name=self.name,
            question=question,
            scale_min=scale_min,
            scale_max=scale_max,
            scale_labels=self.scale_labels,
            timeout=self.timeout,
            participant_1_question=p1_question,
            participant_2_question=p2_question,
            display_target=display_target,
            p1_keys=self.p1_keys,
            p2_keys=self.p2_keys,
            observer_beep=self.observer_beep
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

        # Check per-participant questions
        if self.participant_1_question and self._is_template(str(self.participant_1_question)):
            variables.update(self._extract_variables(str(self.participant_1_question)))
        if self.participant_2_question and self._is_template(str(self.participant_2_question)):
            variables.update(self._extract_variables(str(self.participant_2_question)))

        # Check display_target
        if self._is_template(self.display_target):
            variables.update(self._extract_variables(self.display_target))

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
            'participant_1_question': self.participant_1_question,
            'participant_2_question': self.participant_2_question,
            'display_target': self.display_target,
            'p1_keys': self.p1_keys,
            'p2_keys': self.p2_keys,
            'observer_beep': self.observer_beep,
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
            timeout=data.get('timeout'),
            participant_1_question=data.get('participant_1_question'),
            participant_2_question=data.get('participant_2_question'),
            display_target=data.get('display_target', 'both'),
            p1_keys=data.get('p1_keys', '1234567'),
            p2_keys=data.get('p2_keys', 'QWERTYU'),
            observer_beep=data.get('observer_beep', False)
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
