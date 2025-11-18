"""
LSL Stream Scanner - Verify LSL streams are broadcasting on the network

This utility helps diagnose LabRecorder auto-start issues by independently
verifying that LSL streams are active and discoverable before attempting
to start recording.

Usage:
    python utilities/lsl_stream_scanner.py

Requirements:
    pip install pylsl
"""

import pylsl
import time
import sys


def scan_lsl_streams(timeout=2.0, verbose=True):
    """
    Scan network for active LSL streams.

    Args:
        timeout: How long to wait for stream discovery (seconds)
        verbose: Print detailed information

    Returns:
        List of pylsl.StreamInfo objects
    """
    if verbose:
        print(f"[LSL Scanner] Scanning for LSL streams (timeout={timeout}s)...")
        print(f"[LSL Scanner] Please wait...")

    try:
        streams = pylsl.resolve_streams(timeout)
    except Exception as e:
        if verbose:
            print(f"[LSL Scanner] ERROR: Failed to resolve streams: {e}")
        return []

    if verbose:
        print(f"\n{'='*70}")
        if len(streams) == 0:
            print(f"[LSL Scanner] ⚠️  NO STREAMS FOUND")
            print(f"{'='*70}")
            print(f"\n[LSL Scanner] Troubleshooting:")
            print(f"  1. Make sure Emotiv software is running with LSL streaming enabled")
            print(f"  2. Check that experiment is running (creates marker stream)")
            print(f"  3. Verify no firewall is blocking LSL multicast (224.0.0.0/4)")
            print(f"  4. Try running this scanner while Emotiv is actively streaming")
            print(f"  5. Check Emotiv LSL settings - ensure 'Enable LSL' is checked")
        else:
            print(f"[LSL Scanner] ✓ Found {len(streams)} stream(s):")
            print(f"{'='*70}")
            for i, stream in enumerate(streams, 1):
                print(f"\n  Stream #{i}:")
                print(f"    Name:         {stream.name()}")
                print(f"    Type:         {stream.type()}")
                print(f"    Source ID:    {stream.source_id()}")
                print(f"    Channels:     {stream.channel_count()}")
                print(f"    Sample Rate:  {stream.nominal_srate()} Hz")
                print(f"    Hostname:     {stream.hostname()}")
                print(f"    UID:          {stream.uid()}")

    return streams


def wait_for_streams(min_streams=1, timeout=30.0, check_interval=2.0, verbose=True):
    """
    Wait until minimum number of streams are available.

    Useful for waiting for Emotiv or other devices to start streaming
    before launching LabRecorder.

    Args:
        min_streams: Minimum streams required
        timeout: Maximum wait time (seconds)
        check_interval: Time between checks (seconds)
        verbose: Print status updates

    Returns:
        True if streams found, False if timeout
    """
    if verbose:
        print(f"\n{'='*70}")
        print(f"[LSL Scanner] Waiting for at least {min_streams} stream(s)...")
        print(f"[LSL Scanner] Timeout: {timeout}s, Check interval: {check_interval}s")
        print(f"{'='*70}\n")

    start_time = time.time()
    attempt = 0

    while (time.time() - start_time) < timeout:
        attempt += 1
        elapsed = time.time() - start_time

        if verbose:
            print(f"[LSL Scanner] Attempt {attempt} (elapsed: {elapsed:.1f}s)...")

        try:
            streams = pylsl.resolve_streams(check_interval)

            if len(streams) >= min_streams:
                if verbose:
                    print(f"\n[LSL Scanner] ✓ Success! Found {len(streams)} stream(s):")
                    for stream in streams:
                        print(f"  - {stream.name()} ({stream.type()})")
                return True

            if verbose:
                remaining = timeout - elapsed
                print(f"[LSL Scanner]   Found {len(streams)} stream(s) - need {min_streams}")
                print(f"[LSL Scanner]   Still waiting... ({remaining:.1f}s remaining)\n")

        except Exception as e:
            if verbose:
                print(f"[LSL Scanner]   Error during scan: {e}\n")

    if verbose:
        print(f"\n[LSL Scanner] ✗ Timeout reached!")
        print(f"[LSL Scanner] Only found {len(streams)} stream(s) (needed {min_streams})")

    return False


