"""
String Marker System Example

Demonstrates how to use string markers with template variables from CSV columns.

This example shows:
1. Creating a trial list CSV with a 'type' column (happy, sad, neutral)
2. Defining string markers in the catalog ({type}_start, {type}_end, etc.)
3. Configuring phases to send string markers based on trial data
4. Running experiment and tracking all markers sent
5. Exporting marker log and summary

String markers are useful when you want descriptive event names like:
  "happy_start", "sad_end", "neutral_video_complete"
instead of numeric codes.

LSL supports both integer and string markers natively.
"""

import os
import sys
import tempfile
import pandas as pd
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.markers import (
    MarkerDefinition, MarkerCatalog, MarkerBinding,
    resolve_marker_template, MarkerLogger
)
from core.execution.phases import VideoPhase, FixationPhase, RatingPhase
from core.execution import Procedure


def create_sample_trial_list_with_types():
    """Create a sample CSV with video pairs and emotion types"""
    # Create sample trial list with 'type' column
    trials = [
        {
            'trial_id': 1,
            'VideoPath1': 'videos/happy_01.mp4',
            'VideoPath2': 'videos/happy_01.mp4',
            'type': 'happy',
            'condition': 'same'
        },
        {
            'trial_id': 2,
            'VideoPath1': 'videos/sad_01.mp4',
            'VideoPath2': 'videos/sad_02.mp4',
            'type': 'sad',
            'condition': 'different'
        },
        {
            'trial_id': 3,
            'VideoPath1': 'videos/neutral_01.mp4',
            'VideoPath2': 'videos/neutral_01.mp4',
            'type': 'neutral',
            'condition': 'same'
        },
    ]

    # Save to temporary CSV
    df = pd.DataFrame(trials)
    csv_path = tempfile.mktemp(suffix='_trials.csv')
    df.to_csv(csv_path, index=False)
    print(f"[*] Created trial list CSV: {csv_path}")
    print(f"    Columns: {list(df.columns)}")
    print(f"    Trials: {len(df)}")
    print()

    return csv_path, df


def setup_string_marker_catalog():
    """Add string marker definitions to the catalog"""
    catalog = MarkerCatalog()

    # Define string markers for different event types
    string_markers = [
        MarkerDefinition(
            name="Video Start (by type)",
            description="Video playback start with emotion type",
            template_pattern="{type}_start",
            marker_type='string'
        ),
        MarkerDefinition(
            name="Video End (by type)",
            description="Video playback end with emotion type",
            template_pattern="{type}_end",
            marker_type='string'
        ),
        MarkerDefinition(
            name="Video Complete (type + condition)",
            description="Both videos complete with type and condition info",
            template_pattern="{type}_{condition}_complete",
            marker_type='string'
        ),
        MarkerDefinition(
            name="Trial Start (by type)",
            description="Trial start with emotion type",
            template_pattern="trial_{trial_index}_{type}",
            marker_type='string'
        ),
    ]

    print("[*] Adding string marker definitions to catalog:")
    for marker_def in string_markers:
        success = catalog.add_definition(marker_def)
        status = "[+]" if success else "[-]"
        print(f"    {status} {marker_def.template_pattern}: {marker_def.description}")
    print()

    return catalog


