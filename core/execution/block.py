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

    def execute(self, device_manager, lsl_outlet, data_collector):
        """
        Execute all trials in this block with zero-ISI preloading.

        Args:
            device_manager: For accessing displays/audio
            lsl_outlet: For sending LSL markers
            data_collector: For saving trial data
        """
        # Phase 3: Create continuous preloader for zero-ISI support
        from .continuous_preloader import ContinuousPreloader
        preloader = ContinuousPreloader(device_manager)

        try:
            if self.block_type == 'simple':
                # Single execution (e.g., baseline)
                self.procedure.execute(
                    trial_data=None,
                    device_manager=device_manager,
                    lsl_outlet=lsl_outlet,
                    data_collector=data_collector,
                    preloader=preloader  # Phase 3: Enable preloading
                )

            elif self.block_type == 'trial_based':
                # Get (possibly randomized) trial order
                # NOTE: Randomization happens HERE, before execution starts
                # This enables lookahead for preloading (E-Prime's TopOfProcedure approach)
                trials = self.trial_list.get_trials(self.randomization)

                for i, trial in enumerate(trials, start=1):
                    # Add trial_index to trial data for marker template resolution (1-based indexing)
                    trial_data_with_index = trial.data.copy()
                    trial_data_with_index['trial_index'] = i

                    # Execute procedure with this trial's data
                    trial_result = self.procedure.execute(
                        trial_data=trial_data_with_index,
                        device_manager=device_manager,
                        lsl_outlet=lsl_outlet,
                        data_collector=data_collector,
                        preloader=preloader  # Phase 3: Enable zero-ISI preloading
                    )

                    # Store result
                    trial.result = trial_result
                    self.completed_trials.append(trial)

                    # Save intermediate data (in case of crash)
                    data_collector.save_trial(trial)

                    self.current_trial_index += 1

        finally:
            # Phase 3: Ensure preloader shutdown (releases resources, joins threads)
            preloader.shutdown()

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
