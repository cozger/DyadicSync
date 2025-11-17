"""
Example: LSL Marker System Usage

Demonstrates how to use the new event-based marker system with:
- Marker catalog
- Template-based markers (trial-indexed, participant-specific)
- Multi-marker events
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.markers import MarkerCatalog, MarkerBinding, resolve_marker_template
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.phases.fixation_phase import FixationPhase


def example_1_marker_catalog():
    """Example 1: Working with the Marker Catalog"""
    print("=" * 60)
    print("Example 1: Marker Catalog")
    print("=" * 60)

    # Get the global catalog instance
    catalog = MarkerCatalog()

    # Display all defined markers
    print("\n[*] All Markers in Catalog:")
    for definition in catalog.get_all_definitions():
        template_info = f" (template: {definition.template_pattern})" if definition.template_pattern else ""
        print(f"  {definition.code}: {definition.name}{template_info}")
        print(f"     -> {definition.description}")

    # Look up a specific marker
    baseline_start = catalog.get_definition(8888)
    print(f"\n[+] Lookup 8888: {baseline_start.name}")

    # Get marker name (for logging)
    print(f"[+] Lookup 1000: {catalog.get_name(1000)}")
    print(f"[+] Lookup 99999 (unknown): {catalog.get_name(99999)}")


def example_2_template_resolution():
    """Example 2: Resolving Marker Templates"""
    print("\n" + "=" * 60)
    print("Example 2: Template Resolution")
    print("=" * 60)

    # Simple trial-indexed markers
    print("\n[*] Trial-Indexed Markers:")
    for trial in [1, 2, 5, 10]:
        marker = resolve_marker_template("100#", trial_index=trial)
        print(f"  Trial {trial}: 100# -> {marker}")

    # Participant-specific markers
    print("\n[*] Participant-Specific Markers:")
    for trial in [1, 3, 7]:
        p1_marker = resolve_marker_template("210#", trial_index=trial)
        p2_marker = resolve_marker_template("220#", trial_index=trial)
        print(f"  Trial {trial}: P1=210# -> {p1_marker}, P2=220# -> {p2_marker}")

    # Complex rating markers (trial + response)
    print("\n[*] Rating Markers (trial + response):")
    for trial in [1, 5]:
        for rating in [1, 4, 7]:
            p1_marker = resolve_marker_template("300#0$", trial_index=trial, response_value=rating)
            p2_marker = resolve_marker_template("500#0$", trial_index=trial, response_value=rating)
            print(f"  Trial {trial}, Rating {rating}: P1={p1_marker}, P2={p2_marker}")


def example_3_phase_configuration():
    """Example 3: Configuring Phases with Marker Bindings"""
    print("\n" + "=" * 60)
    print("Example 3: Phase Configuration")
    print("=" * 60)

    # Example 3a: VideoPhase with multiple marker events
    print("\n[*] VideoPhase with Multi-Marker Events:")
    video_phase = VideoPhase(
        name="Emotional Video",
        participant_1_video="videos/happy_p1.mp4",
        participant_2_video="videos/happy_p2.mp4"
    )

    # Configure markers for different events
    video_phase.marker_bindings = [
        # Trial start (both participants)
        MarkerBinding(event_type="video_start", marker_template="100#", participant=None),

        # Participant-specific end markers (critical for different-length videos!)
        MarkerBinding(event_type="video_p1_end", marker_template="210#", participant=1),
        MarkerBinding(event_type="video_p2_end", marker_template="220#", participant=2),

        # Optional: When both complete
        # MarkerBinding(event_type="video_both_complete", marker_template="...", participant=None),
    ]

    print("  Events configured:")
    for binding in video_phase.marker_bindings:
        print(f"    - {binding.event_type}: {binding.marker_template}")

    print("\n  Example resolution for Trial 3:")
    print(f"    video_start -> {resolve_marker_template('100#', trial_index=3)}")
    print(f"    video_p1_end -> {resolve_marker_template('210#', trial_index=3)}")
    print(f"    video_p2_end -> {resolve_marker_template('220#', trial_index=3)}")

    # Example 3b: RatingPhase with response markers
    print("\n[*] RatingPhase with Response Markers:")
    rating_phase = RatingPhase(
        name="Emotional Rating",
        question="How did the video make you feel?"
    )

    # Configure rating markers
    rating_phase.marker_bindings = [
        MarkerBinding(event_type="p1_response", marker_template="300#0$", participant=1),
        MarkerBinding(event_type="p2_response", marker_template="500#0$", participant=2),
    ]

    print("  Events configured:")
    for binding in rating_phase.marker_bindings:
        print(f"    - {binding.event_type}: {binding.marker_template}")

    print("\n  Example resolution for Trial 2, Rating 7:")
    print(f"    P1 response -> {resolve_marker_template('300#0$', trial_index=2, response_value=7)}")
    print(f"    P2 response -> {resolve_marker_template('500#0$', trial_index=2, response_value=7)}")

    # Example 3c: FixationPhase with simple start/end markers
    print("\n[*] FixationPhase with Start/End Markers:")
    fixation_phase = FixationPhase(
        name="Pre-Video Fixation",
        duration=3.0
    )

    # Configure simple phase markers (no templates needed)
    fixation_phase.marker_bindings = [
        MarkerBinding(event_type="phase_start", marker_template="8888", participant=None),
        MarkerBinding(event_type="phase_end", marker_template="9999", participant=None),
    ]

    print("  Events configured:")
    for binding in fixation_phase.marker_bindings:
        print(f"    - {binding.event_type}: {binding.marker_template}")


def example_4_serialization():
    """Example 4: Saving and Loading Phase with Markers"""
    print("\n" + "=" * 60)
    print("Example 4: Serialization")
    print("=" * 60)

    # Create a VideoPhase with marker bindings
    original_phase = VideoPhase(
        name="Test Video",
        participant_1_video="test1.mp4",
        participant_2_video="test2.mp4"
    )
    original_phase.marker_bindings = [
        MarkerBinding(event_type="video_start", marker_template="100#"),
        MarkerBinding(event_type="video_p1_end", marker_template="210#", participant=1),
        MarkerBinding(event_type="video_p2_end", marker_template="220#", participant=2),
    ]

    # Serialize to dictionary
    print("\n[+] Serializing phase to dictionary:")
    phase_dict = original_phase.to_dict()
    print(f"  Type: {phase_dict['type']}")
    print(f"  Name: {phase_dict['name']}")
    print(f"  Marker Bindings: {len(phase_dict['marker_bindings'])} bindings")
    for binding in phase_dict['marker_bindings']:
        print(f"    - {binding['event_type']}: {binding['marker_template']}")

    # Deserialize back to Phase object
    print("\n[+] Deserializing back to Phase object:")
    loaded_phase = VideoPhase.from_dict(phase_dict)
    print(f"  Loaded: {loaded_phase.name}")
    print(f"  Marker Bindings: {len(loaded_phase.marker_bindings)} bindings")
    for binding in loaded_phase.marker_bindings:
        print(f"    - {binding}")


def example_5_different_length_videos():
    """Example 5: Critical Use Case - Different Length Videos"""
    print("\n" + "=" * 60)
    print("Example 5: Different-Length Videos (CRITICAL USE CASE)")
    print("=" * 60)

    print("\n[*] Scenario:")
    print("  - P1 watches a 10-second video")
    print("  - P2 watches a 15-second video")
    print("  - Need separate end markers for each participant")

    print("\n[*] Configuration:")
    print("  VideoPhase with marker bindings:")
    print("    1. video_start -> 100# (sent when both start)")
    print("    2. video_p1_end -> 210# (sent when P1's video ends)")
    print("    3. video_p2_end -> 220# (sent when P2's video ends)")

    print("\n[*] Timeline for Trial 3:")
    print("  t=0.000s: Both videos start -> Marker 1003 (video_start)")
    print("  t=10.000s: P1's video ends -> Marker 2103 (video_p1_end)")
    print("  t=15.000s: P2's video ends -> Marker 2203 (video_p2_end)")
    print("  t=15.000s: Both complete, proceed to next phase")

    print("\n[+] Result: Accurate timing markers for each participant's video completion!")
    print("  This is CRITICAL for analyzing EEG data aligned to video content.")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("LSL MARKER SYSTEM - USAGE EXAMPLES")
    print("=" * 60)

    example_1_marker_catalog()
    example_2_template_resolution()
    example_3_phase_configuration()
    example_4_serialization()
    example_5_different_length_videos()

    print("\n" + "=" * 60)
    print("[+] All examples completed!")
    print("=" * 60)
    print("\n[*] Key Features Demonstrated:")
    print("  [OK] Marker catalog with named markers")
    print("  [OK] Template resolution (trial-indexed, participant-specific)")
    print("  [OK] Multi-marker events (separate P1/P2 end markers)")
    print("  [OK] Phase configuration with marker bindings")
    print("  [OK] Serialization/deserialization")
    print("  [OK] Different-length video handling")
    print("\n[+] Ready to use in your experiments!")


if __name__ == "__main__":
    main()
