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
    """

    def __init__(
        self,
        name: str = "Baseline",
        duration: float = 240.0
    ):
        """
        Initialize baseline phase.

        Args:
            name: Phase name
            duration: Duration in seconds (default 240s = 4 minutes)

        Note:
            Markers are configured via marker_bindings list.
            Typically uses markers 8888 (start) and 9999 (end) for baseline.
        """
        super().__init__(
            name=name,
            duration=duration
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'type': 'BaselinePhase',
            'name': self.name,
            'duration': self.duration,
            'marker_bindings': [binding.to_dict() for binding in self.marker_bindings]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BaselinePhase':
        """Deserialize from dictionary."""
        from core.markers import MarkerBinding

        phase = cls(
            name=data.get('name', 'Baseline'),
            duration=data.get('duration', 240.0)
        )

        # Load marker bindings
        if 'marker_bindings' in data:
            phase.marker_bindings = [
                MarkerBinding.from_dict(binding_data)
                for binding_data in data['marker_bindings']
            ]

        return phase
