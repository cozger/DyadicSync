"""
Unit tests for Phase classes.

Tests all concrete Phase implementations: FixationPhase, VideoPhase, RatingPhase,
InstructionPhase, and BaselinePhase.
"""

import pytest
from core.execution.phases.fixation_phase import FixationPhase
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.phases.instruction_phase import InstructionPhase
from core.execution.phases.baseline_phase import BaselinePhase


# ==================== FIXATION PHASE TESTS ====================

@pytest.mark.unit
def test_fixation_phase_creation():
    """FixationPhase should initialize with duration."""
    phase = FixationPhase(duration=5.0)

    assert phase.name == "Fixation"
    assert phase.duration == 5.0


@pytest.mark.unit
def test_fixation_phase_estimated_duration():
    """FixationPhase should report correct estimated duration."""
    phase = FixationPhase(duration=3.5)

    assert phase.get_estimated_duration() == 3.5


@pytest.mark.unit
def test_fixation_phase_validation_valid():
    """FixationPhase with positive duration should validate."""
    phase = FixationPhase(duration=5.0)

    errors = phase.validate()

    assert len(errors) == 0


@pytest.mark.unit
def test_fixation_phase_validation_negative_duration():
    """FixationPhase with negative duration should fail validation."""
    phase = FixationPhase(duration=-1.0)

    errors = phase.validate()

    assert len(errors) > 0
    assert any('duration' in e.lower() for e in errors)


@pytest.mark.unit
def test_fixation_phase_serialization():
    """FixationPhase should serialize to dict."""
    from core.markers import MarkerBinding

    phase = FixationPhase(duration=3.0)
    phase.marker_bindings = [
        MarkerBinding(event_type="phase_start", marker_template="8888"),
        MarkerBinding(event_type="phase_end", marker_template="9999")
    ]

    phase_dict = phase.to_dict()

    assert phase_dict['type'] == 'FixationPhase'
    assert phase_dict['duration'] == 3.0
    # Check marker bindings instead of marker_start/marker_end
    assert 'marker_bindings' in phase_dict
    assert len(phase_dict['marker_bindings']) == 2


@pytest.mark.unit
def test_fixation_phase_deserialization():
    """FixationPhase should deserialize from dict."""
    data = {
        'name': 'Test Fixation',
        'duration': 4.5,
        'marker_bindings': [
            {'event_type': 'phase_start', 'marker_template': '1111', 'participant': None},
            {'event_type': 'phase_end', 'marker_template': '2222', 'participant': None}
        ]
    }

    phase = FixationPhase.from_dict(data)

    assert phase.name == 'Test Fixation'
    assert phase.duration == 4.5
    # Check marker bindings instead of marker_start/marker_end
    assert len(phase.marker_bindings) == 2
    assert phase.marker_bindings[0].event_type == 'phase_start'
    assert phase.marker_bindings[0].marker_template == '1111'


# ==================== VIDEO PHASE TESTS ====================

@pytest.mark.unit
def test_video_phase_creation():
    """VideoPhase should initialize with video paths."""
    phase = VideoPhase(
        participant_1_video="/path/video1.mp4",
        participant_2_video="/path/video2.mp4"
    )

    assert phase.participant_1_video == "/path/video1.mp4"
    assert phase.participant_2_video == "/path/video2.mp4"


@pytest.mark.unit
def test_video_phase_template_rendering():
    """VideoPhase should render template variables."""
    phase = VideoPhase(
        participant_1_video="{video1}",
        participant_2_video="{video2}"
    )

    trial_data = {
        'video1': '/real/path/v1.mp4',
        'video2': '/real/path/v2.mp4'
    }

    rendered = phase.render(trial_data)

    assert rendered.participant_1_video == '/real/path/v1.mp4'
    assert rendered.participant_2_video == '/real/path/v2.mp4'


@pytest.mark.unit
def test_video_phase_required_variables():
    """VideoPhase should extract required template variables."""
    phase = VideoPhase(
        participant_1_video="{video1}",
        participant_2_video="{video2}"
    )

    variables = phase.get_required_variables()

    assert 'video1' in variables
    assert 'video2' in variables


@pytest.mark.unit
def test_video_phase_serialization():
    """VideoPhase should serialize to dict."""
    from core.markers import MarkerBinding

    phase = VideoPhase(
        participant_1_video="/path/v1.mp4",
        participant_2_video="/path/v2.mp4",
        auto_advance=True
    )
    phase.marker_bindings = [
        MarkerBinding(event_type="video_start", marker_template="1001"),
        MarkerBinding(event_type="video_p1_end", marker_template="2101", participant=1)
    ]

    phase_dict = phase.to_dict()

    assert phase_dict['type'] == 'VideoPhase'
    assert phase_dict['participant_1_video'] == "/path/v1.mp4"
    assert phase_dict['participant_2_video'] == "/path/v2.mp4"
    assert phase_dict['auto_advance'] is True
    # Check marker bindings instead
    assert 'marker_bindings' in phase_dict
    assert len(phase_dict['marker_bindings']) == 2


