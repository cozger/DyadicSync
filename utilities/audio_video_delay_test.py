"""
Audio-Video Delay Measurement Tool

Measures the actual audio-video delay on your system to help calibrate
the audio lead time setting for synchronized playback.

Usage:
    python utilities/audio_video_delay_test.py [--trials N] [--lead MS] [--video PATH]

Arguments:
    --trials N    Number of trials to run (default: 5)
    --lead MS     Audio lead time in ms to test (default: current setting)
    --video PATH  Path to test video (default: first video from video_pairs_extended.csv)

Output:
    - Per-trial timing data
    - Summary statistics (mean, std, min, max)
    - Suggested optimal audio lead time
"""

import sys
import os
import time
import argparse
import statistics

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pyglet
import pandas as pd


def run_delay_test(video_path: str, audio_device: int, num_trials: int, audio_lead_ms: float):
    """
    Run multiple trials to measure audio-video delay.

    Args:
        video_path: Path to test video
        audio_device: Audio device index
        num_trials: Number of trials to run
        audio_lead_ms: Audio lead time setting to test

    Returns:
        List of delay measurements (positive = audio first)
    """
    from playback.synchronized_player import SynchronizedPlayer
    from playback.sync_engine import SyncEngine

    # Create a test window (can be small, just needs OpenGL context)
    window = pyglet.window.Window(width=640, height=480, caption="Delay Test")

    delays = []

    for trial in range(num_trials):
        print(f"\n{'='*60}")
        print(f"Trial {trial + 1}/{num_trials}")
        print(f"{'='*60}")

        # Create and prepare player
        player = SynchronizedPlayer(video_path, audio_device, window)

        # Temporarily override the audio lead setting
        player.DEFAULT_AUDIO_LEAD_MS = audio_lead_ms

        # Prepare (extract audio)
        print("Preparing player...")
        player.prepare()

        # Create Pyglet player (must be on main thread)
        player.create_player()

        # Calculate sync timestamp (200ms in future)
        sync_timestamp = SyncEngine.calculate_sync_timestamp(prep_time_ms=200)

        # Arm with specified lead time
        print(f"Arming with {audio_lead_ms:.0f}ms audio lead...")
        player.arm_sync_timestamp(sync_timestamp, audio_lead_ms=audio_lead_ms)

        # Trigger playback
        print("Triggering playback...")
        SyncEngine.trigger_synchronized_playback([player])

        # Run Pyglet event loop briefly to process callbacks
        start_time = time.time()
        playback_duration = 2.0  # Play for 2 seconds

        while time.time() - start_time < playback_duration:
            pyglet.clock.tick()
            window.dispatch_events()

            # Check if we have delay data
            delay_data = player.get_audio_video_delay()
            if delay_data and delay_data not in [None]:
                break

            time.sleep(0.01)

        # Get final delay measurement
        delay_data = player.get_audio_video_delay()

        if delay_data:
            delay_ms = delay_data['delay_ms']
            delays.append(delay_ms)
            print(f"\n>>> Measured delay: {delay_ms:+.1f}ms (audio {'before' if delay_ms > 0 else 'after'} video)")
        else:
            print("\n>>> WARNING: Could not measure delay (playback may not have started)")

        # Stop and cleanup
        print("Stopping player...")
        player.stop()

        # Brief pause between trials
        time.sleep(0.5)

    # Close window
    window.close()

    return delays