def create_procedure_with_string_markers():
    """Create a procedure configured to send string markers"""
    procedure = Procedure("String Marker Demo")

    # Fixation phase with trial start marker
    fixation = FixationPhase(name="Fixation", duration=1.0)
    fixation.marker_bindings = [
        MarkerBinding(
            event_type="phase_start",
            marker_template="trial_{trial_index}_{type}",  # String template with trial_data
            participant=None
        ),
    ]
    procedure.add_phase(fixation)

    # Video phase with type-based markers
    video = VideoPhase(
        name="Video Playback",
        participant_1_video="{VideoPath1}",
        participant_2_video="{VideoPath2}"
    )
    video.marker_bindings = [
        MarkerBinding(
            event_type="video_start",
            marker_template="{type}_start",  # "happy_start", "sad_start", etc.
            participant=None
        ),
        MarkerBinding(
            event_type="video_p1_end",
            marker_template="{type}_end",  # "happy_end", "sad_end", etc.
            participant=1
        ),
        MarkerBinding(
            event_type="video_p2_end",
            marker_template="{type}_end",
            participant=2
        ),
        MarkerBinding(
            event_type="video_both_complete",
            marker_template="{type}_{condition}_complete",  # "happy_same_complete"
            participant=None
        ),
    ]
    procedure.add_phase(video)

    # Rating phase (keep using integer markers for ratings)
    rating = RatingPhase(
        name="Rating",
        question="How did the video make you feel?",
        timeout=10.0
    )
    rating.marker_bindings = [
        MarkerBinding(
            event_type="p1_response",
            marker_template="300#0$",  # Integer template: 300 + trial + rating
            participant=1
        ),
        MarkerBinding(
            event_type="p2_response",
            marker_template="500#0$",  # Integer template: 500 + trial + rating
            participant=2
        ),
    ]
    procedure.add_phase(rating)

    return procedure


def demonstrate_template_resolution():
    """Demonstrate how string templates get resolved with trial data"""
    print("[*] Demonstrating template resolution:")
    print()

    # Example trial data
    trial_data_examples = [
        {'trial_index': 1, 'type': 'happy', 'condition': 'same'},
        {'trial_index': 2, 'type': 'sad', 'condition': 'different'},
        {'trial_index': 3, 'type': 'neutral', 'condition': 'same'},
    ]

    # String templates to resolve
    templates = [
        "{type}_start",
        "{type}_end",
        "{type}_{condition}_complete",
        "trial_{trial_index}_{type}",
    ]

    for trial_data in trial_data_examples:
        print(f"  Trial {trial_data['trial_index']} (type={trial_data['type']}, condition={trial_data['condition']}):")
        for template in templates:
            resolved = resolve_marker_template(template, trial_data=trial_data)
            print(f"    {template:30} -> {resolved}")
        print()


def simulate_marker_logging():
    """Simulate logging markers during experiment execution"""
    print("[*] Simulating marker logging during experiment:")
    print()

    # Create marker logger
    logger = MarkerLogger(session_id="demo_session")

    # Simulate some marker events
    trial_data_examples = [
        {'trial_index': 1, 'type': 'happy', 'condition': 'same'},
        {'trial_index': 2, 'type': 'sad', 'condition': 'different'},
    ]

    for trial_data in trial_data_examples:
        trial_idx = trial_data['trial_index']

        # Trial start (string marker)
        marker = resolve_marker_template("trial_{trial_index}_{type}", trial_data=trial_data)
        logger.log_marker(
            marker=marker,
            event_type="phase_start",
            phase_name="Fixation",
            trial_index=trial_idx
        )
        print(f"  [Fixation] Trial {trial_idx}: {marker}")

        # Video start (string marker)
        marker = resolve_marker_template("{type}_start", trial_data=trial_data)
        logger.log_marker(
            marker=marker,
            event_type="video_start",
            phase_name="Video Playback",
            trial_index=trial_idx
        )
        print(f"  [Video] Start: {marker}")

        # Video end (string marker)
        marker = resolve_marker_template("{type}_end", trial_data=trial_data)
        logger.log_marker(
            marker=marker,
            event_type="video_p1_end",
            phase_name="Video Playback",
            trial_index=trial_idx,
            participant=1
        )
        print(f"  [Video] P1 End: {marker}")

        # Video complete (string marker with multiple variables)
        marker = resolve_marker_template("{type}_{condition}_complete", trial_data=trial_data)
        logger.log_marker(
            marker=marker,
            event_type="video_both_complete",
            phase_name="Video Playback",
            trial_index=trial_idx
        )
        print(f"  [Video] Complete: {marker}")

        # Rating (integer marker)
        rating_value = 7  # Simulated rating
        marker = resolve_marker_template("300#0$", trial_data=trial_data, response_value=rating_value)
        logger.log_marker(
            marker=marker,
            event_type="p1_response",
            phase_name="Rating",
            trial_index=trial_idx,
            participant=1,
            response_value=rating_value
        )
        print(f"  [Rating] P1: {marker} (integer marker: trial={trial_idx}, rating={rating_value})")
        print()

    # Export marker log
    log_csv = tempfile.mktemp(suffix='_markers.csv')
    summary_txt = tempfile.mktemp(suffix='_summary.txt')

    logger.export_to_csv(log_csv)
    logger.export_summary(summary_txt)

    print(f"[+] Exported marker log to: {log_csv}")
    print(f"[+] Exported marker summary to: {summary_txt}")
    print()

    # Show summary
    print("[*] Marker Summary:")
    with open(summary_txt, 'r') as f:
        print(f.read())

    return logger, log_csv, summary_txt