def continuous_monitor(interval=5.0):
    """
    Continuously monitor LSL streams and report changes.

    Useful for watching when devices start/stop streaming.

    Args:
        interval: Time between scans (seconds)
    """
    print(f"\n{'='*70}")
    print(f"[LSL Scanner] Continuous Monitor Mode")
    print(f"[LSL Scanner] Press Ctrl+C to stop")
    print(f"{'='*70}\n")

    previous_streams = set()
    scan_count = 0

    try:
        while True:
            scan_count += 1
            print(f"[LSL Scanner] Scan #{scan_count} at {time.strftime('%H:%M:%S')}...")

            streams = pylsl.resolve_streams(2.0)
            current_streams = {(s.name(), s.type(), s.source_id()) for s in streams}

            # Detect new streams
            new_streams = current_streams - previous_streams
            if new_streams:
                print(f"[LSL Scanner] ✓ NEW STREAMS DETECTED:")
                for name, type_, source in new_streams:
                    print(f"  + {name} ({type_}) - {source}")

            # Detect removed streams
            removed_streams = previous_streams - current_streams
            if removed_streams:
                print(f"[LSL Scanner] ✗ STREAMS REMOVED:")
                for name, type_, source in removed_streams:
                    print(f"  - {name} ({type_}) - {source}")

            # Show current count
            if not new_streams and not removed_streams:
                print(f"[LSL Scanner]   {len(streams)} stream(s) active (no changes)")

            previous_streams = current_streams

            print(f"[LSL Scanner] Next scan in {interval}s...\n")
            time.sleep(interval)

    except KeyboardInterrupt:
        print(f"\n[LSL Scanner] Monitoring stopped by user")


def main():
    """Main entry point for command-line usage."""
    print(f"\n{'='*70}")
    print(f"  LSL Stream Scanner")
    print(f"  DyadicSync Diagnostic Utility")
    print(f"{'='*70}\n")

    # Check if pylsl is installed
    try:
        import pylsl
        print(f"[LSL Scanner] pylsl version: {pylsl.__version__}")
    except ImportError:
        print(f"[LSL Scanner] ERROR: pylsl not installed!")
        print(f"[LSL Scanner] Install with: pip install pylsl")
        sys.exit(1)

    # Check command-line arguments
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "wait":
            # Wait mode: wait for streams to appear
            min_streams = int(sys.argv[2]) if len(sys.argv) > 2 else 1
            timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
            success = wait_for_streams(min_streams=min_streams, timeout=timeout)
            sys.exit(0 if success else 1)

        elif command == "monitor":
            # Monitor mode: continuously watch for stream changes
            interval = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
            continuous_monitor(interval=interval)
            sys.exit(0)

        elif command == "help":
            print(f"Usage:")
            print(f"  python utilities/lsl_stream_scanner.py          # Scan once")
            print(f"  python utilities/lsl_stream_scanner.py wait 2 30 # Wait for 2 streams (30s timeout)")
            print(f"  python utilities/lsl_stream_scanner.py monitor 5 # Monitor every 5 seconds")
            print(f"  python utilities/lsl_stream_scanner.py help      # Show this help")
            sys.exit(0)

        else:
            print(f"[LSL Scanner] Unknown command: {command}")
            print(f"[LSL Scanner] Use 'help' to see available commands")
            sys.exit(1)

    # Default: single scan
    streams = scan_lsl_streams(timeout=3.0)

    print(f"\n{'='*70}")
    if len(streams) > 0:
        print(f"[LSL Scanner] ✓ SUCCESS: Found {len(streams)} stream(s)")
        print(f"[LSL Scanner] LabRecorder should be able to discover these streams")
        sys.exit(0)
    else:
        print(f"[LSL Scanner] ✗ FAILURE: No streams found")
        print(f"[LSL Scanner] LabRecorder will have nothing to record!")
        sys.exit(1)


if __name__ == "__main__":
    main()
