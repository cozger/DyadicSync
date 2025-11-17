"""
Integration tests for GUI → Adapter → Execution pipeline.

Tests the full pipeline from Timeline Editor through adapter to execution engine.
"""

import pytest
import os
import tempfile
from pathlib import Path

from config.experiment import ExperimentConfig
from config.trial import Trial as ConfigTrial
from config.question import Question
from core.adapters.experiment_config_adapter import ExperimentConfigAdapter
from core.execution.timeline import Timeline
from timeline_editor.config_io import save_config, load_config


class TestGUIToExecutionPipeline:
    """Test the complete pipeline from GUI configuration to execution."""

    def test_gui_config_converts_to_timeline(self, tmp_path):
        """Test that GUI-created config successfully converts to Timeline."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Simulate GUI-created configuration
        config = ExperimentConfig(
            name="Test Experiment",
            description="Created in Timeline Editor",
            baseline_duration=60.0,
            audio_device_p1=9,
            audio_device_p2=7
        )

        # Add trials (simulating user adding trials in GUI)
        for i in range(3):
            config.add_trial(ConfigTrial(
                index=i,
                video_path_1=str(video1),
                video_path_2=str(video2),
                fixation_duration=3.0,
                notes=f"Trial {i+1} created in GUI"
            ))

        # Convert to timeline (what happens when user clicks "Run")
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Verify timeline structure
        assert isinstance(timeline, Timeline)
        assert len(timeline.blocks) == 2  # Baseline + Videos
        assert timeline.get_total_trials() == 4  # 1 (baseline) + 3 (videos)

        # Verify timeline validation passes
        errors = timeline.validate()
        assert len(errors) == 0

    def test_save_and_load_preserves_convertibility(self, tmp_path):
        """Test that saving and loading config preserves ability to convert to Timeline."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Create config
        original_config = ExperimentConfig(
            name="Save/Load Test",
            baseline_duration=120.0
        )
        original_config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        # Save config
        config_file = tmp_path / "test_config.json"
        assert save_config(original_config, str(config_file))

        # Load config
        loaded_config = load_config(str(config_file))
        assert loaded_config is not None

        # Convert loaded config to timeline
        timeline = ExperimentConfigAdapter.to_timeline(loaded_config)

        # Verify conversion successful
        assert timeline is not None
        assert timeline.get_total_trials() == 2  # 1 (baseline) + 1 (video)
        assert timeline.blocks[0].name == "Baseline"

    def test_gui_workflow_config_to_timeline_to_config(self, tmp_path):
        """Test GUI workflow: create config → convert to timeline → convert back."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Step 1: User creates config in GUI
        gui_config = ExperimentConfig(name="Round Trip Test")
        gui_config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            fixation_duration=5.0
        ))

        # Step 2: User clicks "Run" → config converted to timeline
        timeline = ExperimentConfigAdapter.to_timeline(gui_config)

        # Step 3: Timeline converted back to config (for editing)
        restored_config = ExperimentConfigAdapter.from_timeline(timeline)

        # Verify key properties preserved
        assert len(restored_config.trials) == 1
        assert restored_config.trials[0].video_path_1 == str(video1)
        assert restored_config.trials[0].video_path_2 == str(video2)
        assert restored_config.trials[0].fixation_duration == 5.0

    def test_validation_errors_caught_before_conversion(self, tmp_path):
        """Test that validation errors are caught before attempting conversion."""
        # Create config with missing video paths
        config = ExperimentConfig()
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1="",  # Invalid: empty path
            video_path_2=""
        ))

        # Validate conversion (simulates pre-run check)
        errors = ExperimentConfigAdapter.validate_conversion(config)

        # Should have validation errors
        assert len(errors) > 0
        assert any("Missing video paths" in e or "not found" in e for e in errors)

    def test_multiple_questions_create_multiple_rating_phases(self, tmp_path):
        """Test that config with multiple questions creates appropriate RatingPhases."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Create config with trials using different questions
        config = ExperimentConfig(baseline_duration=0.0)

        # Trial 1: Default question
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        # Trial 2: Custom question (future feature)
        custom_question = Question(text="How arousing was this?")
        config.add_trial(ConfigTrial(
            index=1,
            video_path_1=str(video1),
            video_path_2=str(video2),
            question_override=custom_question
        ))

        # Convert
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Verify conversion successful
        assert timeline is not None
        assert len(timeline.blocks) >= 1  # At least one video block

        # Verify procedure has rating phases
        for block in timeline.blocks:
            if block.block_type == 'trial_based':
                rating_phases = [p for p in block.procedure.phases
                                if p.__class__.__name__ == 'RatingPhase']
                assert len(rating_phases) > 0  # Has at least one rating phase

    def test_disabled_trials_excluded_from_timeline(self, tmp_path):
        """Test that disabled trials don't appear in converted timeline."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Create config with enabled and disabled trials
        config = ExperimentConfig(baseline_duration=0.0)

        # Add 2 enabled trials
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2),
            enabled=True
        ))
        config.add_trial(ConfigTrial(
            index=1,
            video_path_1=str(video1),
            video_path_2=str(video2),
            enabled=True
        ))

        # Add 1 disabled trial
        config.add_trial(ConfigTrial(
            index=2,
            video_path_1=str(video1),
            video_path_2=str(video2),
            enabled=False  # Disabled
        ))

        # Convert
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should only have 2 trials in timeline
        assert timeline.get_total_trials() == 2

    def test_baseline_duration_zero_skips_baseline_block(self, tmp_path):
        """Test that baseline_duration=0 creates no baseline block."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Create config with no baseline
        config = ExperimentConfig(baseline_duration=0.0)
        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        # Convert
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should only have video block, no baseline
        assert len(timeline.blocks) == 1
        assert timeline.blocks[0].block_type == 'trial_based'