def demonstrate_codebook_export():
    """Export updated codebook with string markers"""
    catalog = MarkerCatalog()

    codebook_path = tempfile.mktemp(suffix='_CodeBook.txt')
    catalog.export_to_codebook(codebook_path)

    print(f"[*] Exported CodeBook to: {codebook_path}")
    print()
    print("[*] CodeBook Contents:")
    print("-" * 70)
    with open(codebook_path, 'r') as f:
        print(f.read())
    print("-" * 70)
    print()

    return codebook_path


def main():
    """Run the string markers demonstration"""
    print("=" * 70)
    print("STRING MARKER SYSTEM DEMONSTRATION")
    print("=" * 70)
    print()

    # 1. Create trial list with 'type' column
    csv_path, df = create_sample_trial_list_with_types()
    print(f"Sample trial data:")
    print(df)
    print()

    # 2. Setup string marker catalog
    catalog = setup_string_marker_catalog()

    # 3. Demonstrate template resolution
    demonstrate_template_resolution()

    # 4. Create procedure with string markers
    procedure = create_procedure_with_string_markers()
    print(f"[*] Created procedure with {len(procedure.phases)} phases")
    print(f"    Phases: {[p.name for p in procedure.phases]}")
    print()

    # 5. Simulate marker logging
    logger, log_csv, summary_txt = simulate_marker_logging()

    # 6. Export updated codebook
    codebook_path = demonstrate_codebook_export()

    # Summary
    print("=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)
    print()
    print("Key Takeaways:")
    print()
    print("1. STRING TEMPLATES:")
    print("   - Use {variable} syntax for string markers")
    print("   - Variables come from trial_data (CSV columns)")
    print("   - Examples: {type}_start, {type}_{condition}_complete")
    print()
    print("2. INTEGER TEMPLATES (still supported):")
    print("   - Use # for trial_index, $ for response_value")
    print("   - Examples: 100#, 300#0$")
    print()
    print("3. MIXED USAGE:")
    print("   - Can use string markers for events (video_start, video_end)")
    print("   - Can use integer markers for responses (ratings)")
    print("   - Both types work seamlessly together")
    print()
    print("4. MARKER LOGGING:")
    print(f"   - All markers tracked automatically")
    print(f"   - Export to CSV for analysis: {log_csv}")
    print(f"   - Export summary for documentation: {summary_txt}")
    print()
    print("5. CODEBOOK EXPORT:")
    print(f"   - Auto-generated documentation: {codebook_path}")
    print(f"   - Includes both integer and string marker sections")
    print()
    print("6. INTEGRATION WITH CSV:")
    print("   - Add custom columns to trial CSV (type, condition, etc.)")
    print("   - Use those columns in marker templates")
    print("   - Templates resolved automatically during execution")
    print()


if __name__ == "__main__":
    main()
