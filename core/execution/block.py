"""
Block class for DyadicSync Framework.

A block represents a collection of trials with a shared procedure.
"""

from typing import Dict, List, Optional, Any
from .procedure import Procedure
from .constraints import Constraint


class RandomizationConfig:
    """
    Configuration for trial list randomization.
    """

    def __init__(self):
        self.method: str = 'none'  # 'none', 'full', 'block', 'latin_square', 'constrained'
        self.seed: Optional[int] = None  # Random seed for reproducibility
        self.constraints: List = []  # Ordering constraints

        # Viewer randomization settings (for turn-taking conditions)
        self.viewer_randomization_enabled: bool = True  # Auto-assign viewers for turn_taking trials
        self.viewer_seed: Optional[int] = None  # Separate seed for viewer assignment

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'method': self.method,
            'seed': self.seed,
            'constraints': [c.to_dict() for c in self.constraints],
            'viewer_randomization_enabled': self.viewer_randomization_enabled,
            'viewer_seed': self.viewer_seed
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RandomizationConfig':
        """Deserialize from dictionary."""
        config = cls()
        config.method = data.get('method', 'none')
        config.seed = data.get('seed')

        # Deserialize constraints
        constraint_data = data.get('constraints', [])
        config.constraints = [Constraint.from_dict(c) for c in constraint_data]

        # Viewer randomization settings
        config.viewer_randomization_enabled = data.get('viewer_randomization_enabled', True)
        config.viewer_seed = data.get('viewer_seed')

        return config