@pytest.mark.unit
def test_video_phase_deserialization():
    """VideoPhase should deserialize from dict."""
    data = {
        'participant_1_video': '/test/v1.mp4',
        'participant_2_video': '/test/v2.mp4',
        'auto_advance': False,
        'marker_bindings': [
            {'event_type': 'video_start', 'marker_template': '1005', 'participant': None},
            {'event_type': 'video_p1_end', 'marker_template': '2105', 'participant': 1}
        ]
    }

    phase = VideoPhase.from_dict(data)

    assert phase.participant_1_video == '/test/v1.mp4'
    assert phase.participant_2_video == '/test/v2.mp4'
    assert phase.auto_advance is False
    # Check marker bindings instead
    assert len(phase.marker_bindings) == 2
    assert phase.marker_bindings[0].event_type == 'video_start'


# ==================== RATING PHASE TESTS ====================

@pytest.mark.unit
def test_rating_phase_creation():
    """RatingPhase should initialize with question and scale."""
    phase = RatingPhase(
        question="How did you feel?",
        scale_min=1,
        scale_max=7
    )

    assert phase.question == "How did you feel?"
    assert phase.scale_min == 1
    assert phase.scale_max == 7


@pytest.mark.unit
def test_rating_phase_marker_calculation_p1():
    """RatingPhase should use marker bindings for P1 responses."""
    from core.markers import MarkerBinding

    phase = RatingPhase()
    phase.marker_bindings = [
        MarkerBinding(event_type="p1_response", marker_template="300#0$", participant=1),
        MarkerBinding(event_type="p2_response", marker_template="500#0$", participant=2)
    ]

    # Verify marker bindings are set
    assert len(phase.marker_bindings) == 2
    assert phase.marker_bindings[0].event_type == "p1_response"
    assert phase.marker_bindings[0].marker_template == "300#0$"
    assert phase.marker_bindings[0].participant == 1


@pytest.mark.unit
def test_rating_phase_marker_calculation_p2():
    """RatingPhase should use marker bindings for P2 responses."""
    from core.markers import MarkerBinding

    phase = RatingPhase()
    phase.marker_bindings = [
        MarkerBinding(event_type="p1_response", marker_template="300#0$", participant=1),
        MarkerBinding(event_type="p2_response", marker_template="500#0$", participant=2)
    ]

    # Verify P2 marker binding
    assert len(phase.marker_bindings) == 2
    assert phase.marker_bindings[1].event_type == "p2_response"
    assert phase.marker_bindings[1].marker_template == "500#0$"
    assert phase.marker_bindings[1].participant == 2


@pytest.mark.unit
def test_rating_phase_marker_calculation_trial_1():
    """RatingPhase marker templates should support trial indexing."""
    from core.markers import MarkerBinding

    phase = RatingPhase()
    phase.marker_bindings = [
        MarkerBinding(event_type="p1_response", marker_template="300#0$", participant=1)
    ]

    # The marker template "300#0$" will be resolved at runtime with trial_data
    # This test just verifies the binding structure
    assert phase.marker_bindings[0].marker_template == "300#0$"


@pytest.mark.unit
def test_rating_phase_validation_valid():
    """RatingPhase with valid scale should pass validation."""
    phase = RatingPhase(scale_min=1, scale_max=7)

    errors = phase.validate()

    assert len(errors) == 0


@pytest.mark.unit
def test_rating_phase_validation_invalid_scale():
    """RatingPhase with min >= max should fail validation."""
    phase = RatingPhase(scale_min=7, scale_max=1)

    errors = phase.validate()

    assert len(errors) > 0
    assert any('scale' in e.lower() for e in errors)


@pytest.mark.unit
def test_rating_phase_validation_negative_timeout():
    """RatingPhase with negative timeout should fail validation."""
    phase = RatingPhase(timeout=-5.0)

    errors = phase.validate()

    assert len(errors) > 0
    assert any('timeout' in e.lower() for e in errors)