def analyze_delays(delays: list, configured_lead_ms: float):
    """
    Analyze delay measurements and suggest optimal lead time.

    Args:
        delays: List of measured delays (positive = audio first)
        configured_lead_ms: The audio lead setting used for testing
    """
    if not delays:
        print("\nNo delay measurements to analyze!")
        return

    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")

    print(f"\nConfigured audio lead: {configured_lead_ms:.0f}ms")
    print(f"Number of trials: {len(delays)}")

    # Statistics
    mean_delay = statistics.mean(delays)
    std_delay = statistics.stdev(delays) if len(delays) > 1 else 0
    min_delay = min(delays)
    max_delay = max(delays)

    print(f"\nMeasured Delays (positive = audio started first):")
    print(f"  Mean:   {mean_delay:+.1f}ms")
    print(f"  StdDev: {std_delay:.1f}ms")
    print(f"  Min:    {min_delay:+.1f}ms")
    print(f"  Max:    {max_delay:+.1f}ms")

    # Interpretation
    print(f"\nInterpretation:")
    if mean_delay > 10:
        print(f"  Audio is starting {mean_delay:.0f}ms BEFORE video on average.")
        print(f"  This means your audio lead setting ({configured_lead_ms:.0f}ms) is too high.")
        suggested = configured_lead_ms - mean_delay
        print(f"  Suggested adjustment: reduce audio lead to ~{max(0, suggested):.0f}ms")
    elif mean_delay < -10:
        print(f"  Audio is starting {abs(mean_delay):.0f}ms AFTER video on average.")
        print(f"  This means your audio lead setting ({configured_lead_ms:.0f}ms) is too low.")
        suggested = configured_lead_ms + abs(mean_delay)
        print(f"  Suggested adjustment: increase audio lead to ~{suggested:.0f}ms")
    else:
        print(f"  Audio-video sync is within acceptable range ({mean_delay:+.1f}ms)!")
        print(f"  Current audio lead setting ({configured_lead_ms:.0f}ms) appears optimal.")

    # Calculate optimal lead time for perfect sync
    # If we're measuring delay D with lead L, then optimal = L - D
    optimal_lead = configured_lead_ms - mean_delay
    print(f"\nOptimal audio lead for your system: {optimal_lead:.0f}ms")
    print(f"(This compensates for {configured_lead_ms - optimal_lead:.0f}ms of audio path latency)")

    # Per-trial breakdown
    print(f"\nPer-trial measurements:")
    for i, d in enumerate(delays):
        bar_len = int(abs(d) / 10)
        if d > 0:
            bar = "+" + "=" * bar_len
        else:
            bar = "-" + "=" * bar_len
        print(f"  Trial {i+1}: {d:+7.1f}ms {bar}")


def main():
    parser = argparse.ArgumentParser(
        description="Measure audio-video delay to calibrate sync settings"
    )
    parser.add_argument(
        "--trials", "-n", type=int, default=5,
        help="Number of trials to run (default: 5)"
    )
    parser.add_argument(
        "--lead", "-l", type=float, default=None,
        help="Audio lead time in ms (default: current setting from code)"
    )
    parser.add_argument(
        "--video", "-v", type=str, default=None,
        help="Path to test video"
    )
    parser.add_argument(
        "--device", "-d", type=int, default=None,
        help="Audio device index (run audioscan.py to see available devices)"
    )

    args = parser.parse_args()

    # Get current audio lead setting if not specified
    if args.lead is None:
        from playback.synchronized_player import SynchronizedPlayer
        args.lead = SynchronizedPlayer.DEFAULT_AUDIO_LEAD_MS
        print(f"Using current audio lead setting: {args.lead:.0f}ms")

    # Get test video if not specified
    if args.video is None:
        # Try to find a video from the CSV
        csv_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "video_pairs_extended.csv"
        )
        if os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            if 'VideoPath1' in df.columns and len(df) > 0:
                args.video = df['VideoPath1'].iloc[0]
                print(f"Using video from CSV: {args.video}")

        if args.video is None:
            print("ERROR: No test video specified and couldn't find one in CSV.")
            print("Usage: python audio_video_delay_test.py --video /path/to/video.mp4")
            sys.exit(1)

    if not os.path.exists(args.video):
        print(f"ERROR: Video file not found: {args.video}")
        sys.exit(1)

    # Get audio device if not specified
    if args.device is None:
        import sounddevice as sd
        # Default to device 0, but warn user
        args.device = sd.default.device[1]  # Default output device
        print(f"Using default audio output device: {args.device}")
        print("(Run 'python utilities/audioscan.py' to see all devices)")

    print(f"\n{'='*60}")
    print("AUDIO-VIDEO DELAY MEASUREMENT TOOL")
    print(f"{'='*60}")
    print(f"Video: {args.video}")
    print(f"Audio device: {args.device}")
    print(f"Audio lead: {args.lead:.0f}ms")
    print(f"Trials: {args.trials}")

    # Run the test
    delays = run_delay_test(
        video_path=args.video,
        audio_device=args.device,
        num_trials=args.trials,
        audio_lead_ms=args.lead
    )

    # Analyze results
    analyze_delays(delays, args.lead)


if __name__ == "__main__":
    main()