class Block:
    """
    A block represents a collection of trials with a shared procedure.

    Examples:
    - Baseline block: Single trial, FixationPhase(240s)
    - Video block: 20 trials, each following Fixation→Video→Rating procedure
    - Instruction block: Single trial, InstructionPhase
    - Variant block: Used within BranchBlock as an alternative

    Components:
    - Procedure: Template defining phase sequence
    - Trial List: Data source (CSV or manual)
    - Randomization: How to order trials

    Block Types:
    - 'trial_based': Execute procedure once per trial from trial list
    - 'simple': Execute procedure once (no trial list needed)
    - 'variant': Used within BranchBlock (has procedure, optional trial list)
    """

    # Valid block types
    BLOCK_TYPES = ['trial_based', 'simple', 'variant']

    def __init__(self, name: str, block_type: str = 'trial_based'):
        """
        Initialize block.

        Args:
            name: Human-readable block name (e.g., "Emotional Videos")
            block_type: 'trial_based', 'simple', or 'variant'
        """
        self.name = name
        self.block_type = block_type

        # Procedure and trials
        self.procedure: Optional[Procedure] = None
        self.trial_list = None  # Will be TrialList instance
        self.randomization: RandomizationConfig = RandomizationConfig()

        # Weight for branch block selection (default 1.0)
        self.weight: float = 1.0

        # Runtime state
        self.current_trial_index: int = 0
        self.completed_trials: List = []  # Will be List[Trial]

    def execute(self, device_manager, lsl_outlet, data_collector, on_complete=None):
        """
        Execute all trials in this block with zero-ISI preloading (non-blocking, callback-based).

        Args:
            device_manager: For accessing displays/audio
            lsl_outlet: For sending LSL markers
            data_collector: For saving trial data
            on_complete: Callback function() called when block completes

        Note:
            This method is non-blocking. It schedules trials sequentially and returns immediately.
            on_complete is called when all trials finish.
        """
        # Phase 3: Create continuous preloader for zero-ISI support
        from .continuous_preloader import ContinuousPreloader
        preloader = ContinuousPreloader(device_manager)

        def finish_block():
            """Cleanup and complete block."""
            # Phase 3: Ensure preloader shutdown (releases resources, joins threads)
            preloader.shutdown()
            if on_complete:
                on_complete()

        if self.block_type == 'simple':
            # Single execution (e.g., baseline)
            def on_procedure_complete(result):
                finish_block()

            self.procedure.execute(
                trial_data=None,
                device_manager=device_manager,
                lsl_outlet=lsl_outlet,
                data_collector=data_collector,
                preloader=preloader,  # Phase 3: Enable preloading
                on_complete=on_procedure_complete
            )

        elif self.block_type == 'trial_based':
            # Get (possibly randomized) trial order
            # NOTE: Randomization happens HERE, before execution starts
            # This enables lookahead for preloading (E-Prime's TopOfProcedure approach)
            trials = self.trial_list.get_trials(self.randomization)

            # Recursive function to execute trials sequentially
            def execute_trial_at_index(index):
                """Execute trial at given index, then schedule next trial."""
                if index >= len(trials):
                    # All trials complete - shutdown and call completion callback
                    finish_block()
                    return

                trial = trials[index]

                # Add trial_index to trial data for marker template resolution (1-based indexing)
                trial_data_with_index = trial.data.copy()
                trial_data_with_index['trial_index'] = index + 1

                # Define completion callback for this trial
                def on_trial_complete(trial_result):
                    """Called when current trial completes."""
                    # Store result
                    trial.result = trial_result
                    self.completed_trials.append(trial)

                    # Save intermediate data (in case of crash)
                    data_collector.save_trial(trial)

                    self.current_trial_index += 1

                    # Schedule next trial (use pyglet.clock to avoid deep recursion)
                    import pyglet
                    pyglet.clock.schedule_once(lambda dt: execute_trial_at_index(index + 1), 0.0)

                # Execute procedure with this trial's data (non-blocking)
                self.procedure.execute(
                    trial_data=trial_data_with_index,
                    device_manager=device_manager,
                    lsl_outlet=lsl_outlet,
                    data_collector=data_collector,
                    preloader=preloader,  # Phase 3: Enable zero-ISI preloading
                    on_complete=on_trial_complete
                )

            # Start executing trials from index 0
            import pyglet
            pyglet.clock.schedule_once(lambda dt: execute_trial_at_index(0), 0.0)

    def validate(self) -> List[str]:
        """
        Validate block configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.procedure:
            errors.append("No procedure defined")
        else:
            errors.extend(self.procedure.validate())

        if self.block_type == 'trial_based':
            if not self.trial_list:
                errors.append("Trial-based block requires trial list")
            else:
                errors.extend(self.trial_list.validate())

        return errors

    def get_trial_count(self) -> int:
        """
        Number of trials in this block.

        Returns:
            Trial count
        """
        if self.block_type == 'simple':
            return 1
        return len(self.trial_list.trials) if self.trial_list else 0

    def get_estimated_duration(self) -> float:
        """
        Estimated block duration in seconds.

        Returns:
            Duration in seconds
        """
        if not self.procedure:
            return 0.0

        trial_duration = self.procedure.get_estimated_duration()
        return trial_duration * self.get_trial_count()

    def calculate_accurate_duration(self) -> Optional[float]:
        """
        Calculate accurate block duration by reading video metadata from CSV files.

        This method uses two-tier caching:
        1. _cached_video_duration_total: Sum of video durations (survives phase changes)
        2. _cached_duration: Final total (cleared when phases or CSV change)

        When phases change, only fixation durations need recalculating - video
        probing is skipped if video cache exists.

        Returns:
            Total duration in seconds, or None if unable to calculate

        Notes:
            - Only works for trial-based blocks with CSV trial lists
            - For simple blocks, uses get_estimated_duration() instead
            - Call invalidate_duration_cache() when phases change
            - Call invalidate_video_cache() when CSV changes
        """
        print(f"\n[DURATION_CALC] ═══ Starting calculation for block '{self.name}' ═══")

        # Return cached result if available
        if hasattr(self, '_cached_duration') and self._cached_duration is not None:
            print(f"[DURATION_CALC] ✓ Using cached duration: {self._cached_duration:.1f}s")
            return self._cached_duration

        # Simple blocks: Use estimated duration
        if self.block_type == 'simple':
            print(f"[DURATION_CALC] Simple block - using estimated duration")
            duration = self.get_estimated_duration()
            self._cached_duration = duration
            return duration

        # Trial-based blocks require procedure and trial list
        if not self.procedure or not self.trial_list:
            print(f"[DURATION_CALC] ✗ No procedure or trial list configured")
            return None

        try:
            # Check if we have cached video durations (skip re-probing)
            if hasattr(self, '_cached_video_duration_total') and self._cached_video_duration_total is not None:
                print(f"[DURATION_CALC] Using cached video duration: {self._cached_video_duration_total:.1f}s")
                fixed_total = self._calculate_fixed_phases_total()
                total_duration = self._cached_video_duration_total + fixed_total
                self._cached_duration = total_duration
                print(f"[DURATION_CALC] ✓ Total: {total_duration:.1f}s ({total_duration/60:.1f} min) [video cached, phases recalculated]")
                return total_duration

            # Full calculation with video probing
            from .phases.fixation_phase import FixationPhase
            from .phases.video_phase import VideoPhase
            from .phases.rating_phase import RatingPhase
            from .phases.instruction_phase import InstructionPhase
            from utilities.video_duration import probe_videos_parallel

            # Get trials (possibly randomized)
            trials = self.trial_list.get_trials(self.randomization)

            if not trials:
                print(f"[DURATION_CALC] ✗ No trials found in trial list")
                return None

            print(f"[DURATION_CALC] Processing {len(trials)} trials...")

            # Debug: show what phases exist in procedure
            print(f"[DURATION_CALC] Phases in procedure: {[type(p).__name__ for p in self.procedure.phases]}")

            # Single pass: collect video paths AND all fixed-duration phases
            all_video_paths = []
            fixed_phases_total = 0.0

            for trial in trials:
                trial_data = trial.data.copy()
                for phase in self.procedure.phases:
                    # FixationPhase (and BaselinePhase which inherits from it)
                    if isinstance(phase, FixationPhase):
                        fixed_phases_total += phase.duration

                    # VideoPhase - collect paths for probing
                    elif isinstance(phase, VideoPhase):
                        rendered = phase.render(trial_data)
                        all_video_paths.append((rendered.participant_1_video, rendered.participant_2_video))

                    # RatingPhase - use timeout if set
                    elif isinstance(phase, RatingPhase):
                        if hasattr(phase, 'timeout') and phase.timeout is not None:
                            fixed_phases_total += phase.timeout

                    # InstructionPhase - use duration if set
                    elif isinstance(phase, InstructionPhase):
                        if hasattr(phase, 'duration') and phase.duration is not None:
                            fixed_phases_total += phase.duration

            print(f"[DURATION_CALC] Fixed phases total: {fixed_phases_total:.1f}s ({fixed_phases_total/len(trials):.1f}s per trial)")

            # Parallel probe all unique videos
            unique_videos = list(set(v for pair in all_video_paths for v in pair))
            durations = probe_videos_parallel(unique_videos)

            # Sum video durations (max of each pair)
            video_total = sum(
                max(durations.get(p1) or 0, durations.get(p2) or 0)
                for p1, p2 in all_video_paths
            )

            # Cache video duration separately (survives phase changes)
            self._cached_video_duration_total = video_total

            total_duration = fixed_phases_total + video_total
            self._cached_duration = total_duration
            print(f"[DURATION_CALC] ✓ Total: {total_duration:.1f}s ({total_duration/60:.1f} min) - {len(trials)} trials, {len(unique_videos)} unique videos")
            return total_duration

        except Exception as e:
            # Log error but don't crash
            import logging
            import traceback
            print(f"[DURATION_CALC] ✗ ERROR: {e}")
            traceback.print_exc()
            logging.warning(f"Failed to calculate accurate duration for block '{self.name}': {e}")
            return None

    def _calculate_fixed_phases_total(self) -> float:
        """
        Calculate total duration of all fixed-duration phases without re-probing videos.

        Includes:
        - FixationPhase.duration
        - BaselinePhase.duration (inherits from FixationPhase)
        - RatingPhase.timeout (if set)
        - InstructionPhase.duration (if set)

        Returns:
            Total fixed-phase duration across all trials in seconds
        """
        from .phases.fixation_phase import FixationPhase
        from .phases.rating_phase import RatingPhase
        from .phases.instruction_phase import InstructionPhase

        if not self.procedure or not self.trial_list:
            return 0.0

        trial_count = len(self.trial_list.trials)

        # Sum all fixed-duration phases per trial
        fixed_per_trial = 0.0
        for phase in self.procedure.phases:
            if isinstance(phase, FixationPhase):
                # Includes BaselinePhase (inherits from FixationPhase)
                fixed_per_trial += phase.duration
            elif isinstance(phase, RatingPhase):
                if hasattr(phase, 'timeout') and phase.timeout is not None:
                    fixed_per_trial += phase.timeout
            elif isinstance(phase, InstructionPhase):
                if hasattr(phase, 'duration') and phase.duration is not None:
                    fixed_per_trial += phase.duration

        return fixed_per_trial * trial_count

    def invalidate_duration_cache(self):
        """
        Invalidate cached duration calculation (keeps video cache).

        Call this when procedure phases are modified (add/remove/reorder).
        Video durations are preserved - only fixation totals are recalculated.
        """
        if hasattr(self, '_cached_duration'):
            self._cached_duration = None
        # NOTE: Don't clear _cached_video_duration_total here!
        # Video cache survives phase changes.

    def invalidate_video_cache(self):
        """
        Invalidate video duration cache (full re-probe needed).

        Call this when:
        - CSV trial list changes
        - Video files are updated
        - User clicks "Recalculate" button
        """
        if hasattr(self, '_cached_video_duration_total'):
            self._cached_video_duration_total = None
        self.invalidate_duration_cache()

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize block to dictionary.

        Returns:
            Dictionary representation
        """
        result = {
            'name': self.name,
            'type': self.block_type,
            'procedure': self.procedure.to_dict() if self.procedure else None,
            'trial_list': self.trial_list.to_dict() if self.trial_list else None,
            'randomization': self.randomization.to_dict()
        }

        # Only include weight if it's not the default (1.0)
        if self.weight != 1.0:
            result['weight'] = self.weight

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Block':
        """
        Deserialize block from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Block instance
        """
        from .procedure import Procedure

        block = cls(
            name=data['name'],
            block_type=data.get('type', 'trial_based')
        )

        if data.get('procedure'):
            block.procedure = Procedure.from_dict(data['procedure'])

        # Load trial list if present
        if data.get('trial_list'):
            from .trial_list import TrialList
            block.trial_list = TrialList.from_dict(data['trial_list'])

        if data.get('randomization'):
            block.randomization = RandomizationConfig.from_dict(data['randomization'])

        # Load weight (for variant blocks in branch blocks)
        block.weight = data.get('weight', 1.0)

        return block