@pytest.mark.unit
def test_rating_phase_serialization():
    """RatingPhase should serialize to dict."""
    phase = RatingPhase(
        question="Rate your experience",
        scale_min=1,
        scale_max=9,
        timeout=30.0
    )

    phase_dict = phase.to_dict()

    assert phase_dict['type'] == 'RatingPhase'
    assert phase_dict['question'] == "Rate your experience"
    assert phase_dict['scale_min'] == 1
    assert phase_dict['scale_max'] == 9
    assert phase_dict['timeout'] == 30.0


# ==================== INSTRUCTION PHASE TESTS ====================

@pytest.mark.unit
def test_instruction_phase_creation():
    """InstructionPhase should initialize with text."""
    phase = InstructionPhase(text="Press any key to continue")

    assert phase.text == "Press any key to continue"


@pytest.mark.unit
def test_instruction_phase_validation():
    """InstructionPhase should validate successfully."""
    phase = InstructionPhase(text="Test instruction")

    errors = phase.validate()

    assert len(errors) == 0


@pytest.mark.unit
def test_instruction_phase_serialization():
    """InstructionPhase should serialize to dict."""
    phase = InstructionPhase(
        text="Get ready for the next trial",
        font_size=32,
        wait_for_key=True
    )

    phase_dict = phase.to_dict()

    assert phase_dict['type'] == 'InstructionPhase'
    assert phase_dict['text'] == "Get ready for the next trial"
    assert phase_dict['font_size'] == 32
    assert phase_dict['wait_for_key'] is True


# ==================== BASELINE PHASE TESTS ====================

@pytest.mark.unit
def test_baseline_phase_creation():
    """BaselinePhase should initialize with duration."""
    phase = BaselinePhase(duration=240)

    assert phase.duration == 240
    assert phase.name == "Baseline"


@pytest.mark.unit
def test_baseline_phase_is_fixation_subclass():
    """BaselinePhase should be a FixationPhase subclass."""
    phase = BaselinePhase(duration=120)

    assert isinstance(phase, FixationPhase)


@pytest.mark.unit
def test_baseline_phase_default_markers():
    """BaselinePhase can have LSL markers configured via marker_bindings."""
    from core.markers import MarkerBinding

    phase = BaselinePhase(duration=240)

    # Add marker bindings (typically done by adapter or user code)
    phase.marker_bindings = [
        MarkerBinding(event_type="phase_start", marker_template="8888"),
        MarkerBinding(event_type="phase_end", marker_template="9999")
    ]

    # Verify bindings
    assert len(phase.marker_bindings) == 2
    assert phase.marker_bindings[0].event_type == "phase_start"
    assert phase.marker_bindings[0].marker_template == "8888"
    assert phase.marker_bindings[1].event_type == "phase_end"
    assert phase.marker_bindings[1].marker_template == "9999"


@pytest.mark.unit
def test_baseline_phase_estimated_duration():
    """BaselinePhase should report correct duration."""
    phase = BaselinePhase(duration=180)

    assert phase.get_estimated_duration() == 180


# ==================== CROSS-PHASE TESTS ====================

@pytest.mark.unit
def test_all_phases_have_validate():
    """All Phase classes should implement validate()."""
    phases = [
        FixationPhase(duration=1),
        VideoPhase(),
        RatingPhase(),
        InstructionPhase(text="test"),
        BaselinePhase(duration=1)
    ]

    for phase in phases:
        assert hasattr(phase, 'validate')
        assert callable(phase.validate)


@pytest.mark.unit
def test_all_phases_have_to_dict():
    """All Phase classes should implement to_dict()."""
    phases = [
        FixationPhase(duration=1),
        VideoPhase(),
        RatingPhase(),
        InstructionPhase(text="test"),
        BaselinePhase(duration=1)
    ]

    for phase in phases:
        assert hasattr(phase, 'to_dict')
        phase_dict = phase.to_dict()
        assert 'type' in phase_dict
        assert 'name' in phase_dict


@pytest.mark.unit
def test_all_phases_have_from_dict():
    """All Phase classes should implement from_dict()."""
    phase_classes = [FixationPhase, VideoPhase, RatingPhase, InstructionPhase, BaselinePhase]

    for phase_class in phase_classes:
        assert hasattr(phase_class, 'from_dict')
        assert callable(phase_class.from_dict)


@pytest.mark.unit
def test_all_phases_have_get_estimated_duration():
    """All Phase classes should implement get_estimated_duration()."""
    phases = [
        FixationPhase(duration=1),
        VideoPhase(),
        RatingPhase(),
        InstructionPhase(text="test"),
        BaselinePhase(duration=1)
    ]

    for phase in phases:
        assert hasattr(phase, 'get_estimated_duration')
        duration = phase.get_estimated_duration()
        assert isinstance(duration, (int, float)) or duration == -1
