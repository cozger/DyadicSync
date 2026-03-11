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

**Technology Stack**: Python 3.11, PsychoPy 2023.1.3, Pyglet 2.1+, LSL (pylsl), FFmpeg, sounddevice, pandas

## Running the Experiment

### Recommended Method (Auto-activates correct environment)
```bash
# Timeline Editor (new architecture - RECOMMENDED)
launch_editor.bat

# Legacy experiment script
launch_experiment.bat
```

### Manual Method (Requires environment activation)
```bash
# Activate sync environment first
conda activate sync

# Then run:
python launch_timeline_editor.py  # Timeline Editor
# OR
python WithBaseline.py  # Legacy script
```

**IMPORTANT**: See "Python Environment Setup" section below for why the `sync` environment is required.

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
- **Turn-Taking Support**: Per-participant display modes (video/instruction/blank)

**`RatingPhase`** (`core/execution/phases/rating_phase.py`)
- Collects ratings from both participants simultaneously
- Supports per-participant questions for turn-taking conditions
- **Turn-Taking Support**: Different questions for viewer vs observer roles

### Turn-Taking Conditions (New Feature)

The system supports three viewing conditions that can be mixed within a single block:

**Conditions:**
1. **Joint** (default): Both participants watch videos simultaneously and rate with same question
2. **P1 Viewer**: P1 watches video with audio, P2 sees instruction text ("observe" role)
3. **P2 Viewer**: P2 watches video with audio, P1 sees instruction text ("observe" role)

**CSV Format for Turn-Taking:**
```csv
VideoPath1,VideoPath2,condition,viewer
C:\...\video1.mp4,C:\...\video1.mp4,turn_taking,1
C:\...\video2.mp4,C:\...\video2.mp4,turn_taking,2
C:\...\video3.mp4,C:\...\video3.mp4,joint,
```

- `condition`: `turn_taking` | `joint`
- `viewer`: `1` | `2` | empty (empty for joint, or auto-assigned with balanced randomization)

**Automatic Viewer Assignment:**
When `viewer` column is empty for `turn_taking` trials, the system automatically assigns viewers with balanced randomization (~50/50 P1 vs P2).

**Timeline Editor Configuration:**
1. **VideoPhase**: Set `participant_X_mode` to "video", "instruction", or "blank"
2. **RatingPhase**: Set optional `participant_X_question` for role-specific prompts
   - Viewer: "How did the video make you feel?" (self-report)
   - Observer: "How do you think they felt?" (empathic inference)

**Template Variables (from CSV):**
- `{p1_mode}`, `{p2_mode}` - Display mode per participant
- `{role_p1}`, `{role_p2}` - Role assignment ("viewer", "observer", "joint")
- `{viewer}` - Viewer participant number (1 or 2)
- `{condition}` - Trial condition ("turn_taking" or "joint")

**Data Output:**
CSV output includes additional columns:
- `Condition`: "turn_taking" | "joint"
- `Role`: "viewer" | "observer" | "joint"
- `Viewer`: 1 | 2 | null

**LSL Markers for Turn-Taking:**
| Marker | Description |
|--------|-------------|
| 110# | Turn-taking trial # start (P1 viewer) |
| 120# | Turn-taking trial # start (P2 viewer) |
| 310#0$ | P1 viewer self-report rating |
| 410#0$ | P1 observer rating |
| 520#0$ | P2 viewer self-report rating |
| 620#0$ | P2 observer rating |

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

## LabRecorder Auto-Start (New Architecture)

The new architecture (`core/execution`) supports automatic LabRecorder control via Remote Control Socket (RCS). This allows the experiment to automatically start/stop LSL recording without manual intervention.

### Setup Instructions

1. **Start all LSL streaming programs FIRST**:
   - Launch Emotiv software with LSL streaming enabled (for both EEG headsets)
   - Launch any other LSL streams (face synchrony, video capture, etc.)
   - Verify all streams are active using LSL LabRecorder stream list

2. **Launch LabRecorder**:
   - Start LabRecorder application
   - Enable "Remote Control Socket (RCS)" in LabRecorder settings
   - Default port: 22345 (can be configured)
   - Leave LabRecorder running in the background

3. **Configure DyadicSync**:
   - Open Timeline Editor
   - Go to `Experiment > Settings`
   - In "LabRecorder Auto-Start" section:
     - ✓ Enable "Enable LabRecorder auto-start"
     - Set "RCS Host" (default: `localhost`)
     - Set "RCS Port" (default: `22345`)
     - Click "Test Connection" to verify LabRecorder is reachable
   - Save settings

