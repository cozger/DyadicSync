"""
BaselinePhase implementation for DyadicSync Framework.

Displays fixation cross during baseline recording period.
"""

from typing import Dict, List, Set, Any, Optional
from .fixation_phase import FixationPhase


class BaselinePhase(FixationPhase):
    """
    Phase for baseline recording.

    Similar to FixationPhase but specifically for baseline periods.
    Typically longer duration (e.g., 240 seconds) with specific markers.
    Use display_target to control which participants see the cross.
    """

    def __init__(
        self,
        name: str = "Baseline",
        duration: float = 240.0,
        display_target: str = "both",
        observer_text: Optional[str] = None
    ):
        """
        Initialize baseline phase.

        Args:
            name: Phase name
            duration: Duration in seconds (default 240s = 4 minutes)
            display_target: Which participants see the baseline cross:
                - "p1": Only P1 sees cross; P2 sees blank screen
                - "p2": Only P2 sees cross; P1 sees blank screen
                - "both": Both participants see cross (default)
            observer_text: Text shown to non-viewer in turn-taking (see FixationPhase)

        Note:
            Markers are configured via marker_bindings list.
            Typically uses markers 8888 (start) and 9999 (end) for baseline.
        """
        super().__init__(
            name=name,
            duration=duration,
            display_target=display_target,
            observer_text=observer_text
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        data = {
            'type': 'BaselinePhase',
            'name': self.name,
            'duration': self.duration,
            'display_target': self.display_target,
            'marker_bindings': [binding.to_dict() for binding in self.marker_bindings]
        }
        if self.observer_text:
            data['observer_text'] = self.observer_text
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaselinePhase':
        """Deserialize from dictionary."""
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Baseline'),
            duration=data.get('duration', 240.0),
            display_target=data.get('display_target', 'both'),
            observer_text=data.get('observer_text')
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
