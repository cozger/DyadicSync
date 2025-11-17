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

    Shows instruction text on both participant screens and waits for
    experimenter or participant input to continue.
    """

    def __init__(
        self,
        name: str = "Instructions",
        text: str = "",
        font_size: int = 24,
        wait_for_key: bool = True,
        continue_key: Optional[str] = None,
        duration: Optional[float] = None
    ):
        """
        Initialize instruction phase.

        Args:
            name: Phase name
            text: Instruction text to display
            font_size: Font size for text
            wait_for_key: Wait for key press to continue
            continue_key: Specific key to wait for (e.g., 'space', 'enter'), None = any key
            duration: Auto-advance after this many seconds (None = wait for key)

        Note:
            Markers are configured via marker_bindings list.
            Common events: phase_start, phase_end
        """
        super().__init__(name)
        self.text = text
        self.font_size = font_size
        self.wait_for_key = wait_for_key
        self.continue_key = continue_key
        self.duration = duration

    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute instruction display.

        Args:
            device_manager: DeviceManager instance
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for marker template resolution

        Returns:
            {'duration': float, 'start_time': float, 'end_time': float}

        Events emitted:
            - phase_start: At beginning of instruction display
            - phase_end: At end of instruction display
        """
        # Send phase_start event markers
        self.send_event_markers("phase_start", lsl_outlet, trial_data)

        start_time = time.time()

        # Get windows from device manager
        window1 = device_manager.window1
        window2 = device_manager.window2

        # Create instruction batches
        instruction_batch1 = pyglet.graphics.Batch()
        instruction_batch2 = pyglet.graphics.Batch()

        # Create instruction labels
        instruction_text = self.text
        if self.wait_for_key:
            # Add continue instruction based on continue_key
            if self.continue_key:
                key_name = self.continue_key.upper()
                instruction_text += f"\n\nPress {key_name} to continue"
            else:
                instruction_text += "\n\nPress any key to continue"

        label1 = pyglet.text.Label(
            instruction_text,
            font_name='Arial',
            font_size=self.font_size,
            x=window1.width // 2,
            y=window1.height // 2,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=window1.width * 0.8,
            batch=instruction_batch1
        )

        label2 = pyglet.text.Label(
            instruction_text,
            font_name='Arial',
            font_size=self.font_size,
            x=window2.width // 2,
            y=window2.height // 2,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=window2.width * 0.8,
            batch=instruction_batch2
        )

        # Set up draw handlers
        @window1.event
        def on_draw():
            window1.clear()
            instruction_batch1.draw()

        @window2.event
        def on_draw():
            window2.clear()
            instruction_batch2.draw()

        # Set up key press handler if needed
        if self.wait_for_key:
            input_window = pyglet.window.Window(visible=False)

            @input_window.event
            def on_key_press(symbol, modifiers):
                # Check for specific key or accept any key
                if self.continue_key:
                    # Map continue_key string to pyglet key constant
                    key_map = {
                        'space': key.SPACE,
                        'enter': key.ENTER,
                        'return': key.RETURN,
                        'escape': key.ESCAPE,
                        'esc': key.ESCAPE,
                    }
                    expected_key = key_map.get(self.continue_key.lower(), key.SPACE)
                    if symbol == expected_key:
                        pyglet.app.exit()
                else:
                    # Accept any key
                    pyglet.app.exit()

        # Set up duration timer if specified
        if self.duration:
            def auto_exit(dt):
                pyglet.clock.unschedule(auto_exit)
                pyglet.app.exit()

            pyglet.clock.schedule_once(auto_exit, self.duration)

        # Run event loop
        pyglet.app.run()

        end_time = time.time()

        # Clean up
        if self.wait_for_key:
            input_window.close()

        # Send phase_end event markers
        self.send_event_markers("phase_end", lsl_outlet, trial_data)

        return {
            'duration': end_time - start_time,
            'start_time': start_time,
            'end_time': end_time
        }

    def validate(self) -> List[str]:
        """Validate instruction phase configuration."""
        errors = []

        if not self.text:
            errors.append("Instruction text cannot be empty")

        if self.duration and self.duration <= 0:
            errors.append(f"Duration must be positive, got {self.duration}")

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

        # Create new instance with replaced values
        rendered = InstructionPhase(
            name=self.name,
            text=text,
            font_size=self.font_size,
            wait_for_key=self.wait_for_key,
            continue_key=self.continue_key,
            duration=duration
        )
        # Copy marker bindings to rendered instance
        rendered.marker_bindings = self.marker_bindings.copy()
        return rendered

    def get_required_variables(self) -> Set[str]:
        """
        Get template variables required by this phase.

        Returns:
            Set of variable names (e.g., {'text'})
        """
        variables = set()

        # Check text
        if self._is_template(str(self.text)):
            variables.update(self._extract_variables(str(self.text)))

        # Check duration (if specified)
        if self.duration is not None and self._is_template(str(self.duration)):
            variables.update(self._extract_variables(str(self.duration)))

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
            duration=data.get('duration')
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
