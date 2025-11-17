# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**DyadicSync** is a dyadic video synchronization experiment system that presents video stimuli to two participants simultaneously and sends event markers for synchronization with external recording systems. The system handles:
- Synchronized video playback across dual displays with independent audio routing
- LSL event marker transmission for synchronization with external EEG recording (LabRecorder, Emotiv)
- EEG headset-to-participant assignment (for post-hoc data pairing)
- Real-time behavioral ratings from both participants
- Baseline periods with fixation crosses
- CSV output of behavioral data (ratings, timestamps)

**Technology Stack**: Python 3.11, PsychoPy 2023.1.3, Pyglet 1.4.11, LSL (pylsl), FFmpeg, sounddevice, pandas

## Running the Experiment

### Main Command
```bash
python WithBaseline.py
```

### System Requirements
- **3 screens**: Control monitor + 2 participant displays
- **2 audio devices**: Independent headphone routing for each participant
- **2 EEG headsets**: Emotiv systems with LSL streaming enabled (managed by external software, not this code)
- **External recording software**: LabRecorder (EEG/markers), YouQuantified (face synchrony), LSL WebSocket, Video capture utility

### Execution Phases
1. **Welcome Screen** - Headset assignment (G/K keys), instructions display
2. **Baseline Recording** - 240-second fixation cross on both screens
3. **Video Loop** - For each pair: fixation (3s) → video → rating → next pair
4. **Exit** - Automatic after all pairs complete or ESC key

See `Exp Setup Instructions.txt` for detailed setup procedure with all auxiliary software.

## Configuration Parameters

Key parameters at the top of `WithBaseline.py` (legacy script):

```python
audio_device_1_index = 9        # Participant 1 audio output device
audio_device_2_index = 7        # Participant 2 audio output device
baseline_length = 240           # Baseline recording duration (seconds)
audio_offset_ms = 350           # REMOVED in new architecture (replaced by SyncEngine)
csv_path = r"...\video_pairs_extended.csv"  # Stimulus list
```

**Note**: Audio device indices are hardware-specific. Use `utilities/audioscan.py` to enumerate available devices before running.

**Important**: The new architecture (core/execution) uses **SyncEngine** for automatic timestamp-based synchronization. The manual `audio_offset_ms` configuration has been **completely removed** from the new system. The 350ms offset was a hardware-specific workaround that is no longer needed with timestamp-based sync.

## Development & Testing Tools

Located in `utilities/`:

- **`audioscan.py`** - Lists all audio devices and tests playback with sine wave. Run this first to identify correct device indices.
- **`videotester.py`** - Tests video playback and displays codec information via FFmpeg analysis. Useful for diagnosing video loading issues.
- **`3secondTester.py`** - Tests the 3-second fixation cross timing independently.
- **`video_converter.py`** - Batch converts videos to compatible formats if needed.
- **`downloadsvideos.py`** - Utility for downloading video stimuli.

## Architecture

### Modern Architecture (core/execution)

The new execution framework uses a modular architecture with timestamp-based synchronization:

**`SyncEngine`** (`playback/sync_engine.py`)
- **Purpose**: High-precision timestamp-based synchronization for multi-player coordination
- **Key Methods**:
  - `calculate_sync_timestamp(prep_time_ms)` - Calculates future sync point
  - `wait_until_timestamp(target)` - Hybrid sleep (OS sleep + busy-wait) for <1ms precision
  - `play_synchronized(players, prep_time_ms)` - Launches players at same timestamp
  - `_verify_sync(actual_starts, target)` - Logs drift/spread metrics
- **Performance**: <5ms audio-video sync, <2ms inter-player sync (verified every trial)
- **Usage**: Automatically invoked by `VideoPhase.execute()`, no manual configuration needed

**`SynchronizedPlayer`** (`playback/synchronized_player.py`)
- Manages video playback and audio extraction for a single participant
- **New**: `play_at_timestamp(sync_timestamp)` method for precise sync
- Uses FFmpeg to extract audio to temporary WAV files
- Routes audio to specific device via sounddevice
- Pyglet handles video rendering with muted player
- Compatible with SyncEngine coordination

**`VideoPhase`** (`core/execution/phases/video_phase.py`)
- Integrates SyncEngine for automatic synchronization
- Returns `sync_quality` metrics in execution result
- Logs drift and spread to console every trial
- No manual offset configuration required

### Legacy Architecture (WithBaseline.py)

**`SynchronizedPlayer`** (lines 304-400 in WithBaseline.py)
- Manages video playback and audio extraction for a single participant
- Uses FFmpeg to extract audio to temporary WAV files
- Routes audio to specific device via sounddevice
- Pyglet handles video rendering with muted player
- Threading: Audio plays in separate thread, video in main Pyglet loop

**`CrossDisplay`** (lines 402-434)
- Renders white fixation cross on fullscreen window
- Dynamically sized based on window dimensions
- Toggled via `.active` flag during phase transitions

**Global Input Listener** (lines 48-79)
- Hidden Pyglet window captures all keyboard input
- Simultaneous dual-participant rating collection
- Keys: 1-7 (P1), Q-U (P2) for 7-point ratings
- Sends LSL markers with encoded pair index and rating value

### Execution Flow

```
main()
  → show_welcome_screen()           # Headset selection, instructions
  → display_cross_for_duration()    # 240s baseline with LSL markers
  → play_video_pairs_consecutively()
      → play_next_pair() [loop]
          → run_video_audio_sync()  # 3s cross → video → handle_playback_end()
          → create_rating_screen()  # Dual ratings, save to CSV
          → play_next_pair()        # Recurse until all pairs complete
  → exit_program()
```

