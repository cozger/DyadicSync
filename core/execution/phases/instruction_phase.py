"""
InstructionPhase implementation for DyadicSync Framework.

Displays text instructions to participants.
"""

from typing import Dict, List, Set, Any, Optional
import time
import pyglet
from pyglet.window import key
from ..phase import Phase


class InstructionPhase(Phase):
    """
    Phase for displaying text instructions.

    Shows instruction text on participant screens and waits for
    experimenter or participant input to continue.
    Use display_target to control which participants see the instructions.
    Use participant_X_text for per-participant individualization.
    """

    # Named key constants for resolving key name strings
    NAMED_KEYS = {
        'space': key.SPACE,
        'enter': key.ENTER,
        'return': key.RETURN,
        'escape': key.ESCAPE,
        'esc': key.ESCAPE,
        'tab': key.TAB,
    }

    def __init__(
        self,
        name: str = "Instructions",
        text: str = "",
        font_size: int = 24,
        wait_for_key: bool = True,
        continue_key: Optional[str] = None,
        duration: Optional[float] = None,
        display_target: str = "both",
        # Per-participant text (implicit individualization)
        participant_1_text: Optional[str] = None,
        participant_2_text: Optional[str] = None,
        # Per-participant key press with waiting message
        p1_continue_key: Optional[str] = None,
        p2_continue_key: Optional[str] = None,
        waiting_message: Optional[str] = None
    ):
        """
        Initialize instruction phase.

        Args:
            name: Phase name
            text: Instruction text to display (default for both participants)
            font_size: Font size for text
            wait_for_key: Wait for key press to continue
            continue_key: Specific key to wait for (e.g., 'space', 'enter'), None = any key
            duration: Auto-advance after this many seconds (None = wait for key)
            display_target: Which participants see the instructions:
                - "p1": Only P1 sees instructions; P2 sees blank screen
                - "p2": Only P2 sees instructions; P1 sees blank screen
                - "both": Both see instructions (default)
            participant_1_text: Override text for P1 (None = use default text)
            participant_2_text: Override text for P2 (None = use default text)
            p1_continue_key: Key P1 must press in dual-acknowledge mode (e.g., 'space')
            p2_continue_key: Key P2 must press in dual-acknowledge mode (e.g., 'enter')
            waiting_message: Text shown after a participant presses their key
                (e.g., '(waiting for partner)'). Enables dual-acknowledge mode
                when both p1_continue_key and p2_continue_key are also set.

        Note:
            Markers are configured via marker_bindings list.
            Common events: phase_start, phase_end
        """
        super().__init__(name, display_target=display_target)
        self.text = text
        self.font_size = font_size
        self.wait_for_key = wait_for_key
        self.continue_key = continue_key
        self.duration = duration
        # Per-participant text for implicit individualization
        self.participant_1_text = participant_1_text
        self.participant_2_text = participant_2_text
        # Per-participant key press with waiting message
        self.p1_continue_key = p1_continue_key
        self.p2_continue_key = p2_continue_key
        self.waiting_message = waiting_message

    @staticmethod
    def _resolve_key_name(name):
        """Resolve a key name string to a pyglet key constant."""
        name = name.strip().lower()
        if name in InstructionPhase.NAMED_KEYS:
            return InstructionPhase.NAMED_KEYS[name]
        # Single character keys
        if len(name) == 1:
            if name.isdigit():
                return getattr(key, f'_{name}', None)
            elif name.isalpha():
                return getattr(key, name.upper(), None)
        return None

    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None,
                on_complete=None) -> None:
        """
        Execute instruction display (non-blocking, callback-based).

        Args:
            device_manager: DeviceManager instance
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for marker template resolution
            on_complete: Callback function(result_dict) called when phase completes

        Events emitted:
            - phase_start: At beginning of instruction display
            - phase_end: At end of instruction display

        Note:
            This method is non-blocking. It schedules instruction display and returns immediately.
            Results are passed to on_complete callback when user presses key or duration expires.
        """
        # Send phase_start event markers
        self.send_event_markers("phase_start", lsl_outlet, trial_data)

        start_time = time.time()

        # Get windows from device manager
        window1 = device_manager.window1
        window2 = device_manager.window2

        # Determine which participants see the instructions based on display_target
        show_p1 = self.should_show_to_p1()
        show_p2 = self.should_show_to_p2()

        # Determine text for each visible participant (implicit individualization)
        p1_text = self.participant_1_text if self.participant_1_text else self.text
        p2_text = self.participant_2_text if self.participant_2_text else self.text

        # Create UI only for visible participants
        self.instruction_batch1 = None
        self.instruction_batch2 = None
        self.label1 = None
        self.label2 = None

        if show_p1:
            # CRITICAL: Switch to window1's OpenGL context before creating its graphics
            window1.switch_to()
            self.instruction_batch1 = pyglet.graphics.Batch()
            self.label1 = pyglet.text.Label(
                p1_text,
                font_name='Arial',
                font_size=self.font_size,
                x=window1.width // 2,
                y=window1.height // 2,
                anchor_x='center',
                anchor_y='center',
                multiline=True,
                width=window1.width * 0.8,
                batch=self.instruction_batch1
            )

        if show_p2:
            # CRITICAL: Switch to window2's OpenGL context before creating its graphics
            window2.switch_to()
            self.instruction_batch2 = pyglet.graphics.Batch()
            self.label2 = pyglet.text.Label(
                p2_text,
                font_name='Arial',
                font_size=self.font_size,
                x=window2.width // 2,
                y=window2.height // 2,
                anchor_x='center',
                anchor_y='center',
                multiline=True,
                width=window2.width * 0.8,
                batch=self.instruction_batch2
            )

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

        # Track cleanup resources
        self.auto_exit_func = None
        self.key_handler_finished = False

        # Check for keyboard router (per-keyboard input routing)
        keyboard_router = getattr(device_manager, 'keyboard_router', None)

        # Always use dual-acknowledge mode when keyboard router is active and
        # per-participant keys are configured.
        dual_acknowledge = bool(self.p1_continue_key and self.p2_continue_key)

        def finish_phase():
            """Cleanup and complete phase. MUST run on main (Pyglet) thread."""
            # Prevent multiple calls
            if self.key_handler_finished:
                return
            self.key_handler_finished = True

            end_time = time.time()

            # Clean up input handlers
            if self.wait_for_key:
                if keyboard_router:
                    keyboard_router.unregister_handler(on_routed_key)
                else:
                    if show_p1:
                        window1.remove_handlers(on_key_press=on_key_press_handler)
                    if show_p2:
                        window2.remove_handlers(on_key_press=on_key_press_handler)

            if self.auto_exit_func:
                pyglet.clock.unschedule(self.auto_exit_func)

            # Send phase_end event markers
            self.send_event_markers("phase_end", lsl_outlet, trial_data)

            # Prepare result
            result = {
                'duration': end_time - start_time,
                'start_time': start_time,
                'end_time': end_time
            }

            # Call completion callback
            if on_complete:
                on_complete(result)

        def _schedule_finish_on_main_thread():
            """Schedule finish_phase to run on main Pyglet thread (thread-safe)."""
            pyglet.clock.schedule_once(lambda dt: finish_phase(), 0)

        # Set up key press handler if needed
        if self.wait_for_key:
            if dual_acknowledge:
                # --- DUAL-ACKNOWLEDGE MODE ---
                # Each participant has their own key. Phase advances when all
                # visible participants have pressed.
                p1_key = self._resolve_key_name(self.p1_continue_key)
                p2_key = self._resolve_key_name(self.p2_continue_key)
                waiting_text = self.waiting_message or "(waiting for partner)"

                p1_needs_press = show_p1
                p2_needs_press = show_p2
                p1_pressed = False
                p2_pressed = False

                def _check_all_done(from_background_thread=False):
                    all_done = True
                    if p1_needs_press and not p1_pressed:
                        all_done = False
                    if p2_needs_press and not p2_pressed:
                        all_done = False
                    if all_done:
                        if from_background_thread:
                            _schedule_finish_on_main_thread()
                        else:
                            finish_phase()

                if keyboard_router:
                    # ROUTED: Both participants can use the same key,
                    # identified by which keyboard they press on.
                    # Callback fires on background thread — schedule UI/finish on main thread.
                    def on_routed_key(participant_id, pyglet_key, is_key_down):
                        nonlocal p1_pressed, p2_pressed
                        if not is_key_down:
                            return

                        if participant_id == 1 and p1_needs_press and not p1_pressed and pyglet_key == p1_key:
                            p1_pressed = True
                            # Schedule label update on main thread
                            if hasattr(self, 'label1') and self.label1:
                                pyglet.clock.schedule_once(lambda dt: setattr(self.label1, 'text', waiting_text), 0)
                            _check_all_done(from_background_thread=True)
                        elif participant_id == 2 and p2_needs_press and not p2_pressed and pyglet_key == p2_key:
                            p2_pressed = True
                            if hasattr(self, 'label2') and self.label2:
                                pyglet.clock.schedule_once(lambda dt: setattr(self.label2, 'text', waiting_text), 0)
                            _check_all_done(from_background_thread=True)

                    keyboard_router.register_handler(on_routed_key)
                else:
                    # FALLBACK: Pyglet window handlers (already on main thread)
                    def on_key_press_handler(symbol, modifiers):
                        nonlocal p1_pressed, p2_pressed

                        if p1_needs_press and not p1_pressed and symbol == p1_key:
                            p1_pressed = True
                            if hasattr(self, 'label1') and self.label1:
                                self.label1.text = waiting_text

                        if p2_needs_press and not p2_pressed and symbol == p2_key:
                            p2_pressed = True
                            if hasattr(self, 'label2') and self.label2:
                                self.label2.text = waiting_text

                        _check_all_done()

                    if show_p1:
                        window1.push_handlers(on_key_press=on_key_press_handler)
                    if show_p2:
                        window2.push_handlers(on_key_press=on_key_press_handler)

            else:
                # --- LEGACY SINGLE-KEY MODE ---
                # Count-based tracking: "enter, enter" means enter must be pressed twice
                required_counts = {}
                if self.continue_key:
                    for key_name in self.continue_key.split(','):
                        resolved = self._resolve_key_name(key_name)
                        if resolved is not None:
                            required_counts[resolved] = required_counts.get(resolved, 0) + 1

                if not required_counts:
                    required_counts[key.SPACE] = 1  # fallback

                pressed_counts = {}

                if keyboard_router:
                    # ROUTED: Track presses from any identified device
                    def on_routed_key(participant_id, pyglet_key, is_key_down):
                        if not is_key_down:
                            return
                        if pyglet_key in required_counts:
                            pressed_counts[pyglet_key] = pressed_counts.get(pyglet_key, 0) + 1
                            if all(pressed_counts.get(k, 0) >= v for k, v in required_counts.items()):
                                _schedule_finish_on_main_thread()

                    keyboard_router.register_handler(on_routed_key)
                else:
                    # FALLBACK: Pyglet window handlers (existing behavior)
                    def on_key_press_handler(symbol, modifiers):
                        if symbol in required_counts:
                            pressed_counts[symbol] = pressed_counts.get(symbol, 0) + 1
                            if all(pressed_counts.get(k, 0) >= v for k, v in required_counts.items()):
                                finish_phase()

                    if show_p1:
                        window1.push_handlers(on_key_press=on_key_press_handler)
                    if show_p2:
                        window2.push_handlers(on_key_press=on_key_press_handler)

        # Set up duration timer if specified
        if self.duration:
            def auto_exit(dt):
                finish_phase()

            self.auto_exit_func = auto_exit
            pyglet.clock.schedule_once(self.auto_exit_func, self.duration)

    def validate(self) -> List[str]:
        """Validate instruction phase configuration."""
        errors = []

        # Must have at least default text OR per-participant text
        has_default_text = bool(self.text)
        has_p1_text = bool(self.participant_1_text)
        has_p2_text = bool(self.participant_2_text)

        show_p1 = self.should_show_to_p1() if not self._is_template(self.display_target) else True
        show_p2 = self.should_show_to_p2() if not self._is_template(self.display_target) else True

        if show_p1 and not has_default_text and not has_p1_text:
            errors.append("P1 is visible but no instruction text specified")
        if show_p2 and not has_default_text and not has_p2_text:
            errors.append("P2 is visible but no instruction text specified")

        if self.duration and self.duration <= 0:
            errors.append(f"Duration must be positive, got {self.duration}")

        # Validate per-participant keys if in dual-acknowledge mode
        if self.p1_continue_key and self.p2_continue_key:
            if self._resolve_key_name(self.p1_continue_key) is None:
                errors.append(f"Invalid P1 continue key: '{self.p1_continue_key}'")
            if self._resolve_key_name(self.p2_continue_key) is None:
                errors.append(f"Invalid P2 continue key: '{self.p2_continue_key}'")
        elif self.p1_continue_key or self.p2_continue_key:
            errors.append("Both P1 and P2 continue keys must be set for dual-acknowledge mode")

        # Validate display_target
        errors.extend(self._validate_display_target())

        return errors

    def get_estimated_duration(self) -> float:
        """Return duration or -1 if waiting for key."""
        return self.duration if self.duration else -1

    def render(self, trial_data: Dict[str, Any]) -> 'InstructionPhase':
        """
        Render phase with trial data (replace template variables).

        Args:
            trial_data: Dictionary of trial variables

        Returns:
            New InstructionPhase instance with variables replaced

        Supports template variables:
            {text} - Instruction text
            {duration} - Duration in seconds (if specified)
        """
        # Replace templates in text
        text = self._replace_template(str(self.text), trial_data) if self._is_template(str(self.text)) else self.text

        # Replace templates in duration (if specified)
        duration = self.duration
        if self.duration is not None:
            duration_str = str(self.duration)
            if self._is_template(duration_str):
                duration = float(self._replace_template(duration_str, trial_data))

        # Replace display_target template if needed
        display_target = self.display_target
        if self._is_template(display_target):
            display_target = self._replace_template(display_target, trial_data)

        # Replace per-participant text templates
        p1_text = None
        if self.participant_1_text:
            p1_text = self._replace_template(str(self.participant_1_text), trial_data) if self._is_template(str(self.participant_1_text)) else self.participant_1_text

        p2_text = None
        if self.participant_2_text:
            p2_text = self._replace_template(str(self.participant_2_text), trial_data) if self._is_template(str(self.participant_2_text)) else self.participant_2_text

        # Replace waiting_message template if needed
        waiting_msg = self.waiting_message
        if waiting_msg and self._is_template(str(waiting_msg)):
            waiting_msg = self._replace_template(str(waiting_msg), trial_data)

        # Create new instance with replaced values
        rendered = InstructionPhase(
            name=self.name,
            text=text,
            font_size=self.font_size,
            wait_for_key=self.wait_for_key,
            continue_key=self.continue_key,
            duration=duration,
            display_target=display_target,
            participant_1_text=p1_text,
            participant_2_text=p2_text,
            p1_continue_key=self.p1_continue_key,
            p2_continue_key=self.p2_continue_key,
            waiting_message=waiting_msg
        )
        # Copy marker bindings to rendered instance
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        """
        Get template variables required by this phase.

        Returns:
            Set of variable names (e.g., {'text', 'display_target'})
        """
        # Get marker template variables from parent
        variables = super().get_required_variables()

        # Check text
        if self._is_template(str(self.text)):
            variables.update(self._extract_variables(str(self.text)))

        # Check duration (if specified)
        if self.duration is not None and self._is_template(str(self.duration)):
            variables.update(self._extract_variables(str(self.duration)))

        # Check display_target
        if self._is_template(self.display_target):
            variables.update(self._extract_variables(self.display_target))

        # Check per-participant text
        if self.participant_1_text and self._is_template(str(self.participant_1_text)):
            variables.update(self._extract_variables(str(self.participant_1_text)))
        if self.participant_2_text and self._is_template(str(self.participant_2_text)):
            variables.update(self._extract_variables(str(self.participant_2_text)))

        # Check waiting message
        if self.waiting_message and self._is_template(str(self.waiting_message)):
            variables.update(self._extract_variables(str(self.waiting_message)))

        return variables

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'InstructionPhase',
            'name': self.name,
            'text': self.text,
            'font_size': self.font_size,
            'wait_for_key': self.wait_for_key,
            'continue_key': self.continue_key,
            'duration': self.duration,
            'display_target': self.display_target,
            'participant_1_text': self.participant_1_text,
            'participant_2_text': self.participant_2_text,
            'p1_continue_key': self.p1_continue_key,
            'p2_continue_key': self.p2_continue_key,
            'waiting_message': self.waiting_message,
            'marker_bindings': [binding.to_dict() for binding in self.marker_bindings]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InstructionPhase':
        """Deserialize from dictionary."""
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Instructions'),
            text=data.get('text', ''),
            font_size=data.get('font_size', 24),
            wait_for_key=data.get('wait_for_key', True),
            continue_key=data.get('continue_key'),
            duration=data.get('duration'),
            display_target=data.get('display_target', 'both'),
            participant_1_text=data.get('participant_1_text'),
            participant_2_text=data.get('participant_2_text'),
            p1_continue_key=data.get('p1_continue_key'),
            p2_continue_key=data.get('p2_continue_key'),
            waiting_message=data.get('waiting_message')
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
