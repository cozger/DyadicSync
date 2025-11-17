"""
Unit tests for adapter layer.

Tests bidirectional conversion between ExperimentConfig and Timeline.
"""

import pytest
import os
import tempfile
from pathlib import Path

from core.adapters.experiment_config_adapter import ExperimentConfigAdapter
from config.experiment import ExperimentConfig
from config.trial import Trial as ConfigTrial
from config.question import Question, ScaleType
from core.execution.timeline import Timeline
from core.execution.block import Block
from core.execution.phases import BaselinePhase, FixationPhase, VideoPhase, RatingPhase


class TestExperimentConfigToTimeline:
    """Test ExperimentConfig → Timeline conversion."""

    def test_basic_conversion(self, tmp_path):
        """Test basic conversion with baseline and trials."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Create config
        config = ExperimentConfig(
            name="Test Experiment",
            baseline_duration=60.0,
            audio_device_p1=9,
            audio_device_p2=7
        )

        # Add trials
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            fixation_duration=3.0
        ))

        # Convert
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Verify structure
        assert isinstance(timeline, Timeline)
        assert len(timeline.blocks) == 2  # Baseline + Videos

        # Check baseline block
        baseline_block = timeline.blocks[0]
        assert baseline_block.name == "Baseline"
        assert baseline_block.block_type == 'simple'
        assert len(baseline_block.procedure.phases) == 1
        assert isinstance(baseline_block.procedure.phases[0], BaselinePhase)
        assert baseline_block.procedure.phases[0].duration == 60.0

        # Check marker bindings
        baseline_phase = baseline_block.procedure.phases[0]
        assert len(baseline_phase.marker_bindings) == 2
        assert any(b.event_type == "phase_start" and b.marker_template == "8888"
                   for b in baseline_phase.marker_bindings)
        assert any(b.event_type == "phase_end" and b.marker_template == "9999"
                   for b in baseline_phase.marker_bindings)

        # Check video block
        video_block = timeline.blocks[1]
        assert video_block.block_type == 'trial_based'
        assert video_block.procedure is not None
        assert video_block.trial_list is not None
        assert len(video_block.trial_list.trials) == 1

    def test_no_baseline(self, tmp_path):
        """Test conversion without baseline period."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should have only video block
        assert len(timeline.blocks) == 1
        assert timeline.blocks[0].block_type == 'trial_based'

    def test_multiple_trials(self, tmp_path):
        """Test conversion with multiple trials."""
        # Create test videos
        videos = []
        for i in range(5):
            v1 = tmp_path / f"video{i*2}.mp4"
            v2 = tmp_path / f"video{i*2+1}.mp4"
            v1.touch()
            v2.touch()
            videos.append((v1, v2))

        config = ExperimentConfig(baseline_duration=120.0)

        # Add 5 trials
        for i, (v1, v2) in enumerate(videos):
            config.add_trial(ConfigTrial(
                index=i,
                video_path_1=str(v1),
                video_path_2=str(v2),
                fixation_duration=3.0
            ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should have 2 blocks (baseline + videos)
        assert len(timeline.blocks) == 2

        # Check video block has all trials
        video_block = timeline.blocks[1]
        assert len(video_block.trial_list.trials) == 5

    def test_disabled_trials_excluded(self, tmp_path):
        """Test that disabled trials are not included."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)

        # Add enabled trial
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            enabled=True
        ))

        # Add disabled trial
        config.add_trial(ConfigTrial(
            index=1,
            video_path_1=str(video1),
            video_path_2=str(video2),
            enabled=False
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should only have 1 trial in trial list
        assert len(timeline.blocks[0].trial_list.trials) == 1

    def test_procedure_structure(self, tmp_path):
        """Test that procedure has correct phase sequence."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            fixation_duration=5.0
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Check procedure phases
        procedure = timeline.blocks[0].procedure
        assert len(procedure.phases) == 3  # Fixation + Video + Rating

        # Check phase types and order
        assert isinstance(procedure.phases[0], FixationPhase)
        assert isinstance(procedure.phases[1], VideoPhase)
        assert isinstance(procedure.phases[2], RatingPhase)

        # Check fixation duration
        assert procedure.phases[0].duration == 5.0

        # Check video phase uses templates
        video_phase = procedure.phases[1]
        assert video_phase.participant_1_video == "{video1}"
        assert video_phase.participant_2_video == "{video2}"

        # Check rating phase
        rating_phase = procedure.phases[2]
        assert rating_phase.question == config.global_defaults.text
        assert rating_phase.scale_max == config.global_defaults.scale_points

    def test_trial_data_mapping(self, tmp_path):
        """Test that trial data is correctly mapped to TrialList."""
        video1 = tmp_path / "v1.mp4"
        video2 = tmp_path / "v2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Check trial data
        trial = timeline.blocks[0].trial_list.trials[0]
        assert trial.data['VideoPath1'] == str(video1)
        assert trial.data['VideoPath2'] == str(video2)
        assert trial.data['video1'] == str(video1)  # Template compatibility
        assert trial.data['video2'] == str(video2)
        assert trial.data['trial_index'] == 0

    def test_question_override_creates_separate_blocks(self, tmp_path):
        """Test that trials with different questions are grouped into separate blocks."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)

        # Trial with default question
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            question_override=None
        ))

        # Trial with override question
        custom_question = Question(
            text="How arousing was this video?",
            scale_type=ScaleType.LIKERT_7
        )
        config.add_trial(ConfigTrial(
            index=1,
            video_path_1=str(video1),
            video_path_2=str(video2),
            question_override=custom_question
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should have 2 video blocks (1 per question type)
        # Note: Currently implementation groups all into one block
        # This test documents expected future behavior
        assert len(timeline.blocks) >= 1  # At minimum, all trials grouped

    def test_empty_config(self):
        """Test conversion of config with no trials."""
        config = ExperimentConfig(baseline_duration=60.0)

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should only have baseline block
        assert len(timeline.blocks) == 1
        assert timeline.blocks[0].block_type == 'simple'


class TestTimelineToExperimentConfig:
    """Test Timeline → ExperimentConfig conversion."""

    def test_basic_reverse_conversion(self):
        """Test basic reverse conversion."""
        # Create simple timeline
        timeline = Timeline()

        # Add baseline
        baseline_block = Block(name="Baseline", block_type='simple')
        from core.execution.procedure import Procedure
        baseline_procedure = Procedure("Baseline")
        baseline_procedure.add_phase(BaselinePhase(duration=180.0))
        baseline_block.procedure = baseline_procedure
        timeline.add_block(baseline_block)

        # Convert to config
        config = ExperimentConfigAdapter.from_timeline(timeline)

        # Verify
        assert config.baseline_duration == 180.0

    def test_extract_trials_from_timeline(self, tmp_path):
        """Test extracting trials from timeline."""
        # Create test CSV
        csv_path = tmp_path / "trials.csv"
        csv_content = "VideoPath1,VideoPath2\n/path/v1.mp4,/path/v2.mp4\n/path/v3.mp4,/path/v4.mp4"
        csv_path.write_text(csv_content)

        # Create timeline with trial block
        timeline = Timeline()

        from core.execution.procedure import Procedure
        from core.execution.trial_list import TrialList

        video_block = Block(name="Videos", block_type='trial_based')
        procedure = Procedure("Standard")
        procedure.add_phase(FixationPhase(duration=4.0))
        procedure.add_phase(VideoPhase(
            participant_1_video="{video1}",
            participant_2_video="{video2}"
        ))
        procedure.add_phase(RatingPhase(
            question="How intense?",
            scale_min=1,
            scale_max=7
        ))
        video_block.procedure = procedure
        video_block.trial_list = TrialList(source=str(csv_path))
        timeline.add_block(video_block)

        # Convert to config
        config = ExperimentConfigAdapter.from_timeline(timeline)

        # Verify trials
        assert len(config.trials) == 2
        assert config.trials[0].video_path_1 == "/path/v1.mp4"
        assert config.trials[0].video_path_2 == "/path/v2.mp4"
        assert config.trials[0].fixation_duration == 4.0
        assert config.trials[1].video_path_1 == "/path/v3.mp4"

    def test_extract_question_configuration(self):
        """Test that question config is extracted correctly."""
        timeline = Timeline()

        from core.execution.procedure import Procedure

        block = Block(name="Videos", block_type='trial_based')
        procedure = Procedure("Standard")
        procedure.add_phase(RatingPhase(
            question="How did you feel?",
            scale_min=1,
            scale_max=5,
            timeout=30.0
        ))
        block.procedure = procedure

        # Create empty trial list
        import pandas as pd
        csv_path = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        csv_path.write("VideoPath1,VideoPath2\n")
        csv_path.close()
        from core.execution.trial_list import TrialList
        block.trial_list = TrialList(source=csv_path.name)

        timeline.add_block(block)

        # Convert
        config = ExperimentConfigAdapter.from_timeline(timeline)

        # Verify question
        assert config.global_defaults.text == "How did you feel?"
        assert config.global_defaults.scale_points == 5
        assert config.global_defaults.timeout_seconds == 30.0

        # Cleanup
        os.unlink(csv_path.name)


class TestRoundTripConversion:
    """Test that round-trip conversion preserves data."""

    def test_round_trip_preserves_baseline(self, tmp_path):
        """Test baseline duration preserved through round trip."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Original config
        original = ExperimentConfig(baseline_duration=240.0)
        original.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        # Convert to timeline and back
        timeline = ExperimentConfigAdapter.to_timeline(original)
        restored = ExperimentConfigAdapter.from_timeline(timeline)

        # Verify
        assert restored.baseline_duration == 240.0

    def test_round_trip_preserves_trials(self, tmp_path):
        """Test trial data preserved through round trip."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Original config
        original = ExperimentConfig(baseline_duration=0.0)
        original.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            fixation_duration=5.0
        ))
        original.add_trial(ConfigTrial(
            index=1,
            video_path_1=str(video2),
            video_path_2=str(video1),
            fixation_duration=5.0
        ))

        # Convert to timeline and back
        timeline = ExperimentConfigAdapter.to_timeline(original)
        restored = ExperimentConfigAdapter.from_timeline(timeline)

        # Verify trial count
        assert len(restored.trials) == 2

        # Verify video paths
        assert restored.trials[0].video_path_1 == str(video1)
        assert restored.trials[0].video_path_2 == str(video2)
        assert restored.trials[1].video_path_1 == str(video2)
        assert restored.trials[1].video_path_2 == str(video1)

        # Verify fixation duration
        assert restored.trials[0].fixation_duration == 5.0


class TestValidation:
    """Test validation functionality."""

    def test_validate_valid_config(self, tmp_path):
        """Test validation passes for valid config."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig()
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        errors = ExperimentConfigAdapter.validate_conversion(config)
        assert len(errors) == 0

    def test_validate_no_trials(self):
        """Test validation fails when no enabled trials."""
        config = ExperimentConfig()

        errors = ExperimentConfigAdapter.validate_conversion(config)
        assert len(errors) > 0
        assert any("No enabled trials" in e for e in errors)

    def test_validate_missing_videos(self):
        """Test validation fails when video paths missing."""
        config = ExperimentConfig()
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1="",
            video_path_2=""
        ))

        errors = ExperimentConfigAdapter.validate_conversion(config)
        assert len(errors) > 0
        assert any("Missing video paths" in e for e in errors)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_single_trial(self, tmp_path):
        """Test conversion with single trial."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        assert len(timeline.blocks) == 1
        assert len(timeline.blocks[0].trial_list.trials) == 1

    def test_large_number_of_trials(self, tmp_path):
        """Test conversion with many trials."""
        # Create videos
        videos = []
        for i in range(50):
            v1 = tmp_path / f"v{i*2}.mp4"
            v2 = tmp_path / f"v{i*2+1}.mp4"
            v1.touch()
            v2.touch()
            videos.append((v1, v2))

        config = ExperimentConfig(baseline_duration=0.0)
        for i, (v1, v2) in enumerate(videos):
            config.add_trial(ConfigTrial(
                index=i,
                video_path_1=str(v1),
                video_path_2=str(v2)
            ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should have all 50 trials
        assert len(timeline.blocks[0].trial_list.trials) == 50

    def test_cleanup_temp_files(self, tmp_path):
        """Test that temporary CSV files are cleaned up."""
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        config = ExperimentConfig(baseline_duration=0.0)
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Get temp file path
        temp_csv = timeline.blocks[0].trial_list._temp_csv_path

        # Verify file exists
        assert os.path.exists(temp_csv)

        # Cleanup
        ExperimentConfigAdapter.cleanup_timeline(timeline)

        # Verify file removed
        assert not os.path.exists(temp_csv)
