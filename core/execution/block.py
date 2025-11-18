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

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            'method': self.method,
            'seed': self.seed,
            'constraints': [c.to_dict() for c in self.constraints]
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

        return config


class Block:
    """
    A block represents a collection of trials with a shared procedure.

    Examples:
    - Baseline block: Single trial, FixationPhase(240s)
    - Video block: 20 trials, each following Fixation→Video→Rating procedure
    - Instruction block: Single trial, InstructionPhase

    Components:
    - Procedure: Template defining phase sequence
    - Trial List: Data source (CSV or manual)
    - Randomization: How to order trials
    """

    def __init__(self, name: str, block_type: str = 'trial_based'):
        """
        Initialize block.

        Args:
            name: Human-readable block name (e.g., "Emotional Videos")
            block_type: 'trial_based' or 'simple' (no trials, just procedure)
        """
        self.name = name
        self.block_type = block_type

        # Procedure and trials
        self.procedure: Optional[Procedure] = None
        self.trial_list = None  # Will be TrialList instance
        self.randomization: RandomizationConfig = RandomizationConfig()

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

        This method:
        1. Resolves template variables ({video1}, etc.) using actual trial data
        2. Probes video files with FFprobe to get real durations
        3. Sums fixed-duration phases (fixations, videos)
        4. Ignores variable-duration phases (ratings, instructions)

        Returns:
            Total duration in seconds, or None if unable to calculate

        Notes:
            - Only works for trial-based blocks with CSV trial lists
            - For simple blocks, uses get_estimated_duration() instead
            - Results are cached; call invalidate_duration_cache() to refresh
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
            from .phases.fixation_phase import FixationPhase
            from .phases.video_phase import VideoPhase
            from utilities.video_duration import get_max_video_duration

            # Get trials (possibly randomized)
            trials = self.trial_list.get_trials(self.randomization)

            if not trials:
                print(f"[DURATION_CALC] ✗ No trials found in trial list")
                return None

            print(f"[DURATION_CALC] Processing {len(trials)} trials...")
            total_duration = 0.0
            trial_count = 0

            # Calculate duration for each trial
            for trial in trials:
                trial_count += 1
                trial_duration = 0.0
                print(f"\n[DURATION_CALC] --- Trial {trial_count}/{len(trials)} ---")

                # Render procedure with trial data to resolve templates
                trial_data = trial.data.copy()

                # For each phase in procedure
                for phase in self.procedure.phases:
                    # Render phase to resolve template variables
                    rendered_phase = phase.render(trial_data) if trial_data else phase

                    # FixationPhase: Use configured duration
                    if isinstance(rendered_phase, FixationPhase):
                        print(f"[DURATION_CALC]   Fixation: {rendered_phase.duration:.1f}s")
                        total_duration += rendered_phase.duration
                        trial_duration += rendered_phase.duration

                    # VideoPhase: Probe video files for actual duration
                    elif isinstance(rendered_phase, VideoPhase):
                        print(f"[DURATION_CALC]   VideoPhase - probing files...")
                        video_duration = get_max_video_duration(
                            rendered_phase.participant_1_video,
                            rendered_phase.participant_2_video
                        )
                        if video_duration is not None:
                            total_duration += video_duration
                            trial_duration += video_duration
                            print(f"[DURATION_CALC]   Added {video_duration:.2f}s to trial duration")
                        else:
                            print(f"[DURATION_CALC]   ⚠ Unable to read video duration (skipping)")
                        # If unable to read video, skip (don't break entire calculation)

                    # RatingPhase, InstructionPhase: Ignore (variable duration)
                    # User specified to ignore these in requirements
                    else:
                        phase_name = type(rendered_phase).__name__
                        print(f"[DURATION_CALC]   {phase_name}: Variable duration (ignored)")

                print(f"[DURATION_CALC] Trial {trial_count} total: {trial_duration:.2f}s")

            # Cache result
            self._cached_duration = total_duration
            print(f"\n[DURATION_CALC] ═══ TOTAL DURATION: {total_duration:.2f}s ({total_duration/60:.1f} min) ═══\n")
            return total_duration

        except Exception as e:
            # Log error but don't crash
            import logging
            import traceback
            print(f"[DURATION_CALC] ✗ ERROR: {e}")
            traceback.print_exc()
            logging.warning(f"Failed to calculate accurate duration for block '{self.name}': {e}")
            return None

    def invalidate_duration_cache(self):
        """
        Invalidate cached duration calculation.

        Call this when:
        - CSV trial list changes
        - Procedure phases are modified
        - Video files are updated
        """
        if hasattr(self, '_cached_duration'):
            self._cached_duration = None

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize block to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'type': self.block_type,
            'procedure': self.procedure.to_dict() if self.procedure else None,
            'trial_list': self.trial_list.to_dict() if self.trial_list else None,
            'randomization': self.randomization.to_dict()
        }

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

        return block