4. **Run Experiment**:
   - When you click "Run Experiment", DyadicSync will:
     - Automatically connect to LabRecorder
     - Select ALL available LSL streams (no filtering)
     - Start recording with filename: `sub-{ID:03d}_ses-{#:02d}_{task}.xdf`
     - Stop recording when experiment completes or is aborted

### Features

**Automatic Stream Selection**:
- Auto-start captures **ALL** available LSL streams on the network
- No filtering by stream type or name
- Ensures complete multi-modal data capture (EEG, Markers, face synchrony, video, etc.)

**Synchronized Filenames**:
- XDF file uses same naming convention as behavioral CSV
- Example: `sub-001_ses-01_DyadicVideoSync.xdf`
- Both files stored in same output directory (configured in Experiment Settings)

**Graceful Fallback**:
- If LabRecorder connection fails, experiment continues without LSL recording
- Warning displayed in execution dialog: "⚠️ LabRecorder: Connection failed (continuing without)"
- Manual recording with LabRecorder GUI still works as backup

**Test Mode Support**:
- When `subject_id = 0` or `session = 0`, auto-start is skipped
- Matches existing behavior: no CSV saved, no XDF recording
- Useful for testing experiment flow without generating data files

### Status Indicators

During experiment execution, the progress dialog shows LabRecorder status:
- "🔴 LabRecorder: Recording all streams" (green) - Recording active
- "⚠️ LabRecorder: Connection failed" (orange) - Failed to connect, experiment continuing
- "⏹ LabRecorder: Stopped" (gray) - Recording stopped after completion

### Implementation Details

**Architecture**:
- `core/labrecorder_control.py` - LabRecorderController class for RCS communication
- `timeline_editor/dialogs/execution_dialog.py` - Start/stop control integrated into execution flow
- `core/ipc/serialization.py` - LabRecorder settings passed to subprocess via ExperimentConfig

**Remote Control Protocol**:
- TCP socket connection to LabRecorder RCS (default: `localhost:22345`)
- Commands used:
  - `select all` - Select all available LSL streams
  - `filename {root:...} {participant:...} {session:...} {task:...}` - Configure output filename
  - `start` - Start recording
  - `stop` - Stop recording

**Timing**:
- LabRecorder starts BEFORE experiment subprocess launches
- Ensures headset selection marker (9161/9162) is captured
- Recording stops AFTER experiment completes
- Captures all markers including completion events

### Troubleshooting

**"Connection failed" error**:
1. Verify LabRecorder is running
2. Check "Remote Control Socket" is enabled in LabRecorder settings
3. Verify host/port settings match LabRecorder configuration
4. Use "Test Connection" button in Experiment Settings to diagnose

**No streams recorded**:
1. Verify LSL streaming programs are running BEFORE starting LabRecorder
2. Check LabRecorder stream list shows all expected streams
3. Ensure streams are active (green indicators in LabRecorder)

**Partial data capture**:
- If experiment aborts or crashes, LabRecorder may still have partial recording
- XDF file will contain all markers up to abort point
- This is normal behavior - partial data is saved

**Manual override**:
- Auto-start can be disabled in Experiment Settings
- LabRecorder can be controlled manually via GUI as before
- Both approaches work simultaneously (auto-start + manual control compatible)

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

### Exit Code 3221225477 (0xC0000005 - Access Violation) ⚠️ MOST COMMON

**Symptoms**: Experiment crashes immediately or during video playback with exit code 3221225477 (hexadecimal 0xC0000005)

**Root Cause (99% of cases)**: Wrong Python environment - running with base environment instead of `sync` environment

**Why This Happens**:
- Base Python environment (3.13.x) does NOT have required dependencies (pyglet, sounddevice, pylsl, pandas, ffmpeg-python)
- When experiment subprocess tries to `import pyglet`, it fails immediately with Access Violation
- This is the #1 issue for new installations

**SOLUTION** (in order of ease):

1. **Use launcher scripts** (EASIEST):
   - Double-click `launch_editor.bat` for Timeline Editor
   - Double-click `launch_experiment.bat` for legacy WithBaseline.py
   - Scripts automatically activate the correct environment

2. **Activate environment manually**:
   ```bash
   conda activate sync
   python launch_timeline_editor.py
   ```

3. **Verify environment** (if still having issues):
   ```bash
   conda activate sync
   python test_environment.py
   ```
   Should show all dependencies available

**How to Confirm This Is Your Issue**:
- Check which Python is running: `python --version`
- If you see `3.13.x` → Wrong environment (should be `3.11.0`)
- Try importing pyglet: `python -c "import pyglet"`
- If ModuleNotFoundError → Confirmed wrong environment