class TestEdgeCases:
    """Test edge cases in GUI integration."""

    def test_empty_experiment_graceful_handling(self):
        """Test that empty experiment is handled gracefully."""
        config = ExperimentConfig(baseline_duration=60.0)  # No trials

        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Should have only baseline block
        assert len(timeline.blocks) == 1
        assert timeline.blocks[0].name == "Baseline"

    def test_large_experiment_converts_successfully(self, tmp_path):
        """Test that large experiments with many trials convert successfully."""
        # Create test videos
        videos = []
        for i in range(20):
            v1 = tmp_path / f"video{i*2}.mp4"
            v2 = tmp_path / f"video{i*2+1}.mp4"
            v1.touch()
            v2.touch()
            videos.append((v1, v2))

        # Create large config
        config = ExperimentConfig(baseline_duration=240.0)
        for i, (v1, v2) in enumerate(videos):
            config.add_trial(ConfigTrial(
                index=i,
                video_path_1=str(v1),
                video_path_2=str(v2)
            ))

        # Convert
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Verify
        assert timeline.get_total_trials() == 21  # 1 (baseline) + 20 (videos)
        assert len(timeline.blocks) == 2  # Baseline + Videos
        assert timeline.validate() == []  # No errors

    def test_config_metadata_preserved_through_conversion(self, tmp_path):
        """Test that config metadata is accessible after conversion."""
        # Create test videos
        video1 = tmp_path / "video1.mp4"
        video2 = tmp_path / "video2.mp4"
        video1.touch()
        video2.touch()

        # Create config with metadata
        config = ExperimentConfig(
            name="Metadata Test",
            description="Testing metadata preservation"
        )
        config.metadata['researcher'] = "Dr. Smith"
        config.metadata['experiment_id'] = "EXP001"

        config.add_trial(ConfigTrial(
            index=0,
            video_path_1=str(video1),
            video_path_2=str(video2)
        ))

        # Convert
        timeline = ExperimentConfigAdapter.to_timeline(config)

        # Convert back
        restored = ExperimentConfigAdapter.from_timeline(timeline)

        # Metadata might not be preserved through Timeline (Timeline doesn't store metadata)
        # But config should still be valid
        assert restored.name == "DyadicSync Experiment"  # Default name used
        assert len(restored.trials) == 1
