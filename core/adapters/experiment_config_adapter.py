"""
Adapter for converting between ExperimentConfig and Timeline formats.

This module provides bidirectional conversion:
- ExperimentConfig (GUI format) → Timeline (execution format)
- Timeline (execution format) → ExperimentConfig (GUI format)

Design decisions:
- Trials are grouped by question configuration into separate blocks
- Multiple questions per trial → multiple RatingPhases in procedure
- Baseline block created if baseline_duration > 0
- Audio offset ignored (deprecated, Phase 2 will use timestamp sync)
- Template variables {video1}, {video2} used for video paths
"""

from typing import List, Dict, Any, Optional
import os
import tempfile
from collections import defaultdict

# Config imports (absolute imports since config is sibling to core)
import sys
from pathlib import Path
# Add parent directory to path for absolute imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from config.experiment import ExperimentConfig
from config.trial import Trial as ConfigTrial
from config.question import Question

# Execution imports (relative to core package)
from core.execution.timeline import Timeline
from core.execution.block import Block, RandomizationConfig
from core.execution.procedure import Procedure
from core.execution.trial_list import TrialList
from core.execution.trial import Trial as ExecTrial
from core.execution.phases import (
    BaselinePhase,
    FixationPhase,
    VideoPhase,
    RatingPhase
)
from core.markers import MarkerBinding