### Threading Model
- **Main thread**: Pyglet event loop (video rendering, GUI events)
- **Audio threads**: One per participant, started synchronously with video
- **Preparation threads**: Parallel video/audio loading before each trial
- **ESC listener**: Daemon thread monitoring for emergency exit

### Phase Management
Global `phase` variable tracks current state: `"welcome"` | `"baseline"` | `"videos"`

Window `on_draw()` handlers check phase to determine what to render (welcome text, fixation cross, or video texture).

## LSL Marker Scheme

**Important**: This code sends LSL markers via `outlet.push_sample()` but does **not** record them. External software (LabRecorder) captures both the EEG streams and these event markers for offline synchronization.

From `CodeBook.txt`:

| Marker | Description |
|--------|-------------|
| 9161 | Participant 1 assigned headset B16 |
| 9162 | Participant 1 assigned other headset |
| 8888 | Baseline fixation cross start |
| 9999 | Baseline fixation cross end |
| 100# | Trial # video playback start (both participants) |
| 210# | Trial # video end for Participant 1 |
| 220# | Trial # video end for Participant 2 |
| 300#0$ | P1 rating: trial #, rating $ (1-7) |
| 500#0$ | P2 rating: trial #, rating $ (1-7) |

**Example**: Marker `300507` = Participant 1, Trial 5, Rating 7

## Video Pair CSV Format

Required columns:
- `VideoPath1` - Full path to Participant 1's video
- `VideoPath2` - Full path to Participant 2's video

Multiple CSV variants exist for different testing scenarios:
- `video_pairs_extended.csv` - Full experiment (default)
- `video_pairs_simple.csv` - Reduced set
- `video_pairs-quick.csv` - Quick testing

## Key Implementation Details

### Audio/Video Synchronization

**New Architecture (core/execution with SyncEngine):**
- **Timestamp-based synchronization**: All players start at the exact same timestamp
- **Hybrid sleep approach**: OS sleep + busy-wait for <5ms precision
- **Automatic verification**: Drift and spread logged every trial
- **No manual configuration**: SyncEngine auto-coordinates timing
- **Performance targets**: <5ms audio-video sync, <2ms inter-player sync

**Implementation:**
```python
from playback.sync_engine import SyncEngine

# Synchronize multiple players automatically
sync_result = SyncEngine.play_synchronized([player1, player2])
# Achieves <5ms precision without manual offset configuration
```

**Legacy Approach (WithBaseline.py - DEPRECATED):**
- Manual offset (`audio_offset_ms = 350`) compensated for processing delays
- Used blocking `time.sleep()` with unpredictable latency
- No verification of actual sync quality
- Required per-system calibration

**Common Components (both architectures):**
- Audio extracted via FFmpeg to handle diverse codecs (H.264, VP9, etc.)
- Pyglet for video playback, sounddevice for audio routing
- Separate audio streams per participant

### Dual Completion Detection
Each video uses two mechanisms to detect playback end:
1. **EOS handlers**: Pyglet's `on_eos` event (preferred)
2. **Timed fallback**: `pyglet.clock.schedule_once()` at video duration + 0.1s

Both videos must complete before transitioning to rating screen (`completed_videos == 2`).

### Data Output from This Code

**This code only saves behavioral data**, not EEG. Output file: `experiment_data.csv`

Columns:
- Participant (P1/P2)
- Rating (1-7)
- VideoPair (trial index)
- Video1, Video2 (file paths)
- Timestamp

**Note**: Filename is currently hardcoded; should be enhanced with subject ID and session timestamp.

EEG data and LSL markers are recorded by LabRecorder (external software) in separate XDF files.

### Multi-Screen Management
- Requires exactly 3 screens (control + 2 participant displays)
- `pyglet.canvas.get_display().get_screens()` enumerates available screens
- Fullscreen windows created on `screens[1]` and `screens[2]`
- Exclusive keyboard disabled to allow global input listener

## Common Issues & Solutions

**Audio device mismatch**: Run `utilities/audioscan.py` to get current device indices, update lines 21-22 in `WithBaseline.py`

**Video won't load**: Use `utilities/videotester.py` to check codec compatibility. Convert problematic videos with `utilities/video_converter.py`

**Screen not detected**: Verify 3 displays connected. Check display settings in OS. Pyglet may cache screen configuration (restart Python).

**LSL streams not appearing**: Ensure Emotiv software is running with LSL enabled before starting LabRecorder. Check that LSL WebSocket is connected.

**Ratings not captured**: Verify global input listener window is created (lines 41, 46). Check that participant response flags (`p1_responded`, `p2_responded`) are reset in `create_rating_screen()`.

## Code Modification Guidelines

When modifying this codebase:

1. **Preserve LSL marker scheme** - External analysis pipelines depend on the marker numbering system
2. **Test with quick CSV first** - Use `video_pairs-quick.csv` for rapid iteration
3. **Maintain dual-participant symmetry** - All displays, audio, and markers must remain balanced
4. **Handle threading carefully** - Audio threads must join before cleanup; use proper Event signaling
5. **Validate phase transitions** - Global `phase` variable must update correctly for `on_draw()` handlers
6. **Test escape behavior** - ESC key must safely exit from any phase without hanging

## Related Documentation

- `code_analysis.md` - Detailed code structure analysis
- `gui_style_analysis.md` - GUI implementation patterns
- `psychopy_research.md` - PsychoPy framework research notes
- `Exp Setup Instructions.txt` - Complete experimental setup checklist
- `CodeBook.txt` - LSL marker definitions
- you should use the VideoEEG conda environment for this package
- the required conda environement is here: /mnt/c/Users/canoz/Anaconda3/envs/VideoEEG/python.exe
- the required conda environement is here: /mnt/c/Users/canoz/Anaconda3/envs/VideoEEG/python.exe