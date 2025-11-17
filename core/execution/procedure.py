"""
Procedure class for DyadicSync Framework.

Defines the sequence of phases that occur in each trial.
"""

from typing import Dict, List, Set, Optional, Any
from .phase import Phase


class Procedure:
    """
    Defines the sequence of phases that occur in each trial.

    Example:
        procedure = Procedure("Standard Trial")
        procedure.add_phase(FixationPhase(duration=3))
        procedure.add_phase(VideoPhase(p1_video="{video1}", p2_video="{video2}"))
        procedure.add_phase(RatingPhase(question="How did you feel?"))

    Templates:
    - Phases can reference trial data using {column_name} syntax
    - Values filled at runtime from trial list
    """

    def __init__(self, name: str):
        """
        Initialize procedure.

        Args:
            name: Human-readable procedure name
        """
        self.name = name
        self.phases: List[Phase] = []

    def add_phase(self, phase: Phase):
        """
        Add a phase to the procedure.

        Args:
            phase: Phase instance to add
        """
        self.phases.append(phase)

    def remove_phase(self, index: int):
        """
        Remove phase at index.

        Args:
            index: Phase index to remove
        """
        del self.phases[index]

    def reorder_phase(self, old_index: int, new_index: int):
        """
        Move phase from old_index to new_index.

        Args:
            old_index: Current phase index
            new_index: Target phase index
        """
        phase = self.phases.pop(old_index)
        self.phases.insert(new_index, phase)

    def execute(self, trial_data: Optional[Dict], device_manager, lsl_outlet, data_collector, preloader=None):
        """
        Execute all phases in sequence with zero-ISI preloading support.

        Args:
            trial_data: Dictionary of trial variables (e.g., {'video1': 'path.mp4', 'trial_index': 1})
            device_manager: DeviceManager instance
            lsl_outlet: LSL outlet for markers
            data_collector: DataCollector instance
            preloader: ContinuousPreloader instance for zero-ISI support (optional, Phase 3)

        Returns:
            dict: Results from all phases (e.g., ratings, RTs)
        """
        # HIGH PRIORITY FIX: Validate trial_data is provided
        if not trial_data:
            raise ValueError(
                "trial_data is required for procedure execution. "
                "Procedures need trial data for marker template resolution and phase rendering."
            )

        # HIGH PRIORITY FIX: Validate trial_index is present in trial_data
        if 'trial_index' not in trial_data:
            raise ValueError(
                "trial_data must contain 'trial_index' key for marker template resolution. "
                f"Got trial_data keys: {list(trial_data.keys())}"
            )

        results = {}
        trial_index = trial_data['trial_index']

        # Phase 3: Render all phases upfront and inject _next_phase references
        rendered_phases = []
        for phase in self.phases:
            rendered_phase = phase.render(trial_data) if trial_data else phase
            rendered_phases.append(rendered_phase)

        # Inject _next_phase references for time-borrowing preload
        for i in range(len(rendered_phases) - 1):
            rendered_phases[i]._next_phase = rendered_phases[i + 1]

        # Execute phases sequentially with preloading support
        for i, rendered_phase in enumerate(rendered_phases):
            # Phase 3: Trigger preload for next phase (if preloader available and next phase exists)
            if preloader and i < len(rendered_phases) - 1:
                next_phase = rendered_phases[i + 1]
                if next_phase.needs_preload():
                    # Schedule preload to start 200ms from now (during current phase display)
                    import time
                    preload_start_time = time.time() + 0.2
                    preloader.preload_next(next_phase, when=preload_start_time)

            # Execute phase (pass trial_data for LSL marker template resolution)
            phase_result = rendered_phase.execute(
                device_manager=device_manager,
                lsl_outlet=lsl_outlet,
                trial_data=trial_data
            )

            # Store result
            results[rendered_phase.name] = phase_result

            # Phase 3: Wait for preload to complete before next phase starts
            # (In typical case with proper time-borrowing, this returns immediately)
            if preloader:
                preloader.wait_for_preload(timeout=10.0)

        # Extract and save participant response data
        self._save_participant_responses(results, trial_data, trial_index, data_collector)

        return results

    def _save_participant_responses(self, results: Dict[str, Any], trial_data: Optional[Dict],
                                     trial_index: int, data_collector):
        """
        Extract participant responses from results and save to data collector.

        Args:
            results: Results from all phases
            trial_data: Trial data dictionary
            trial_index: Trial index
            data_collector: DataCollector instance
        """
        # Find rating results (look for RatingPhase results)
        rating_results = None
        for phase_name, phase_result in results.items():
            # Check if this looks like rating data (has p1_response, p2_response)
            if isinstance(phase_result, dict) and 'p1_response' in phase_result:
                rating_results = phase_result
                break

        if not rating_results:
            return  # No rating data to save

        # Extract trial_id from trial_data
        trial_id = trial_data.get('trial_id', trial_index) if trial_data else trial_index

        # Save P1 response
        if rating_results.get('p1_response') is not None:
            # Prepare additional data for the response record
            extra_data = {}
            if trial_data:
                # Include video paths and other trial metadata
                extra_data.update({
                    'video1': trial_data.get('VideoPath1', trial_data.get('video1', '')),
                    'video2': trial_data.get('VideoPath2', trial_data.get('video2', '')),
                    'trial_index': trial_index
                })
                # Include any other columns from trial_data
                for key, value in trial_data.items():
                    if key not in extra_data and key not in ['trial_id', 'trial_index']:
                        extra_data[key] = value

            data_collector.add_participant_response(
                participant='P1',
                trial_id=trial_id,
                response=rating_results['p1_response'],
                rt=rating_results.get('p1_rt', 0.0),
                **extra_data
            )

        # Save P2 response
        if rating_results.get('p2_response') is not None:
            # Prepare additional data for the response record
            extra_data = {}
            if trial_data:
                # Include video paths and other trial metadata
                extra_data.update({
                    'video1': trial_data.get('VideoPath1', trial_data.get('video1', '')),
                    'video2': trial_data.get('VideoPath2', trial_data.get('video2', '')),
                    'trial_index': trial_index
                })
                # Include any other columns from trial_data
                for key, value in trial_data.items():
                    if key not in extra_data and key not in ['trial_id', 'trial_index']:
                        extra_data[key] = value

            data_collector.add_participant_response(
                participant='P2',
                trial_id=trial_id,
                response=rating_results['p2_response'],
                rt=rating_results.get('p2_rt', 0.0),
                **extra_data
            )

    def validate(self) -> List[str]:
        """
        Validate all phases.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for i, phase in enumerate(self.phases):
            phase_errors = phase.validate()
            errors.extend([f"Phase {i} ({phase.name}): {e}" for e in phase_errors])
        return errors

    def get_estimated_duration(self) -> float:
        """
        Estimated procedure duration in seconds.

        Returns:
            Total duration (sum of all phases with known durations)
        """
        total = 0.0
        for phase in self.phases:
            duration = phase.get_estimated_duration()
            if duration > 0:  # Only count known durations (skip -1 for unknown)
                total += duration
        return total

    def get_required_variables(self) -> Set[str]:
        """
        Get all variables required by this procedure.

        Returns:
            Set of variable names (e.g., {'video1', 'video2', 'emotion'})

        Used to validate trial list has required columns.
        """
        variables = set()
        for phase in self.phases:
            variables.update(phase.get_required_variables())
        return variables

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize procedure to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'phases': [phase.to_dict() for phase in self.phases]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Procedure':
        """
        Deserialize procedure from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Procedure instance
        """
        from .phases import phase_from_dict  # Import here to avoid circular imports

        procedure = cls(data['name'])

        for phase_data in data.get('phases', []):
            phase = phase_from_dict(phase_data)
            procedure.add_phase(phase)

        return procedure