class ExperimentConfigAdapter:
    """
    Adapter for converting between ExperimentConfig and Timeline formats.

    Handles the structural transformation between the flat, trial-based
    ExperimentConfig (used by GUI) and the hierarchical, block-based
    Timeline (used by execution engine).
    """

    @staticmethod
    def to_timeline(config: ExperimentConfig) -> Timeline:
        """
        Convert ExperimentConfig to Timeline.

        Args:
            config: ExperimentConfig instance from GUI

        Returns:
            Timeline instance ready for execution

        Conversion logic:
        1. Create baseline block if baseline_duration > 0
        2. Group enabled trials by question configuration
        3. For each group, create a block with:
           - Procedure with FixationPhase → VideoPhase → RatingPhase(s)
           - TrialList with trial data
        """
        timeline = Timeline()

        # 1. Create baseline block if needed
        if config.baseline_duration > 0:
            baseline_block = ExperimentConfigAdapter._create_baseline_block(
                config.baseline_duration
            )
            timeline.add_block(baseline_block)

        # 2. Get enabled trials
        enabled_trials = config.get_enabled_trials()
        if not enabled_trials:
            return timeline

        # 3. Group trials by question configuration
        # For now, we'll create a single block with all trials
        # In future, we can split by question_override
        trial_groups = ExperimentConfigAdapter._group_trials_by_question(
            enabled_trials, config.global_defaults
        )

        # 4. Create a block for each trial group
        for group_idx, (question_signature, trials_in_group) in enumerate(trial_groups.items()):
            block = ExperimentConfigAdapter._create_video_block(
                name=f"Video Trials - Group {group_idx + 1}",
                trials=trials_in_group,
                questions=question_signature,  # List of Question objects
                audio_device_p1=config.audio_device_p1,
                audio_device_p2=config.audio_device_p2
            )
            timeline.add_block(block)

        return timeline

    @staticmethod
    def from_timeline(timeline: Timeline) -> ExperimentConfig:
        """
        Convert Timeline to ExperimentConfig.

        Args:
            timeline: Timeline instance

        Returns:
            ExperimentConfig instance suitable for GUI editing

        Conversion logic:
        1. Extract baseline_duration from first BaselinePhase (if exists)
        2. Flatten all trial-based blocks into single trials list
        3. Extract question configuration from RatingPhases
        4. Reconstruct trial parameters (video paths, fixation, etc.)
        """
        config = ExperimentConfig()

        # Track trial index across all blocks
        trial_index = 0

        for block in timeline.blocks:
            if block.block_type == 'simple':
                # Extract baseline duration
                for phase in block.procedure.phases:
                    if isinstance(phase, BaselinePhase):
                        config.baseline_duration = phase.duration
                        break

            elif block.block_type == 'trial_based':
                # Extract trials from this block
                if not block.trial_list or not block.procedure:
                    continue

                # Get fixation duration from procedure
                fixation_duration = 3.0  # default
                for phase in block.procedure.phases:
                    if isinstance(phase, FixationPhase):
                        fixation_duration = phase.duration
                        break

                # Get question from procedure
                question = None
                for phase in block.procedure.phases:
                    if isinstance(phase, RatingPhase):
                        # Calculate scale points
                        scale_points = phase.scale_max - phase.scale_min + 1

                        # Determine scale_type
                        from config.question import ScaleType
                        if scale_points == 7:
                            scale_type = ScaleType.LIKERT_7
                        elif scale_points == 5:
                            scale_type = ScaleType.LIKERT_5
                        elif scale_points == 2:
                            scale_type = ScaleType.BINARY
                        else:
                            scale_type = ScaleType.CUSTOM

                        # Generate appropriate key mappings
                        if scale_points == 7:
                            p1_keys = ['1', '2', '3', '4', '5', '6', '7']
                            p2_keys = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U']
                        elif scale_points == 5:
                            p1_keys = ['1', '2', '3', '4', '5']
                            p2_keys = ['Q', 'W', 'E', 'R', 'T']
                        elif scale_points == 2:
                            p1_keys = ['1', '2']
                            p2_keys = ['Q', 'W']
                        else:
                            # Custom scale - generate keys dynamically
                            p1_keys = [str(i) for i in range(1, scale_points + 1)]
                            p2_keys_map = ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P']
                            p2_keys = p2_keys_map[:scale_points]

                        question = Question(
                            text=phase.question,
                            scale_type=scale_type,
                            scale_points=scale_points,
                            p1_keys=p1_keys,
                            p2_keys=p2_keys,
                            timeout_seconds=phase.timeout
                        )
                        break

                # Set as global defaults if first question encountered
                if question and config.global_defaults.text == "How did the video make you feel?":
                    config.global_defaults = question

                # Extract trials
                for exec_trial in block.trial_list.trials:
                    config_trial = ConfigTrial(
                        index=trial_index,
                        video_path_1=exec_trial.data.get('VideoPath1', exec_trial.data.get('video1', '')),
                        video_path_2=exec_trial.data.get('VideoPath2', exec_trial.data.get('video2', '')),
                        fixation_duration=fixation_duration,
                        question_override=None  # TODO: Detect if different from global
                    )
                    config.trials.append(config_trial)
                    trial_index += 1

        return config

    @staticmethod
    def _create_baseline_block(duration: float) -> Block:
        """
        Create a baseline recording block.

        Args:
            duration: Baseline duration in seconds

        Returns:
            Block with BaselinePhase
        """
        block = Block(name="Baseline", block_type='simple')

        procedure = Procedure("Baseline Recording")

        # Create baseline phase
        baseline_phase = BaselinePhase(
            name="Baseline",
            duration=duration
        )

        # Add marker bindings for baseline start and end
        baseline_phase.marker_bindings = [
            MarkerBinding(event_type="phase_start", marker_template="8888"),
            MarkerBinding(event_type="phase_end", marker_template="9999")
        ]

        procedure.add_phase(baseline_phase)

        block.procedure = procedure
        return block

    @staticmethod
    def _group_trials_by_question(
        trials: List[ConfigTrial],
        global_defaults: Question
    ) -> Dict[tuple, List[ConfigTrial]]:
        """
        Group trials by their question configuration.

        Args:
            trials: List of Trial objects
            global_defaults: Default Question configuration

        Returns:
            Dictionary mapping question signature → list of trials
            Signature is tuple of question texts (allows multiple questions per trial)

        For now, simple implementation:
        - Trials with no override → group 1 (global defaults)
        - Trials with override → separate groups by override
        """
        groups = defaultdict(list)

        for trial in trials:
            # Create signature from question(s)
            if trial.question_override:
                signature = (trial.question_override.text,)
            else:
                signature = (global_defaults.text,)

            groups[signature].append(trial)

        return dict(groups)

    @staticmethod
    def _create_video_block(
        name: str,
        trials: List[ConfigTrial],
        questions: tuple,
        audio_device_p1: int,
        audio_device_p2: int
    ) -> Block:
        """
        Create a video trial block.

        Args:
            name: Block name
            trials: List of ConfigTrial objects in this block
            questions: Tuple of question texts (for future multi-question support)
            audio_device_p1: Audio device index for P1
            audio_device_p2: Audio device index for P2

        Returns:
            Block with Procedure and TrialList
        """
        block = Block(name=name, block_type='trial_based')

        # Create procedure template
        procedure = Procedure("Standard Trial")

        # Add fixation phase (use first trial's duration)
        fixation_duration = trials[0].fixation_duration if trials else 3.0
        procedure.add_phase(
            FixationPhase(
                name="Pre-stimulus Fixation",
                duration=fixation_duration
            )
        )

        # Add video phase (uses template variables)
        video_phase = VideoPhase(
            name="Video Playback",
            participant_1_video="{video1}",
            participant_2_video="{video2}"
        )

        # Add marker bindings for video events
        video_phase.marker_bindings = [
            MarkerBinding(event_type="video_start", marker_template="100#"),
            MarkerBinding(event_type="video_p1_end", marker_template="210#", participant=1),
            MarkerBinding(event_type="video_p2_end", marker_template="220#", participant=2)
        ]

        procedure.add_phase(video_phase)

        # Add rating phase(s)
        for question_text in questions:
            # Find the Question object from trials
            question = None
            for trial in trials:
                if trial.question_override and trial.question_override.text == question_text:
                    question = trial.question_override
                    break

            # Fallback to create from text if not found
            if not question:
                # Use default question configuration
                temp_config = ExperimentConfig()
                question = temp_config.global_defaults  # Use default

            rating_phase = RatingPhase(
                name=f"Rating: {question_text[:30]}...",
                question=question.text,
                scale_min=1,
                scale_max=question.scale_points,
                scale_labels=[
                    question.labels.get(1, "Low"),
                    question.labels.get(question.scale_points // 2 + 1, "Medium"),
                    question.labels.get(question.scale_points, "High")
                ],
                timeout=question.timeout_seconds
            )

            # Add marker bindings for rating responses
            rating_phase.marker_bindings = [
                MarkerBinding(event_type="p1_response", marker_template="300#0$", participant=1),
                MarkerBinding(event_type="p2_response", marker_template="500#0$", participant=2)
            ]

            procedure.add_phase(rating_phase)

        block.procedure = procedure

        # Create trial list
        block.trial_list = ExperimentConfigAdapter._create_trial_list_from_config_trials(trials)

        return block

    @staticmethod
    def _create_trial_list_from_config_trials(trials: List[ConfigTrial]) -> TrialList:
        """
        Create a TrialList from ConfigTrial objects.

        Since TrialList normally loads from CSV, we create a temporary
        CSV file and load from it.

        Args:
            trials: List of ConfigTrial objects

        Returns:
            TrialList instance
        """
        import pandas as pd

        # Create DataFrame from trials
        trial_data = []
        for trial in trials:
            trial_data.append({
                'trial_index': trial.index,
                'trial_id': trial.index,
                'VideoPath1': trial.video_path_1,
                'VideoPath2': trial.video_path_2,
                'video1': trial.video_path_1,  # Duplicate for template compatibility
                'video2': trial.video_path_2,
                'fixation_duration': trial.fixation_duration,
                'enabled': trial.enabled,
                'notes': trial.notes
            })

        df = pd.DataFrame(trial_data)

        # Write to temporary CSV
        temp_csv = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, newline='')
        csv_path = temp_csv.name
        temp_csv.close()

        df.to_csv(csv_path, index=False)

        # Create TrialList from CSV
        trial_list = TrialList(source=csv_path, source_type='csv')

        # Store reference to temp file for cleanup
        trial_list._temp_csv_path = csv_path

        return trial_list

    @staticmethod
    def validate_conversion(config: ExperimentConfig) -> List[str]:
        """
        Validate that ExperimentConfig can be converted to Timeline.

        Args:
            config: ExperimentConfig to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors = []

        # Validate config first
        is_valid, config_errors = config.validate()
        if not is_valid:
            errors.extend(config_errors)

        # Check for enabled trials
        if not config.get_enabled_trials():
            errors.append("No enabled trials to convert")

        # Check for valid video paths
        for trial in config.get_enabled_trials():
            if not trial.video_path_1 or not trial.video_path_2:
                errors.append(f"Trial {trial.index}: Missing video paths")

        return errors

    @staticmethod
    def cleanup_timeline(timeline: Timeline):
        """
        Clean up temporary resources created during conversion.

        Args:
            timeline: Timeline to clean up
        """
        for block in timeline.blocks:
            if hasattr(block, 'trial_list') and block.trial_list:
                # Remove temporary CSV file
                if hasattr(block.trial_list, '_temp_csv_path'):
                    try:
                        os.unlink(block.trial_list._temp_csv_path)
                    except:
                        pass