**Secondary Causes** (rare, only if sync environment is active):
- Missing dependencies in sync environment → Run `pip install -r requirements.txt` in sync environment
- FFmpeg DLL issues → See FFmpeg troubleshooting below

---

### Audio/Video Synchronization Crashes (New Architecture)

The new execution architecture (`core/execution`) encountered and resolved **4 critical crashes** during development related to threading, sounddevice/PortAudio, and OpenGL resource management.

**If you encounter these exit codes:**
- **3221225501 (0xC0000141)** - DLL_INIT_FAILED: Daemon threads issue
- **3221225622 (0xC0000096)** - PRIVILEGED_INSTRUCTION: Invalid API usage
- **3221225477 (0xC0000005)** - ACCESS_VIOLATION: Premature cleanup
- **3221226356 (0xC0000374)** - HEAP_CORRUPTION: Global operation coordination

**Solution:** Consult `docs/AUDIO_VIDEO_SYNC_FIXES.md` for detailed diagnosis and fixes.

**All crashes have been resolved** in the current codebase. The document provides:
- Root cause analysis for each crash
- Code references (file:line) for fixes
- Best practices for audio/video synchronization
- Testing checklist

---

**Audio device mismatch**: Run `utilities/audioscan.py` to get current device indices, update lines 21-22 in `WithBaseline.py`

**Video won't load / "No decoders available"**:
- **First**: Verify FFmpeg is detected: `python config/ffmpeg_config.py`
- **Local FFmpeg** (automatic): Project uses `DyadicSync/ffmpeg/bin/ffmpeg.exe` automatically if present
- **System FFmpeg** (fallback): Falls back to system PATH if local not found
- **Fix**: Ensure you have FFmpeg **shared** build (not "essentials") in `ffmpeg/bin/` directory
- See `FFMPEG_SETUP.md` for installation details
- Use `utilities/videotester.py` to check codec compatibility
- Convert problematic videos with `utilities/video_converter.py`

**Screen not detected**: Verify 3 displays connected. Check display settings in OS. Pyglet may cache screen configuration (restart Python).

**LSL streams not appearing**: Ensure Emotiv software is running with LSL enabled before starting LabRecorder. Check that LSL WebSocket is connected.

**LabRecorder auto-start not working**: See "LabRecorder Auto-Start" section above for detailed troubleshooting. Most common: RCS not enabled in LabRecorder, or wrong host/port configuration. Use "Test Connection" button in Experiment Settings to diagnose.

**Ratings not captured**: Verify global input listener window is created (lines 41, 46). Check that participant response flags (`p1_responded`, `p2_responded`) are reset in `create_rating_screen()`.

## Code Principles

Always follow **DRY**, **KISS**, and **SOLID** principles when writing or modifying code.

## Code Modification Guidelines

When modifying this codebase:

1. **Preserve LSL marker scheme** - External analysis pipelines depend on the marker numbering system
2. **Test with quick CSV first** - Use `video_pairs-quick.csv` for rapid iteration
3. **Maintain dual-participant symmetry** - All displays, audio, and markers must remain balanced
4. **Handle threading carefully** - Audio threads must join before cleanup; use proper Event signaling
5. **Validate phase transitions** - Global `phase` variable must update correctly for `on_draw()` handlers
6. **Test escape behavior** - ESC key must safely exit from any phase without hanging

## Related Documentation

- `docs/AUDIO_VIDEO_SYNC_FIXES.md` - **Audio/video synchronization crash fixes** (4 major crashes resolved)
- `code_analysis.md` - Detailed code structure analysis
- `gui_style_analysis.md` - GUI implementation patterns
- `psychopy_research.md` - PsychoPy framework research notes
- `Exp Setup Instructions.txt` - Complete experimental setup checklist
- `CodeBook.txt` - LSL marker definitions

## Python Environment Setup

**CRITICAL**: This project requires the `sync` conda environment with Python 3.11.0

**Environment Location**: `C:\Users\synchrony\miniconda3\envs\sync`

**Required Activation**: Before running ANY DyadicSync code, activate the environment:
```bash
conda activate sync
```

**Why This Matters**: The base Python environment (3.13.9) does NOT have required dependencies (pyglet, sounddevice, pylsl, pandas, ffmpeg-python). Running without the sync environment will cause **exit code 3221225477 (Access Violation)**.

**Easy Launch**: Use the provided batch scripts that auto-activate the environment:
- `launch_editor.bat` - Launch Timeline Editor with sync environment
- `launch_experiment.bat` - Launch legacy WithBaseline.py with sync environment

**Environment Validation**: The launcher scripts check for sync environment and display helpful error messages if not found.