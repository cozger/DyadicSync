"""
BranchBlock class for DyadicSync Framework.

A container block that holds multiple variant blocks as alternatives.
On each "run", one variant is selected based on a selection strategy.
"""

from typing import Dict, List, Optional, Any, Tuple, Union
import random

from .block import Block, RandomizationConfig
from .selection_config import SelectionConfig
from .trial_list import TrialList
from .trial import Trial


class BranchBlock:
    """
    Container for variant blocks with selection-based execution.

    A BranchBlock holds multiple variant blocks (alternatives) and selects
    which variant to execute for each run based on the selection strategy.

    Example use cases:
    - P1 Viewer / P2 Viewer / Joint viewing conditions
    - High/Medium/Low intensity stimuli
    - Different task instructions per condition

    Key concepts:
    - Variants are regular Block objects with block_type='variant'
    - Each run selects one variant to execute
    - Trial data comes from shared trial list or per-variant lists
    - Selection is pre-computed before execution starts
    """

    def __init__(self, name: str):
        """
        Initialize branch block.

        Args:
            name: Human-readable block name
        """
        self.name = name
        self.block_type = 'branch'  # For compatibility with code that accesses block.block_type

        # Variant blocks (alternatives)
        self.variant_blocks: List[Block] = []

        # Selection configuration
        self.selection: SelectionConfig = SelectionConfig()

        # Total runs (0 = derive from trial lists)
        self.total_runs: int = 0

        # Shared trial list (fallback for variants without their own)
        self.trial_list: Optional[TrialList] = None

        # Randomization for shared trial list
        self.randomization: RandomizationConfig = RandomizationConfig()

        # Runtime state (set during prepare_execution)
        self._run_plan: Optional[List[Tuple[int, Dict]]] = None
        self._current_run_index: int = 0
        self._completed_runs: List[Dict] = []

    def get_run_progress(self) -> Optional[Dict[str, Any]]:
        """Get current run progress within this branch block.

        Returns:
            Dict with current_run (1-based) and total_runs, or None if not executing.
        """
        if self._run_plan is None:
            return None
        return {
            'current_run': self._current_run_index + 1,
            'total_runs': len(self._run_plan)
        }

    def add_variant(self, variant: Block, index: Optional[int] = None):
        """
        Add a variant block.

        Args:
            variant: Block to add as variant
            index: Position to insert (None = append to end)

        Raises:
            ValueError: If attempting to add a BranchBlock (nesting not supported)
        """
        # Prevent nesting of branch blocks
        if isinstance(variant, BranchBlock):
            raise ValueError("Branch blocks cannot be nested inside other branch blocks.")

        # Ensure block_type is 'variant'
        variant.block_type = 'variant'

        if index is None:
            self.variant_blocks.append(variant)
        else:
            self.variant_blocks.insert(index, variant)

    def remove_variant(self, index: int):
        """
        Remove variant at index.

        Args:
            index: Variant index to remove
        """
        del self.variant_blocks[index]

    def reorder_variant(self, old_index: int, new_index: int):
        """
        Move variant from old_index to new_index.

        Args:
            old_index: Current variant index
            new_index: Target variant index
        """
        variant = self.variant_blocks.pop(old_index)
        self.variant_blocks.insert(new_index, variant)

    def get_variant_names(self) -> List[str]:
        """
        Get list of variant names.

        Returns:
            List of variant block names
        """
        return [v.name for v in self.variant_blocks]

    def get_effective_runs(self) -> int:
        """
        Calculate total runs from trial lists if not explicitly set.

        Priority:
        1. Explicit total_runs if > 0
        2. Sum of variant trial list lengths
        3. Shared trial list length

        Returns:
            Total number of runs
        """
        if self.total_runs > 0:
            return self.total_runs

        # Sum of variant trial lists
        variant_counts = sum(
            len(v.trial_list.trials) if v.trial_list else 0
            for v in self.variant_blocks
        )
        if variant_counts > 0:
            return variant_counts

        # Shared trial list
        if self.trial_list:
            return len(self.trial_list.trials)

        return 0

    def prepare_execution(self, seed: Optional[int] = None) -> List[Tuple[int, Dict]]:
        """
        Pre-compute (variant_index, trial_data) pairs for all runs.

        Called before execution starts. Returns complete run plan.

        Args:
            seed: Random seed for schedule generation (None = random)

        Returns:
            List of (variant_index, trial_data_dict) tuples
        """
        total = self.get_effective_runs()
        if total == 0:
            return []

        variant_names = self.get_variant_names()
        if not variant_names:
            return []

        # Generate selection schedule
        schedule = self.selection.generate_schedule(variant_names, total, seed)

        # Get trials from shared list (if applicable)
        # Always shuffle shared trials — BranchBlock distributes videos across
        # variants, so random-without-replacement is the correct behavior.
        # Each session gets a fresh random order via OS entropy.
        shared_trials = []
        if self.trial_list:
            import random as _random
            shared_trials = self.trial_list.trials.copy()
            _rng = _random.Random(seed)  # seed=None → OS entropy → different each session
            _rng.shuffle(shared_trials)
            print(f"[BranchBlock] Shuffled {len(shared_trials)} shared trials (seed={seed})")

        # Get trials from variant lists
        variant_trials = {}
        for i, variant in enumerate(self.variant_blocks):
            if variant.trial_list:
                # Each variant uses its own randomization config
                variant_trials[i] = variant.trial_list.get_trials(variant.randomization)
            else:
                variant_trials[i] = []

        # Track per-variant and shared trial indices
        variant_trial_idx = {i: 0 for i in range(len(self.variant_blocks))}
        shared_trial_idx = 0

        # Build run plan
        run_plan = []
        for run_idx, variant_idx in enumerate(schedule):
            variant = self.variant_blocks[variant_idx]

            if variant.trial_list and variant_trials[variant_idx]:
                # Use variant's own trial list
                if variant_trial_idx[variant_idx] < len(variant_trials[variant_idx]):
                    trial = variant_trials[variant_idx][variant_trial_idx[variant_idx]]
                    trial_data = trial.data.copy()
                    variant_trial_idx[variant_idx] += 1
                else:
                    # Ran out of variant trials - use empty data
                    trial_data = {}
            elif shared_trials:
                # Use shared trial list
                if shared_trial_idx < len(shared_trials):
                    trial = shared_trials[shared_trial_idx]
                    trial_data = trial.data.copy()
                    shared_trial_idx += 1
                else:
                    # Ran out of shared trials - use empty data
                    trial_data = {}
            else:
                # No trial data available
                trial_data = {}

            # Add branch metadata to trial data
            trial_data['_branch_block'] = self.name
            trial_data['_variant_name'] = variant.name
            trial_data['_variant_index'] = variant_idx
            trial_data['_run_index'] = run_idx

            # Derive role variables from variant name for marker templates
            variant_lower = variant.name.lower()
            if 'p1' in variant_lower and 'viewer' in variant_lower:
                trial_data['role_p1'] = 'viewer'
                trial_data['role_p2'] = 'observer'
            elif 'p2' in variant_lower and 'viewer' in variant_lower:
                trial_data['role_p1'] = 'observer'
                trial_data['role_p2'] = 'viewer'
            else:
                trial_data['role_p1'] = 'joint'
                trial_data['role_p2'] = 'joint'

            run_plan.append((variant_idx, trial_data))

        self._run_plan = run_plan
        return run_plan

    def execute(self, device_manager, lsl_outlet, data_collector, on_complete=None):
        """
        Execute all runs with variant selection.

        Args:
            device_manager: For accessing displays/audio
            lsl_outlet: For sending LSL markers
            data_collector: For saving trial data
            on_complete: Callback function() called when all runs complete

        Note:
            This method is non-blocking. It schedules runs sequentially and returns immediately.
            on_complete is called when all runs finish.
        """
        # Phase 3: Create continuous preloader for zero-ISI support
        from .continuous_preloader import ContinuousPreloader
        preloader = ContinuousPreloader(device_manager)

        # Prepare execution plan if not already done
        if self._run_plan is None:
            self.prepare_execution()

        if not self._run_plan:
            # No runs to execute
            preloader.shutdown()
            if on_complete:
                on_complete()
            return

        self._current_run_index = 0
        self._completed_runs = []

        def finish_block():
            """Cleanup and complete block."""
            preloader.shutdown()
            if on_complete:
                on_complete()

        def execute_run_at_index(index):
            """Execute run at given index, then schedule next run."""
            if index >= len(self._run_plan):
                # All runs complete
                print(f"[BranchBlock] Completed all {len(self._run_plan)} runs")
                finish_block()
                return

            variant_idx, trial_data = self._run_plan[index]
            variant = self.variant_blocks[variant_idx]

            # Add trial_index for marker template resolution (1-based)
            trial_data_with_index = trial_data.copy()
            trial_data_with_index['trial_index'] = index + 1

            print(f"[BranchBlock] Run {index + 1}/{len(self._run_plan)}: "
                  f"variant '{variant.name}' (idx={variant_idx})")

            def on_run_complete(run_result):
                """Called when current run completes."""
                # Add branch metadata to result
                if run_result is None:
                    run_result = {}
                run_result['_branch_block'] = self.name
                run_result['_variant_name'] = variant.name
                run_result['_variant_index'] = variant_idx

                self._completed_runs.append({
                    'run_index': index,
                    'variant_index': variant_idx,
                    'variant_name': variant.name,
                    'trial_data': trial_data,
                    'result': run_result
                })

                self._current_run_index = index + 1

                # Schedule next run
                import pyglet
                pyglet.clock.schedule_once(lambda dt: execute_run_at_index(index + 1), 0.0)

            # Execute variant's procedure with trial data
            if variant.procedure:
                variant.procedure.execute(
                    trial_data=trial_data_with_index,
                    device_manager=device_manager,
                    lsl_outlet=lsl_outlet,
                    data_collector=data_collector,
                    preloader=preloader,
                    on_complete=on_run_complete
                )
            else:
                # No procedure - skip this run
                print(f"[BranchBlock] Warning: variant '{variant.name}' has no procedure")
                on_run_complete({})

        # Start executing runs from index 0
        import pyglet
        pyglet.clock.schedule_once(lambda dt: execute_run_at_index(0), 0.0)

    def validate(self) -> List[str]:
        """
        Validate branch block configuration.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        if not self.variant_blocks:
            errors.append("No variant blocks defined")

        # Validate selection config
        selection_errors = self.selection.validate()
        errors.extend([f"Selection: {e}" for e in selection_errors])

        # Validate each variant
        for i, variant in enumerate(self.variant_blocks):
            if not variant.procedure:
                errors.append(f"Variant {i} ({variant.name}): No procedure defined")
            else:
                procedure_errors = variant.procedure.validate()
                errors.extend([f"Variant {i} ({variant.name}): {e}" for e in procedure_errors])

            # Validate variant's trial list if present
            if variant.trial_list:
                tl_errors = variant.trial_list.validate()
                errors.extend([f"Variant {i} ({variant.name}) trial list: {e}" for e in tl_errors])

        # Validate shared trial list if present
        if self.trial_list:
            tl_errors = self.trial_list.validate()
            errors.extend([f"Shared trial list: {e}" for e in tl_errors])

        # Check trial list coverage
        total_runs = self.get_effective_runs()
        if total_runs == 0:
            errors.append("No trials available (no trial lists configured)")
        else:
            # Verify each variant has enough trials
            distribution = self.selection.calculate_distribution(
                self.get_variant_names(), total_runs
            )

            for i, variant in enumerate(self.variant_blocks):
                expected_runs = distribution.get(variant.name, 0)
                if variant.trial_list:
                    available = len(variant.trial_list.trials)
                    if available < expected_runs:
                        errors.append(
                            f"Variant '{variant.name}' has {available} trials "
                            f"but needs {expected_runs} runs"
                        )

        return errors

    def get_trial_count(self) -> int:
        """
        Get total number of runs (trials) in this branch block.

        Returns:
            Total run count
        """
        return self.get_effective_runs()

    def calculate_accurate_duration(self) -> Optional[float]:
        """
        Calculate accurate duration for branch block.

        Delegates to each variant's calculate_accurate_duration if available,
        otherwise falls back to estimated duration.

        Returns:
            Total duration in seconds, or None if unable to calculate
        """
        if not self.variant_blocks:
            return 0.0

        total_runs = self.get_effective_runs()
        if total_runs == 0:
            return 0.0

        # Calculate weighted duration using variant distributions
        variant_names = self.get_variant_names()
        distribution = self.selection.calculate_distribution(variant_names, total_runs)

        total_duration = 0.0
        for i, variant in enumerate(self.variant_blocks):
            runs = distribution.get(variant.name, 0)
            if runs > 0:
                # Try accurate calculation on each variant
                variant_duration = variant.calculate_accurate_duration()
                if variant_duration is not None and variant.trial_list:
                    # Scale by runs vs trial count
                    trial_count = len(variant.trial_list.trials) if variant.trial_list.trials else 1
                    per_trial = variant_duration / max(trial_count, 1)
                    total_duration += runs * per_trial
                elif variant.procedure:
                    # Fall back to estimated per-run duration
                    total_duration += runs * variant.procedure.get_estimated_duration()

        return total_duration if total_duration > 0 else None

    def get_estimated_duration(self) -> float:
        """
        Estimate total duration in seconds.

        Returns:
            Estimated duration (sum of all runs)
        """
        if not self.variant_blocks:
            return 0.0

        total_runs = self.get_effective_runs()
        if total_runs == 0:
            return 0.0

        # Calculate weighted average procedure duration
        variant_names = self.get_variant_names()
        distribution = self.selection.calculate_distribution(variant_names, total_runs)

        total_duration = 0.0
        for i, variant in enumerate(self.variant_blocks):
            if variant.procedure:
                runs = distribution.get(variant.name, 0)
                duration_per_run = variant.procedure.get_estimated_duration()
                total_duration += runs * duration_per_run

        return total_duration

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize branch block to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'name': self.name,
            'type': 'branch',
            'variant_blocks': [v.to_dict() for v in self.variant_blocks],
            'selection': self.selection.to_dict(),
            'total_runs': self.total_runs,
            'trial_list': self.trial_list.to_dict() if self.trial_list else None,
            'randomization': self.randomization.to_dict()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'BranchBlock':
        """
        Deserialize branch block from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            BranchBlock instance
        """
        branch = cls(name=data['name'])

        # Load variant blocks
        for variant_data in data.get('variant_blocks', []):
            # Force block_type to 'variant' for deserialization
            variant_data = variant_data.copy()
            variant_data['type'] = 'variant'
            variant = Block.from_dict(variant_data)
            branch.add_variant(variant)

        # Load selection config
        if data.get('selection'):
            branch.selection = SelectionConfig.from_dict(data['selection'])

        # Load total_runs
        branch.total_runs = data.get('total_runs', 0)

        # Load shared trial list
        if data.get('trial_list'):
            branch.trial_list = TrialList.from_dict(data['trial_list'])

        # Load randomization
        if data.get('randomization'):
            branch.randomization = RandomizationConfig.from_dict(data['randomization'])

        return branch

    def __repr__(self):
        return (
            f"BranchBlock(name='{self.name}', "
            f"variants={len(self.variant_blocks)}, "
            f"runs={self.get_effective_runs()})"
        )
