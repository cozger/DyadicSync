"""
LabRecorder RCS Interactive Test Script

This script tests LabRecorder Remote Control Socket (RCS) commands step-by-step
with interactive verification to diagnose why auto-start may not be working.

Usage:
    1. Start Emotiv software with LSL streaming enabled
    2. Start LabRecorder with RCS enabled (port 22345)
    3. Run: python utilities/test_labrecorder_rcs.py

The script will:
    - Verify LSL streams exist using pylsl
    - Test each RCS command individually
    - Prompt you to check LabRecorder UI after each command
    - Identify whether the problem is LSL streams or RCS commands

Requirements:
    pip install pylsl
"""

import sys
import time


def main():
    """Main interactive test sequence."""
    print("\n" + "="*70)
    print("  LabRecorder RCS Interactive Test")
    print("  DyadicSync Diagnostic Tool")
    print("="*70 + "\n")

    # Check dependencies
    try:
        import pylsl
        print(f"[Test] OK pylsl version: {pylsl.__version__}")
    except ImportError:
        print(f"[Test] ERROR: pylsl not installed!")
        print(f"[Test] Install with: pip install pylsl")
        sys.exit(1)

    # Import LabRecorder controller
    try:
        sys.path.insert(0, 'C:\\Users\\optilab\\Desktop\\DyadicSync')
        from core.labrecorder_control import LabRecorderController
        print(f"[Test] OK LabRecorderController imported")
    except ImportError as e:
        print(f"[Test] ERROR: Cannot import LabRecorderController: {e}")
        sys.exit(1)

    print("\n" + "="*70)
    print("STEP 1: Pre-Check - Verify LSL Streams Exist")
    print("="*70 + "\n")

    print("[Test] Scanning for LSL streams (3 second timeout)...")
    streams = pylsl.resolve_streams(3.0)

    if len(streams) == 0:
        print("\n[Test] [X] CRITICAL ERROR: No LSL streams found!")
        print("[Test]")
        print("[Test] This is the root cause of your problem!")
        print("[Test]")
        print("[Test] Troubleshooting:")
        print("[Test]   1. Make sure Emotiv software is running")
        print("[Test]   2. Enable LSL streaming in Emotiv settings")
        print("[Test]   3. Verify Emotiv shows 'Streaming' status")
        print("[Test]   4. Check firewall isn't blocking LSL multicast")
        print("[Test]")
        print("[Test] Run utilities/lsl_stream_scanner.py for more diagnostics")
        print("\n" + "="*70)

        response = input("\n[Test] Continue anyway to test RCS commands? (y/n): ").strip().lower()
        if response != 'y':
            print("[Test] Test aborted")
            sys.exit(1)
    else:
        print(f"\n[Test] [OK] SUCCESS: Found {len(streams)} LSL stream(s):\n")
        for i, stream in enumerate(streams, 1):
            print(f"  Stream #{i}:")
            print(f"    Name:     {stream.name()}")
            print(f"    Type:     {stream.type()}")
            print(f"    Channels: {stream.channel_count()}")
            print(f"    Rate:     {stream.nominal_srate()} Hz")
            print()

        print("[Test] LabRecorder SHOULD be able to discover these streams")

    input("\n[Test] Press Enter to continue...")

    # Step 2: Connect to LabRecorder RCS
    print("\n" + "="*70)
    print("STEP 2: Connect to LabRecorder RCS")
    print("="*70 + "\n")

    print("[Test] Make sure LabRecorder is running with RCS enabled")
    print("[Test] Check: LabRecorder → Settings → Remote Control Socket → Enabled")
    print("[Test] Default port: 22345")

    input("\n[Test] Press Enter when LabRecorder is ready...")

    print("\n[Test] Connecting to LabRecorder RCS...")
    controller = LabRecorderController(host='localhost', port=22345, timeout=5.0)

    if not controller.connect():
        print("\n[Test] [X] FAILED: Cannot connect to LabRecorder RCS")
        print("[Test]")
        print("[Test] Troubleshooting:")
        print("[Test]   1. Is LabRecorder running?")
        print("[Test]   2. Is Remote Control Socket enabled in LabRecorder settings?")
        print("[Test]   3. Is port 22345 correct? (check LabRecorder settings)")
        print("[Test]   4. Is another program using port 22345?")
        sys.exit(1)

    print("\n[Test] [OK] SUCCESS: Connected to LabRecorder RCS")

    input("\n[Test] Press Enter to continue...")

    # Step 3: Test "update" command
    print("\n" + "="*70)
    print("STEP 3: Test 'update' Command (Stream Discovery)")
    print("="*70 + "\n")

    print("[Test] About to send 'update' command to LabRecorder")
    print("[Test] This should trigger stream discovery (like clicking Update button)")
    print("[Test]")
    print("[Test] WATCH LABRECORDER GUI NOW:")
    print("[Test]   - Stream list should start populating")
    print("[Test]   - May see 'Refreshing...' indicator")
    print("[Test]   - Should take ~2 seconds")

    input("\n[Test] Press Enter to send 'update' command...")

    success = controller.update_streams()

    if not success:
        print("\n[Test] [X] FAILED: 'update' command failed to send")
        controller.close()
        sys.exit(1)

    print("\n[Test] [OK] Command sent successfully")
    print("[Test] Waiting 5 seconds for stream discovery to complete...")

    for i in range(5, 0, -1):
        print(f"[Test]   {i}...", flush=True)
        time.sleep(1.0)

    print("\n" + "="*70)
    print("CHECK LABRECORDER GUI NOW:")
    print("="*70)
    print()
    print("  Question 1: Does the stream list show any streams?")
    print("              (Should show the LSL streams we found earlier)")
    print()
    print("  Question 2: Are the stream names visible in the list?")
    print()
    print("  Question 3: Are any streams shown in RED (missing)?")
    print()
    print("="*70)

    update_worked = input("\n[Test] Did the 'update' populate the stream list? (y/n): ").strip().lower()

    if update_worked != 'y':
        print("\n[Test] [!]  WARNING: 'update' command did not populate stream list!")
        print("[Test]")
        print("[Test] This is the problem! Possible causes:")
        print("[Test]   1. LSL streams started AFTER LabRecorder was launched")
        print("[Test]      → Try clicking Update button manually - does it work?")
        print("[Test]   2. LabRecorder can't see LSL multicast packets")
        print("[Test]      → Firewall or network configuration issue")
        print("[Test]   3. LabRecorder RCS 'update' command may be broken")
        print("[Test]      → Try newer LabRecorder version")
        print("[Test]")

        manual_update = input("\n[Test] Try clicking Update button manually in LabRecorder (y to continue): ").strip().lower()
        if manual_update != 'y':
            controller.close()
            sys.exit(1)
    else:
        print("\n[Test] [OK] EXCELLENT: 'update' command is working correctly!")

    input("\n[Test] Press Enter to continue...")

    # Step 4: Test "select all" command
    print("\n" + "="*70)
    print("STEP 4: Test 'select all' Command")
    print("="*70 + "\n")

    print("[Test] About to send 'select all' command to LabRecorder")
    print("[Test] This should check all checkboxes in the stream list")
    print("[Test]")
    print("[Test] WATCH LABRECORDER GUI NOW:")
    print("[Test]   - All checkboxes should become checked")
    print("[Test]   - Should happen immediately")

    input("\n[Test] Press Enter to send 'select all' command...")

    success = controller.select_all_streams()

    if not success:
        print("\n[Test] [X] FAILED: 'select all' command failed to send")
        controller.close()
        sys.exit(1)

    print("\n[Test] [OK] Command sent successfully")
    print("[Test] Waiting 1 second for checkboxes to update...")
    time.sleep(1.0)

    print("\n" + "="*70)
    print("CHECK LABRECORDER GUI NOW:")
    print("="*70)
    print()
    print("  Question: Are all stream checkboxes now CHECKED?")
    print()
    print("="*70)

    select_worked = input("\n[Test] Did 'select all' check all the checkboxes? (y/n): ").strip().lower()

    if select_worked != 'y':
        print("\n[Test] [!]  WARNING: 'select all' command did not check boxes!")
        print("[Test]")
        print("[Test] Possible causes:")
        print("[Test]   1. Stream list is still empty (update didn't work)")
        print("[Test]   2. LabRecorder RCS 'select all' command may be broken")
        print("[Test]   3. Need to wait longer for UI to update")
        print("[Test]")
    else:
        print("\n[Test] [OK] EXCELLENT: 'select all' command is working correctly!")

    input("\n[Test] Press Enter to continue...")

    # Step 5: Test "start" command
    print("\n" + "="*70)
    print("STEP 5: Test 'start' Command")
    print("="*70 + "\n")

    print("[Test] About to send 'start' command to LabRecorder")
    print("[Test] This should start recording with selected streams")
    print("[Test]")
    print("[Test] WATCH LABRECORDER GUI NOW:")
    print("[Test]   - Recording indicator should turn RED")
    print("[Test]   - Should see file path being created")

    input("\n[Test] Press Enter to send 'start' command...")

    # Configure test filename
    filename_cmd = "filename {root:C:/temp} {participant:sub-999} {session:ses-01} {task:RCS_Test}"
    print(f"\n[Test] Setting filename: {filename_cmd}")
    controller.send_command(filename_cmd)
    time.sleep(0.3)

    success = controller.send_command("start")

    if not success:
        print("\n[Test] [X] FAILED: 'start' command failed to send")
        controller.close()
        sys.exit(1)

    print("\n[Test] [OK] Command sent successfully")
    print("[Test] Waiting 1 second for recording to start...")
    time.sleep(1.0)

    print("\n" + "="*70)
    print("CHECK LABRECORDER GUI NOW:")
    print("="*70)
    print()
    print("  Question 1: Is the recording indicator RED/active?")
    print()
    print("  Question 2: Does it show the output filename?")
    print()
    print("  Question 3: Are the stream counts incrementing?")
    print()
    print("="*70)

    start_worked = input("\n[Test] Did recording start successfully? (y/n): ").strip().lower()

    if start_worked != 'y':
        print("\n[Test] [!]  WARNING: 'start' command did not begin recording!")
        controller.close()
        sys.exit(1)
    else:
        print("\n[Test] [OK] EXCELLENT: 'start' command is working correctly!")

    input("\n[Test] Press Enter to stop recording...")

    # Step 6: Test "stop" command
    print("\n" + "="*70)
    print("STEP 6: Test 'stop' Command")
    print("="*70 + "\n")

    success = controller.stop_recording()

    if not success:
        print("\n[Test] [X] FAILED: 'stop' command failed")
        controller.close()
        sys.exit(1)

    print("\n[Test] [OK] Recording stopped successfully")

    controller.close()

    # Final summary
    print("\n" + "="*70)
    print("TEST SUMMARY")
    print("="*70 + "\n")

    if len(streams) > 0 and update_worked == 'y' and select_worked == 'y' and start_worked == 'y':
        print("[Test] [OK][OK][OK] ALL TESTS PASSED [OK][OK][OK]")
        print()
        print("[Test] RCS commands are working correctly!")
        print("[Test]")
        print("[Test] If auto-start still doesn't work in your experiment:")
        print("[Test]   1. LSL streams may not exist when auto-start runs")
        print("[Test]   2. Timing issue - streams created too late")
        print("[Test]   3. Check experiment creates LSL outlet before LabRecorder starts")
        print()
    else:
        print("[Test] [!]  SOME TESTS FAILED")
        print()
        print("[Test] Review the failures above to identify the root cause")
        print()

    print("="*70)
    print()


if __name__ == "__main__":
    main()
