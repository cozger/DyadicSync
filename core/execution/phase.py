"""
Phase base class for DyadicSync Framework.

All phase types (Fixation, Video, Rating, etc.) inherit from this base class.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Set, Any, Optional, Union
import re
import threading
import time
import logging
from core.markers import MarkerBinding, resolve_marker_template, MarkerCatalog

logger = logging.getLogger(__name__)


class Phase(ABC):
    """
    Abstract base class for all phase types.

    Subclasses:
    - FixationPhase: Display fixation cross
    - VideoPhase: Play synchronized videos
    - RatingPhase: Collect participant ratings
    - InstructionPhase: Display text instructions
    - BaselinePhase: Baseline recording period
    """

    def __init__(self, name: str):
        """
        Initialize phase.

        Args:
            name: Human-readable phase name
        """
        self.name = name

        # Event marker system
        self.marker_bindings: List[MarkerBinding] = []
        self._marker_catalog = MarkerCatalog()
        self._marker_logger = None  # CRITICAL FIX: Optional MarkerLogger for tracking sent markers

        # Preloading state (Phase 3: Zero-ISI feature)
        self._is_prepared = False
        self._is_sync_prepared = False
        self._prepare_lock = threading.Lock()
        self._next_phase: Optional['Phase'] = None  # Injected by Procedure for time-borrowing

    @abstractmethod
    def execute(self, device_manager, lsl_outlet, trial_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute this phase.

        Args:
            device_manager: DeviceManager instance for accessing displays/audio
            lsl_outlet: LSL StreamOutlet for sending markers
            trial_data: Dictionary of trial variables (e.g., {'trial_index': 3, 'type': 'happy', ...})
                        Used for marker template resolution

        Returns:
            Dictionary of results (e.g., {'response': 5, 'rt': 1.234})
        """
        pass

    def needs_preload(self) -> bool:
        """
        Does this phase have heavy resources requiring preloading?

        Returns:
            True if phase should be preloaded during previous phase.
            False for lightweight phases (text, fixation, etc.)
        """
        return False  # Default: no preload needed

    def prepare(self, device_manager) -> float:
        """
        STAGE 1: Preload resources for this phase (called during PREVIOUS phase).

        This method is thread-safe and can be called from background threads.
        It loads heavy resources (videos, audio files) to eliminate loading delays.

        Args:
            device_manager: DeviceManager instance

        Returns:
            Duration in seconds that preparation took

        Example:
            # During fixation display, preload next video
            next_video_phase.prepare(device_manager)  # Runs in background
        """
        with self._prepare_lock:
            if self._is_prepared:
                return 0.0  # Already prepared

            prep_start = time.time()
            self._prepare_impl(device_manager)
            self._is_prepared = True
            prep_duration = time.time() - prep_start

            logger.info(f"{self.name}: Resources loaded in {prep_duration*1000:.1f}ms")
            return prep_duration

    def _prepare_impl(self, device_manager):
        """
        Subclass implements actual resource loading logic.

        Override this method to load videos, audio, images, etc.
        Default implementation does nothing (for lightweight phases).
        """
        pass  # Default: no resources to load

    def prepare_sync(self, prep_time_ms: int = 150):
        """
        STAGE 2: Prepare synchronization (called just before execute()).

        This lightweight method calculates sync timestamps and arms players
        for instant execution. Should be called ~150ms before phase transition.

        Args:
            prep_time_ms: Milliseconds of preparation time before playback

        Example:
            # 150ms before fixation ends
            next_video_phase.prepare_sync(prep_time_ms=150)
        """
        if self._is_sync_prepared:
            return  # Already prepared

        self._prepare_sync_impl(prep_time_ms)
        self._is_sync_prepared = True

        logger.info(f"{self.name}: Sync prepared")

    def _prepare_sync_impl(self, prep_time_ms: int):
        """
        Subclass implements actual sync preparation logic.

        Override this for phases that need precise timing (VideoPhase).
        Default implementation does nothing.
        """
        pass  # Default: no sync preparation needed

    @abstractmethod
    def validate(self) -> List[str]:
        """
        Validate phase configuration.

        Returns:
            List of error messages (empty if valid)
        """
        pass

    @abstractmethod
    def get_estimated_duration(self) -> float:
        """
        Estimated phase duration in seconds.

        Returns:
            Duration in seconds (or -1 if variable/unknown)
        """
        pass

    def render(self, trial_data: Dict[str, Any]) -> 'Phase':
        """
        Render phase with trial data (replace template variables).

        Args:
            trial_data: Dictionary of trial variables

        Returns:
            New Phase instance with variables replaced

        Example:
            phase = VideoPhase(p1_video="{video1}")
            rendered = phase.render({'video1': 'happy.mp4'})
            # rendered.p1_video == 'happy.mp4'
        """
        # Default: return self (no variables to replace)
        # Subclasses override if they have template variables
        return self

    def get_required_variables(self) -> Set[str]:
        """
        Get template variables required by this phase.

        Returns:
            Set of variable names (e.g., {'video1', 'video2'})
        """
        # Default: no variables
        # Subclasses override if they use templates
        return set()

    def set_marker_logger(self, marker_logger):
        """
        Set the MarkerLogger instance for tracking sent markers.

        Args:
            marker_logger: MarkerLogger instance or None to disable logging
        """
        self._marker_logger = marker_logger

    def send_marker(
        self,
        lsl_outlet,
        marker: Union[int, str],
        event_type: Optional[str] = None,
        trial_index: Optional[int] = None,
        participant: Optional[int] = None,
        **additional_data
    ):
        """
        Send a single LSL marker (low-level method).

        Supports both integer and string markers.

        Args:
            lsl_outlet: LSL StreamOutlet
            marker: Marker value (integer or string)
            event_type: Optional event type for logging (e.g., "video_start")
            trial_index: Optional trial number for logging
            participant: Optional participant number (1 or 2) for logging
            **additional_data: Additional context to log (e.g., response_value)

        Examples:
            send_marker(outlet, 8888)  # Integer marker
            send_marker(outlet, "happy_start")  # String marker
            send_marker(outlet, 1001, event_type="video_start", trial_index=1)  # With context
        """
        if lsl_outlet:
            # LSL supports both int and string markers
            if isinstance(marker, int):
                lsl_outlet.push_sample([marker])
            else:
                lsl_outlet.push_sample([str(marker)])

            marker_name = self._marker_catalog.get_name(marker)
            logger.info(f"LSL Marker: {marker} ({marker_name})")

            # CRITICAL FIX: Log to MarkerLogger if available (with full context)
            if self._marker_logger:
                self._marker_logger.log_marker(
                    marker=marker,
                    event_type=event_type,
                    phase_name=self.name,
                    trial_index=trial_index,
                    participant=participant,
                    **additional_data
                )

    def send_event_markers(
        self,
        event_type: str,
        lsl_outlet,
        trial_data: Optional[Dict[str, Any]] = None,
        **kwargs
    ):
        """
        Send all markers bound to a specific event.

        This is the primary method for sending markers in the new system.
        It resolves templates (integer and string) using trial_data.

        Args:
            event_type: Event name (e.g., "phase_start", "video_p1_end")
            lsl_outlet: LSL StreamOutlet
            trial_data: Dictionary of trial variables for template resolution
                        (e.g., {'trial_index': 3, 'type': 'happy', 'condition': 'sync'})
            **kwargs: Additional context (e.g., response_value for ratings)

        Example:
            # At start of phase with string marker
            trial_data = {'trial_index': 1, 'type': 'happy'}
            self.send_event_markers("phase_start", lsl_outlet, trial_data)
            # If binding.marker_template = "{type}_start" → sends "happy_start"

            # When P1 video ends with integer marker
            self.send_event_markers("video_p1_end", lsl_outlet, trial_data)
            # If binding.marker_template = "210#" → sends 2101

            # When P1 responds
            self.send_event_markers("p1_response", lsl_outlet, trial_data, response_value=7)
        """
        if not lsl_outlet:
            return

        trial_data = trial_data or {}

        # Find all bindings for this event
        matching_bindings = [
            binding for binding in self.marker_bindings
            if binding.event_type == event_type
        ]

        if not matching_bindings:
            logger.debug(f"No marker bindings for event '{event_type}'")
            return

        # Resolve and send each marker
        for binding in matching_bindings:
            try:
                # Resolve template to concrete marker (int or string)
                marker = resolve_marker_template(
                    binding.marker_template,
                    trial_data=trial_data,
                    response_value=kwargs.get('response_value')
                )

                # Send the marker with full context for MarkerLogger
                self.send_marker(
                    lsl_outlet,
                    marker,
                    event_type=event_type,
                    trial_index=trial_data.get('trial_index'),
                    participant=binding.participant,
                    **kwargs  # Pass through any additional context (e.g., response_value)
                )

                # Log with context
                marker_name = self._marker_catalog.get_name(marker)
                participant_info = f" [P{binding.participant}]" if binding.participant else ""
                trial_info = f" Trial {trial_data.get('trial_index', '?')}" if trial_data.get('trial_index') else ""
                logger.info(
                    f"Event '{event_type}'{participant_info}{trial_info}: "
                    f"Marker {marker} ({marker_name})"
                )

            except ValueError as e:
                logger.error(f"Failed to resolve marker template '{binding.marker_template}': {e}")

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize phase to dictionary.

        Returns:
            Dictionary representation of phase
        """
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Phase':
        """
        Deserialize phase from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Phase instance
        """
        pass

    # Helper methods for template variable handling

    @staticmethod
    def _is_template(s: str) -> bool:
        """Check if string contains template variables."""
        return '{' in s and '}' in s

    @staticmethod
    def _extract_variables(template: str) -> Set[str]:
        """Extract variable names from template string."""
        return set(re.findall(r'\{(\w+)\}', template))

    @staticmethod
    def _replace_template(template: str, data: Dict[str, Any]) -> str:
        """Replace {var} with data['var']."""
        result = template
        for key, value in data.items():
            result = result.replace(f'{{{key}}}', str(value))
        return result
