# DyadicSync Framework: Comprehensive Architecture & Roadmap

**Project:** Modular Dyadic Experiment Framework
**Version:** 2.0
**Date:** 2025-11-15
**Status:** Architecture Design Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Current State Analysis](#current-state-analysis)
3. [Core Architecture](#core-architecture)
4. [Synchronization System](#synchronization-system)
5. [Procedure-List Model (E-Prime Style)](#procedure-list-model)
6. [Class Specifications](#class-specifications)
7. [GUI Design](#gui-design)
8. [File Formats](#file-formats)
9. [Implementation Roadmap](#implementation-roadmap)
10. [Testing Strategy](#testing-strategy)
11. [Migration Guide](#migration-guide)
12. [Future Extensions](#future-extensions)

---

## Executive Summary

### Project Goals

Transform the current hardcoded `WithBaseline.py` script into a modular, GUI-driven experiment framework that:

1. **Eliminates manual synchronization offsets** through timestamp-based sync
2. **Provides E-Prime-style procedure/list separation** for trial design
3. **Enables GUI-based experiment design** without code editing
4. **Supports trial randomization** with constraints
5. **Maintains hybrid playback** (Pyglet video + sounddevice audio) - no external dependencies
6. **Saves/loads experiments** as configuration files
7. **Scales to complex experimental designs** through modular architecture

### Key Design Decisions

| Aspect | Decision | Rationale |
|--------|----------|-----------|
| **Audio/Video Sync** | Timestamp-based synchronization | Eliminates 350ms manual offset, programmatic precision |
| **Playback Method** | Hybrid (Pyglet + sounddevice) | No external dependencies, explicit device control |
| **Trial Design** | Procedure/List separation | Follows E-Prime model, separates structure from data |
| **GUI Framework** | Tkinter | Built-in, no dependencies, cross-platform |
| **Config Format** | JSON | Human-readable, easy to edit, Python native |
| **Architecture** | Modular class-based OOP | Separation of concerns, testable, extensible |

---

## Current State Analysis

### WithBaseline.py - Strengths

✅ **Working multi-participant setup** (2 participants, 2 screens, 2 audio devices)
✅ **LSL integration** for precise event marking
✅ **CSV-based stimulus loading** (video_pairs_extended.csv)
✅ **Rating collection** with keyboard input from both participants
✅ **Threading** for concurrent audio playback

### WithBaseline.py - Limitations

❌ **Hardcoded configuration** (device indices, durations, markers)
❌ **Manual synchronization offset** (350ms audio_offset_ms)
❌ **Monolithic structure** (900 lines, hard to maintain)
❌ **No randomization** (videos play in CSV order)
❌ **No experiment reusability** (must edit code for new experiments)
❌ **Limited error handling** (crashes on file not found, device errors)
❌ **No trial constraints** (can't prevent repeating categories)

### Critical Code Sections

```python
# Line 38: Manual offset (TO BE ELIMINATED)
audio_offset_ms = 350

# Lines 366-379: Audio playback (NO SYNC)
def play_audio(self):
    sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
    sd.wait()

# Lines 642-683: Sequential start with manual delay
if audio_offset_ms > 0:
    audio_thread1.start()
    audio_thread2.start()
    time.sleep(video_delay)  # Manual offset!
    player1.player.play()
    player2.player.play()

# Lines 84-103: CSV loading (NO RANDOMIZATION)
video_pairs = load_video_pairs_from_csv(csv_path)
# Plays in order, no shuffling, no constraints
```

---

## Core Architecture

### Design Principles

1. **Separation of Concerns**: Each class has a single, well-defined responsibility
2. **Dependency Injection**: Pass dependencies explicitly (device_manager, lsl_outlet)
3. **Configuration over Code**: Experiments defined in JSON, not Python
4. **Fail-Safe Defaults**: Sensible defaults, extensive validation
5. **Event-Driven**: Phases communicate via events/callbacks
6. **Stateless Where Possible**: Minimize shared mutable state

### Component Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                        Experiment                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                      Timeline                            │  │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │  │
│  │  │  Block 1   │  │  Block 2   │  │  Block 3   │  ...   │  │
│  │  │ (Baseline) │  │ (Videos)   │  │ (Ratings)  │        │  │
│  │  └────────────┘  └────────────┘  └────────────┘        │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                │
│  Device Manager          LSL Outlet         Data Collector    │
│  ┌──────────────┐       ┌──────────┐       ┌──────────┐      │
│  │ Displays     │       │ Markers  │       │ Ratings  │      │
│  │ Audio Devs   │       │ Events   │       │ RTs      │      │
│  └──────────────┘       └──────────┘       └──────────┘      │
└────────────────────────────────────────────────────────────────┘
```

### Block Execution Model

```
Block
├── Procedure (template: what happens each trial)
│   ├── Fixation Phase (3 seconds)
│   ├── Video Phase (variable duration)
│   └── Rating Phase (wait for both responses)
│
├── Trial List (data: which stimuli, what order)
│   ├── Trial 1: video1=happy_01.mp4, video2=happy_02.mp4, emotion=happy
│   ├── Trial 2: video1=sad_03.mp4, video2=sad_04.mp4, emotion=sad
│   └── ... (N trials)
│
└── Execution
    For each trial in (randomized) trial list:
        Execute procedure with trial data
        Collect responses
        Save data
```

---

## Synchronization System

### Problem Analysis

**Current approach:**
```python
# Start audio first
audio_thread1.start()  # T=0.000s (immediate)
audio_thread2.start()  # T=0.000s (immediate)
time.sleep(0.350)      # T=0.350s (blocking sleep)
player1.player.play()  # T=0.350s + pyglet latency (~10-50ms)
player2.player.play()  # T=0.350s + pyglet latency (~10-50ms)
```

**Issues:**
- Manual offset is hardcoded, not calibrated
- Pyglet latency varies (event loop timing)
- No verification that sync actually happened
- No compensation for audio buffer latency

### Timestamp-Based Solution

**Core concept:** All playback starts at a pre-calculated future timestamp.

```python
# Calculate shared start time (100ms in future for thread setup)
sync_timestamp = time.perf_counter() + 0.100

# All threads wait until sync_timestamp, then start
audio_thread1 = Thread(target=play_audio_at_timestamp, args=(sync_timestamp,))
audio_thread2 = Thread(target=play_audio_at_timestamp, args=(sync_timestamp,))
video_thread1 = Thread(target=play_video_at_timestamp, args=(sync_timestamp,))
video_thread2 = Thread(target=play_video_at_timestamp, args=(sync_timestamp,))

# Threads start immediately (but wait internally)
audio_thread1.start()
audio_thread2.start()
video_thread1.start()
video_thread2.start()
```

### SyncEngine Implementation

```python
class SyncEngine:
    """
    Centralized synchronization engine using high-resolution timestamps.

    Design:
    - Uses time.perf_counter() for sub-millisecond precision
    - Busy-wait in final 5ms for precise timing (avoids sleep drift)
    - Logs actual start times for verification
    - Compensates for known device latencies
    """

    @staticmethod
    def calculate_sync_timestamp(prep_time_ms=100):
        """
        Calculate future timestamp for synchronized start.

        Args:
            prep_time_ms: Milliseconds to allow for thread initialization

        Returns:
            float: time.perf_counter() value for synchronized start
        """
        return time.perf_counter() + (prep_time_ms / 1000.0)

    @staticmethod
    def wait_until_timestamp(target_timestamp):
        """
        Wait until precise timestamp (with hybrid sleep + busy-wait).

        Args:
            target_timestamp: time.perf_counter() value to wait for

        Implementation:
        - Sleep until 5ms before target (CPU-friendly)
        - Busy-wait final 5ms (precise timing)
        """
        remaining = target_timestamp - time.perf_counter()

        # Sleep until close to target (avoid CPU spin)
        if remaining > 0.005:  # More than 5ms away
            time.sleep(remaining - 0.005)

        # Busy-wait for final precision
        while time.perf_counter() < target_timestamp:
            pass  # Spin-wait

    @staticmethod
    def play_synchronized(players, prep_time_ms=100):
        """
        Start multiple players at precisely the same timestamp.

        Args:
            players: List of objects with play_at_timestamp(t) method
            prep_time_ms: Time to allow for thread initialization

        Returns:
            dict: Actual start times for each player (for verification)
        """
        sync_timestamp = SyncEngine.calculate_sync_timestamp(prep_time_ms)

        # Start all players in parallel threads
        threads = []
        actual_starts = {}

        for i, player in enumerate(players):
            def player_wrapper(player_obj, player_id):
                actual_start = player_obj.play_at_timestamp(sync_timestamp)
                actual_starts[player_id] = actual_start

            thread = threading.Thread(
                target=player_wrapper,
                args=(player, f"player_{i}")
            )
            threads.append(thread)
            thread.start()

        # Wait for all to complete initialization
        for thread in threads:
            thread.join()

        # Verify synchronization (log differences)
        SyncEngine._verify_sync(actual_starts, sync_timestamp)

        return actual_starts

    @staticmethod
    def _verify_sync(actual_starts, target_timestamp):
        """
        Log synchronization quality.

        Logs:
        - Target timestamp
        - Actual start time for each player
        - Difference from target (should be <5ms)
        - Inter-player differences (should be <2ms)
        """
        if not actual_starts:
            return

        starts = list(actual_starts.values())
        diffs_from_target = [(s - target_timestamp) * 1000 for s in starts]

        print(f"[SYNC] Target timestamp: {target_timestamp:.6f}")
        for player_id, start_time in actual_starts.items():
            diff_ms = (start_time - target_timestamp) * 1000
            print(f"[SYNC] {player_id}: {start_time:.6f} (Δ {diff_ms:+.2f}ms)")

        # Check quality
        max_diff = max(abs(d) for d in diffs_from_target)
        spread = max(starts) - min(starts)

        print(f"[SYNC] Max drift from target: {max_diff:.2f}ms")
        print(f"[SYNC] Inter-player spread: {spread * 1000:.2f}ms")

        if max_diff > 10:
            print(f"[SYNC] WARNING: High drift detected (>{max_diff:.2f}ms)")
        if spread * 1000 > 5:
            print(f"[SYNC] WARNING: High inter-player spread ({spread * 1000:.2f}ms)")
```

### SynchronizedPlayer Modifications

```python
class SynchronizedPlayer:
    """
    Enhanced player with timestamp-based synchronization.
    """

    def __init__(self, video_path, audio_device_index, window):
        self.video_path = video_path
        self.audio_device_index = audio_device_index
        self.window = window
        self.player = None  # Pyglet player
        self.audio_data = None
        self.samplerate = None
        self.ready = threading.Event()

    def prepare(self):
        """
        Load video and extract audio (unchanged from current).
        """
        # ... (same as current implementation)
        # Extract audio via ffmpeg, load with soundfile
        # Create pyglet player, mute it, queue video
        pass

    def play_at_timestamp(self, sync_timestamp):
        """
        Start both video and audio at precise timestamp.

        Args:
            sync_timestamp: time.perf_counter() value to start at

        Returns:
            float: Actual start time (for verification)
        """
        # Wait until sync timestamp
        SyncEngine.wait_until_timestamp(sync_timestamp)

        # Start video (Pyglet)
        actual_video_start = time.perf_counter()
        self.player.play()

        # Start audio (sounddevice) - should be within microseconds
        actual_audio_start = time.perf_counter()
        sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)

        # Log for diagnostics
        video_delay = (actual_video_start - sync_timestamp) * 1000
        audio_delay = (actual_audio_start - sync_timestamp) * 1000
        av_diff = (actual_audio_start - actual_video_start) * 1000

        print(f"[Player {self.audio_device_index}] Video: +{video_delay:.2f}ms, Audio: +{audio_delay:.2f}ms, A-V: {av_diff:.2f}ms")

        return actual_video_start

    def wait_until_finished(self):
        """
        Block until audio completes (video will auto-stop).
        """
        sd.wait()  # Wait for audio to finish
```

### Expected Synchronization Quality

| Metric | Current (Manual Offset) | Target (Timestamp Sync) |
|--------|-------------------------|-------------------------|
| **Audio-Video Sync** | ±50ms (unverified) | <5ms |
| **Inter-Player Sync** | Unknown | <2ms |
| **Drift Over Time** | Possible (independent clocks) | Minimal (shared clock) |
| **Verification** | None | Logged every trial |

---

## Procedure-List Model

### Conceptual Overview

Separates **structure** (procedure) from **data** (trial list), enabling:
- Reusable experimental templates
- Easy stimulus randomization
- Trial-level metadata (emotion category, expected response, etc.)
- Constraints (e.g., no more than 2 consecutive happy videos)

### E-Prime Analogy

| E-Prime Component | DyadicSync Equivalent | Description |
|-------------------|----------------------|-------------|
| **Procedure** | `Procedure` class | Template: Fixation → Stimulus → Response |
| **List** | `TrialList` class | CSV with trial data (VideoPath1, VideoPath2, etc.) |
| **Trial** | `Trial` instance | One execution: specific videos + collected data |
| **Block** | `Block` class | Group of trials with shared procedure + list |
| **SessionProc** | `Timeline` class | Sequence of blocks |

### Example Experiment Structure

```
Experiment: "Emotional Contagion Study"
│
├── Block 1: "Baseline"
│   └── Procedure: FixationPhase(duration=240s)
│
├── Block 2: "Video Trials"
│   ├── Procedure:
│   │   ├── FixationPhase(duration=3s)
│   │   ├── VideoPhase(participant_1_video="{video1}", participant_2_video="{video2}")
│   │   └── RatingPhase(question="How did this make you feel?", scale=1-7)
│   │
│   └── Trial List (CSV):
│       trial_id, video1,              video2,              emotion, valence
│       1,        videos/happy_01.mp4, videos/happy_02.mp4, happy,   positive
│       2,        videos/sad_01.mp4,   videos/sad_02.mp4,   sad,     negative
│       3,        videos/neutral.mp4,  videos/neutral.mp4,  neutral, neutral
│       ...
│
└── Block 3: "Post-Baseline"
    └── Procedure: FixationPhase(duration=120s)
```

### Procedure Template Variables

Procedures can reference trial list columns using `{column_name}` syntax:

```python
# In procedure definition (JSON):
{
    "type": "VideoPhase",
    "participant_1_video": "{video1}",  # References trial list column
    "participant_2_video": "{video2}",  # References trial list column
    "duration": "auto"  # Inferred from video
}

# At runtime, Trial populates these:
trial.data = {"video1": "videos/happy_01.mp4", "video2": "videos/happy_02.mp4"}
phase.render(trial.data)  # Replaces {video1} and {video2}
```

### Randomization Options

```python
class RandomizationConfig:
    """
    Configuration for trial list randomization.
    """
    method: str  # 'none', 'full', 'block', 'latin_square'
    seed: int  # Random seed for reproducibility
    constraints: List[Constraint]  # Ordering constraints

    # Example constraints:
    # - MaxConsecutiveAttribute('emotion', 'happy', 2)
    #   → No more than 2 happy videos in a row
    # - BalanceAttribute('emotion', ['happy', 'sad', 'neutral'])
    #   → Equal counts of each emotion
    # - NoRepeatAttribute('video1', within_trials=3)
    #   → Same video1 can't appear within 3 trials
```

**Supported Methods:**

1. **None**: Use CSV order (current behavior)
2. **Full Shuffle**: Complete randomization (random.shuffle)
3. **Block Randomization**: Shuffle within groups (e.g., 4 happy + 4 sad = 8 trial block, shuffle within)
4. **Latin Square**: Counterbalanced ordering (useful for N participants)
5. **Constrained Random**: Shuffle with constraint checking (reject if violated, reshuffle)

**Implementation:**

```python
def randomize_trial_list(trial_list, config):
    """
    Randomize trial list according to configuration.

    Args:
        trial_list: List of trial dictionaries
        config: RandomizationConfig object

    Returns:
        List of trial dictionaries in randomized order
    """
    if config.method == 'none':
        return trial_list

    random.seed(config.seed)

    if config.method == 'full':
        randomized = trial_list.copy()
        random.shuffle(randomized)

    elif config.method == 'constrained':
        # Shuffle and check constraints
        max_attempts = 1000
        for attempt in range(max_attempts):
            randomized = trial_list.copy()
            random.shuffle(randomized)

            # Check all constraints
            if all(c.check(randomized) for c in config.constraints):
                break
        else:
            raise ValueError(f"Could not satisfy constraints after {max_attempts} attempts")

    # ... other methods

    return randomized
```

---

## Class Specifications

### 1. Experiment Class

```python
class Experiment:
    """
    Top-level experiment orchestrator.

    Responsibilities:
    - Manage timeline of blocks
    - Initialize devices and LSL
    - Coordinate data collection
    - Handle global experiment events (pause, abort)

    Lifecycle:
    1. __init__: Load configuration
    2. validate: Check all resources exist
    3. run: Execute timeline
    4. save_data: Write collected data to disk
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize experiment from configuration file.

        Args:
            config_path: Path to JSON config, or None for empty experiment
        """
        self.name: str = ""
        self.description: str = ""
        self.version: str = "1.0"

        # Core components
        self.timeline: Timeline = Timeline()
        self.device_manager: DeviceManager = DeviceManager()
        self.lsl_outlet: Optional[StreamOutlet] = None
        self.data_collector: DataCollector = DataCollector()

        # Runtime state
        self.current_block_index: int = 0
        self.paused: threading.Event = threading.Event()
        self.aborted: threading.Event = threading.Event()

        # Load from file if provided
        if config_path:
            self.load(config_path)

    def validate(self) -> List[str]:
        """
        Validate experiment configuration.

        Returns:
            List of error messages (empty if valid)

        Checks:
        - All video files exist
        - All audio devices available
        - All displays available
        - Procedures reference valid trial list columns
        - LSL stream name is unique
        """
        errors = []

        # Validate timeline
        errors.extend(self.timeline.validate())

        # Validate devices
        errors.extend(self.device_manager.validate())

        # Validate LSL (check for name conflicts)
        if self.lsl_outlet:
            # ... check LSL stream availability
            pass

        return errors

    def run(self):
        """
        Execute the experiment timeline.

        Flow:
        1. Setup devices
        2. Initialize LSL
        3. For each block in timeline:
            a. Execute block
            b. Check for pause/abort
            c. Save intermediate data
        4. Cleanup and final save
        """
        try:
            # Setup
            self.device_manager.initialize()
            self.lsl_outlet = self._initialize_lsl()

            # Execute timeline
            for block in self.timeline.blocks:
                if self.aborted.is_set():
                    break

                block.execute(
                    device_manager=self.device_manager,
                    lsl_outlet=self.lsl_outlet,
                    data_collector=self.data_collector
                )

                # Handle pause
                while self.paused.is_set():
                    time.sleep(0.1)

        finally:
            # Cleanup
            self.device_manager.cleanup()
            self.data_collector.save_all()

    def pause(self):
        """Pause experiment between blocks."""
        self.paused.set()

    def resume(self):
        """Resume paused experiment."""
        self.paused.clear()

    def abort(self):
        """Abort experiment (save partial data)."""
        self.aborted.set()

    def save(self, filepath: str):
        """
        Save experiment configuration to JSON.

        Args:
            filepath: Path to save JSON file
        """
        from io.experiment_serializer import ExperimentSerializer
        ExperimentSerializer.save(self, filepath)

    def load(self, filepath: str):
        """
        Load experiment configuration from JSON.

        Args:
            filepath: Path to JSON config file
        """
        from io.experiment_serializer import ExperimentSerializer
        ExperimentSerializer.load(self, filepath)

    def _initialize_lsl(self) -> StreamOutlet:
        """Initialize LSL stream for markers."""
        info = StreamInfo(
            name='ExpEvent_Markers',
            type='Markers',
            channel_count=1,
            channel_format='int32',
            source_id='dyadicsync_exp'
        )
        return StreamOutlet(info)
```

### 2. Timeline Class

```python
class Timeline:
    """
    Manages the sequence of blocks in an experiment.

    A timeline is an ordered list of blocks that execute sequentially.
    Supports reordering, insertion, deletion via GUI.
    """

    def __init__(self):
        self.blocks: List[Block] = []

    def add_block(self, block: 'Block', index: Optional[int] = None):
        """
        Add a block to the timeline.

        Args:
            block: Block instance to add
            index: Position to insert (None = append to end)
        """
        if index is None:
            self.blocks.append(block)
        else:
            self.blocks.insert(index, block)

    def remove_block(self, index: int):
        """Remove block at index."""
        del self.blocks[index]

    def reorder_block(self, old_index: int, new_index: int):
        """Move block from old_index to new_index."""
        block = self.blocks.pop(old_index)
        self.blocks.insert(new_index, block)

    def validate(self) -> List[str]:
        """
        Validate all blocks in timeline.

        Returns:
            List of error messages
        """
        errors = []
        for i, block in enumerate(self.blocks):
            block_errors = block.validate()
            errors.extend([f"Block {i} ({block.name}): {e}" for e in block_errors])
        return errors

    def get_total_trials(self) -> int:
        """Calculate total number of trials across all blocks."""
        return sum(block.get_trial_count() for block in self.blocks)

    def get_estimated_duration(self) -> float:
        """
        Estimate total experiment duration in seconds.

        Returns:
            Total seconds (may be approximate for variable-duration phases)
        """
        return sum(block.get_estimated_duration() for block in self.blocks)
```

### 3. Block Class

```python
class Block:
    """
    A block represents a collection of trials with a shared procedure.

    Examples:
    - Baseline block: Single trial, FixationPhase(240s)
    - Video block: 20 trials, each following Fixation→Video→Rating procedure
    - Instruction block: Single trial, InstructionPhase

    Components:
    - Procedure: Template defining phase sequence
    - Trial List: Data source (CSV or manual)
    - Randomization: How to order trials
    """

    def __init__(self, name: str, block_type: str = 'trial_based'):
        """
        Initialize block.

        Args:
            name: Human-readable block name (e.g., "Emotional Videos")
            block_type: 'trial_based' or 'simple' (no trials, just procedure)
        """
        self.name = name
        self.block_type = block_type

        # Procedure and trials
        self.procedure: Optional[Procedure] = None
        self.trial_list: Optional[TrialList] = None
        self.randomization: RandomizationConfig = RandomizationConfig()

        # Runtime state
        self.current_trial_index: int = 0
        self.completed_trials: List[Trial] = []

    def execute(self, device_manager, lsl_outlet, data_collector):
        """
        Execute all trials in this block.

        Args:
            device_manager: For accessing displays/audio
            lsl_outlet: For sending LSL markers
            data_collector: For saving trial data
        """
        if self.block_type == 'simple':
            # Single execution (e.g., baseline)
            self.procedure.execute(
                trial_data=None,
                device_manager=device_manager,
                lsl_outlet=lsl_outlet,
                data_collector=data_collector
            )

        elif self.block_type == 'trial_based':
            # Get (possibly randomized) trial order
            trials = self.trial_list.get_trials(self.randomization)

            for trial in trials:
                # Execute procedure with this trial's data
                trial_result = self.procedure.execute(
                    trial_data=trial.data,
                    device_manager=device_manager,
                    lsl_outlet=lsl_outlet,
                    data_collector=data_collector
                )

                # Store result
                trial.result = trial_result
                self.completed_trials.append(trial)

                # Save intermediate data (in case of crash)
                data_collector.save_trial(trial)

                self.current_trial_index += 1

    def validate(self) -> List[str]:
        """
        Validate block configuration.

        Returns:
            List of error messages
        """
        errors = []

        if not self.procedure:
            errors.append("No procedure defined")
        else:
            errors.extend(self.procedure.validate())

        if self.block_type == 'trial_based':
            if not self.trial_list:
                errors.append("Trial-based block requires trial list")
            else:
                errors.extend(self.trial_list.validate())

        return errors

    def get_trial_count(self) -> int:
        """Number of trials in this block."""
        if self.block_type == 'simple':
            return 1
        return len(self.trial_list.trials) if self.trial_list else 0

    def get_estimated_duration(self) -> float:
        """Estimated block duration in seconds."""
        trial_duration = self.procedure.get_estimated_duration()
        return trial_duration * self.get_trial_count()
```

### 4. Procedure Class

```python
class Procedure:
    """
    Defines the sequence of phases that occur in each trial.

    Example:
        procedure = Procedure("Standard Trial")
        procedure.add_phase(FixationPhase(duration=3))
        procedure.add_phase(VideoPhase(p1_video="{video1}", p2_video="{video2}"))
        procedure.add_phase(RatingPhase(question="How did you feel?"))

    Templates:
    - Phases can reference trial data using {column_name} syntax
    - Values filled at runtime from trial list
    """

    def __init__(self, name: str):
        self.name = name
        self.phases: List[Phase] = []

    def add_phase(self, phase: 'Phase'):
        """Add a phase to the procedure."""
        self.phases.append(phase)

    def remove_phase(self, index: int):
        """Remove phase at index."""
        del self.phases[index]

    def reorder_phase(self, old_index: int, new_index: int):
        """Move phase from old_index to new_index."""
        phase = self.phases.pop(old_index)
        self.phases.insert(new_index, phase)

    def execute(self, trial_data: Optional[Dict], device_manager, lsl_outlet, data_collector):
        """
        Execute all phases in sequence.

        Args:
            trial_data: Dictionary of trial variables (e.g., {'video1': 'path.mp4'})
            device_manager: Device manager instance
            lsl_outlet: LSL outlet for markers
            data_collector: Data collector instance

        Returns:
            dict: Results from all phases (e.g., ratings, RTs)
        """
        results = {}

        for phase in self.phases:
            # Render phase with trial data (replace {video1} etc.)
            rendered_phase = phase.render(trial_data) if trial_data else phase

            # Execute phase
            phase_result = rendered_phase.execute(
                device_manager=device_manager,
                lsl_outlet=lsl_outlet
            )

            # Store result
            results[phase.name] = phase_result

        return results

    def validate(self) -> List[str]:
        """
        Validate all phases.

        Returns:
            List of error messages
        """
        errors = []
        for i, phase in enumerate(self.phases):
            phase_errors = phase.validate()
            errors.extend([f"Phase {i} ({phase.name}): {e}" for e in phase_errors])
        return errors

    def get_estimated_duration(self) -> float:
        """
        Estimated procedure duration in seconds.

        Returns:
            Total duration (sum of all phases)
        """
        return sum(phase.get_estimated_duration() for phase in self.phases)

    def get_required_variables(self) -> Set[str]:
        """
        Get all variables required by this procedure.

        Returns:
            Set of variable names (e.g., {'video1', 'video2', 'emotion'})

        Used to validate trial list has required columns.
        """
        variables = set()
        for phase in self.phases:
            variables.update(phase.get_required_variables())
        return variables
```

### 5. TrialList Class

```python
class TrialList:
    """
    Manages a list of trials loaded from CSV or created manually.

    Handles:
    - Loading from CSV
    - Randomization with constraints
    - Trial generation
    - Validation
    """

    def __init__(self, source: str, source_type: str = 'csv'):
        """
        Initialize trial list.

        Args:
            source: Path to CSV file or JSON string
            source_type: 'csv' or 'json'
        """
        self.source = source
        self.source_type = source_type
        self.trials: List[Trial] = []
        self._load_trials()

    def _load_trials(self):
        """Load trials from source."""
        if self.source_type == 'csv':
            import pandas as pd
            df = pd.read_csv(self.source)

            for idx, row in df.iterrows():
                trial = Trial(
                    trial_id=idx,
                    data=row.to_dict()
                )
                self.trials.append(trial)

    def get_trials(self, randomization_config: RandomizationConfig) -> List['Trial']:
        """
        Get trials in specified order (randomized or not).

        Args:
            randomization_config: Randomization settings

        Returns:
            List of Trial objects in execution order
        """
        if randomization_config.method == 'none':
            return self.trials.copy()

        # Randomize
        return randomize_trial_list(self.trials, randomization_config)

    def validate(self) -> List[str]:
        """
        Validate trial list.

        Returns:
            List of error messages

        Checks:
        - All referenced files exist
        - Required columns present
        - Data types correct
        """
        errors = []

        if not self.trials:
            errors.append("Trial list is empty")
            return errors

        # Check each trial
        for i, trial in enumerate(self.trials):
            # Check video files exist
            for key in ['video1', 'video2', 'VideoPath1', 'VideoPath2']:
                if key in trial.data:
                    video_path = trial.data[key]
                    if not os.path.exists(video_path):
                        errors.append(f"Trial {i}: Video not found: {video_path}")

        return errors

    def get_columns(self) -> List[str]:
        """Get list of column names available in trials."""
        if not self.trials:
            return []
        return list(self.trials[0].data.keys())
```

### 6. Trial Class

```python
class Trial:
    """
    Represents a single trial execution.

    Contains:
    - trial_id: Unique identifier
    - data: Input data (from trial list)
    - result: Output data (collected during execution)
    - timestamp: When trial was executed
    """

    def __init__(self, trial_id: int, data: Dict[str, Any]):
        """
        Initialize trial.

        Args:
            trial_id: Unique trial identifier
            data: Trial data from trial list (e.g., {'video1': 'path.mp4', 'emotion': 'happy'})
        """
        self.trial_id = trial_id
        self.data = data  # Input data
        self.result: Optional[Dict] = None  # Output data (filled during execution)
        self.timestamp: Optional[float] = None  # Execution time

    def to_dict(self) -> Dict:
        """
        Serialize trial to dictionary.

        Returns:
            Dictionary with all trial information
        """
        return {
            'trial_id': self.trial_id,
            'data': self.data,
            'result': self.result,
            'timestamp': self.timestamp
        }
```

### 7. Phase Base Class

```python
from abc import ABC, abstractmethod

class Phase(ABC):
    """
    Abstract base class for all phase types.

    Subclasses:
    - FixationPhase: Display fixation cross
    - VideoPhase: Play synchronized videos
    - RatingPhase: Collect participant ratings
    - InstructionPhase: Display text instructions
    - BaselinePhase: Baseline recording period
    """

    def __init__(self, name: str):
        self.name = name
        self.marker_start: Optional[int] = None
        self.marker_end: Optional[int] = None

    @abstractmethod
    def execute(self, device_manager, lsl_outlet) -> Dict:
        """
        Execute this phase.

        Args:
            device_manager: For accessing displays/audio
            lsl_outlet: For sending LSL markers

        Returns:
            Dictionary of results (e.g., {'response': 5, 'rt': 1.234})
        """
        pass

    @abstractmethod
    def validate(self) -> List[str]:
        """
        Validate phase configuration.

        Returns:
            List of error messages
        """
        pass

    @abstractmethod
    def get_estimated_duration(self) -> float:
        """
        Estimated phase duration in seconds.

        Returns:
            Duration in seconds (or -1 if variable/unknown)
        """
        pass

    def render(self, trial_data: Dict[str, Any]) -> 'Phase':
        """
        Render phase with trial data (replace template variables).

        Args:
            trial_data: Dictionary of trial variables

        Returns:
            New Phase instance with variables replaced

        Example:
            phase = VideoPhase(p1_video="{video1}")
            rendered = phase.render({'video1': 'happy.mp4'})
            # rendered.p1_video == 'happy.mp4'
        """
        # Default: return self (no variables to replace)
        # Subclasses override if they have template variables
        return self

    def get_required_variables(self) -> Set[str]:
        """
        Get template variables required by this phase.

        Returns:
            Set of variable names (e.g., {'video1', 'video2'})
        """
        # Default: no variables
        # Subclasses override if they use templates
        return set()

    def send_marker(self, lsl_outlet, marker: int):
        """
        Send LSL marker.

        Args:
            lsl_outlet: LSL StreamOutlet
            marker: Integer marker value
        """
        if lsl_outlet:
            lsl_outlet.push_sample([marker])
```

### 8. VideoPhase Implementation

```python
class VideoPhase(Phase):
    """
    Phase for playing synchronized videos to two participants.

    Features:
    - Timestamp-based synchronization
    - Per-participant video selection
    - Automatic duration detection
    - LSL markers for video start/end
    """

    def __init__(
        self,
        name: str = "Video Playback",
        participant_1_video: str = "",
        participant_2_video: str = "",
        auto_advance: bool = True
    ):
        """
        Initialize video phase.

        Args:
            name: Phase name
            participant_1_video: Path to P1 video (or "{column}" template)
            participant_2_video: Path to P2 video (or "{column}" template)
            auto_advance: Automatically proceed when videos finish
        """
        super().__init__(name)
        self.participant_1_video = participant_1_video
        self.participant_2_video = participant_2_video
        self.auto_advance = auto_advance

    def execute(self, device_manager, lsl_outlet) -> Dict:
        """
        Execute video playback.

        Returns:
            {'duration': float, 'actual_start': float, 'sync_quality': dict}
        """
        # Send start marker
        self.send_marker(lsl_outlet, self.marker_start)

        # Create synchronized players
        player1 = device_manager.create_video_player(
            video_path=self.participant_1_video,
            display_id=0,
            audio_device_id=device_manager.audio_device_p1
        )
        player2 = device_manager.create_video_player(
            video_path=self.participant_2_video,
            display_id=1,
            audio_device_id=device_manager.audio_device_p2
        )

        # Prepare both players
        player1.prepare()
        player2.prepare()

        # Synchronized playback
        sync_result = SyncEngine.play_synchronized([player1, player2])

        # Wait for completion
        duration1 = player1.wait_until_finished()
        duration2 = player2.wait_until_finished()

        # Send end marker
        self.send_marker(lsl_outlet, self.marker_end)

        # Cleanup
        player1.cleanup()
        player2.cleanup()

        return {
            'duration': max(duration1, duration2),
            'sync_quality': sync_result,
            'video1_duration': duration1,
            'video2_duration': duration2
        }

    def validate(self) -> List[str]:
        """Validate video paths."""
        errors = []

        # Check if videos are templates or actual paths
        if not self._is_template(self.participant_1_video):
            if not os.path.exists(self.participant_1_video):
                errors.append(f"Participant 1 video not found: {self.participant_1_video}")

        if not self._is_template(self.participant_2_video):
            if not os.path.exists(self.participant_2_video):
                errors.append(f"Participant 2 video not found: {self.participant_2_video}")

        return errors

    def get_estimated_duration(self) -> float:
        """
        Estimate duration (from video file metadata).

        Returns:
            Duration in seconds (or -1 if template/unknown)
        """
        if self._is_template(self.participant_1_video):
            return -1  # Variable (depends on trial)

        # Get duration from video file
        try:
            import pyglet
            source = pyglet.media.load(self.participant_1_video)
            return source.duration
        except:
            return -1

    def render(self, trial_data: Dict[str, Any]) -> 'VideoPhase':
        """Replace template variables with trial data."""
        rendered = VideoPhase(
            name=self.name,
            participant_1_video=self._replace_template(self.participant_1_video, trial_data),
            participant_2_video=self._replace_template(self.participant_2_video, trial_data),
            auto_advance=self.auto_advance
        )
        rendered.marker_start = self.marker_start
        rendered.marker_end = self.marker_end
        return rendered

    def get_required_variables(self) -> Set[str]:
        """Extract variable names from templates."""
        variables = set()
        variables.update(self._extract_variables(self.participant_1_video))
        variables.update(self._extract_variables(self.participant_2_video))
        return variables

    @staticmethod
    def _is_template(s: str) -> bool:
        """Check if string contains template variables."""
        return '{' in s and '}' in s

    @staticmethod
    def _extract_variables(template: str) -> Set[str]:
        """Extract variable names from template string."""
        import re
        return set(re.findall(r'\{(\w+)\}', template))

    @staticmethod
    def _replace_template(template: str, data: Dict[str, Any]) -> str:
        """Replace {var} with data['var']."""
        result = template
        for key, value in data.items():
            result = result.replace(f'{{{key}}}', str(value))
        return result
```

### 9. DeviceManager Class

```python
class DeviceManager:
    """
    Manages all hardware devices (displays, audio, input).

    Responsibilities:
    - Enumerate available devices
    - Validate device configuration
    - Create players with correct device routing
    - Manage multi-display setup
    """

    def __init__(self):
        self.displays: List[Any] = []
        self.audio_devices: List[Dict] = []

        # Configuration (set via GUI or config file)
        self.display_p1: int = 1
        self.display_p2: int = 2
        self.audio_device_p1: int = 9
        self.audio_device_p2: int = 7

        # Windows
        self.window1: Optional[pyglet.window.Window] = None
        self.window2: Optional[pyglet.window.Window] = None

    def initialize(self):
        """
        Initialize devices and create windows.
        """
        # Enumerate devices
        self.displays = self._enumerate_displays()
        self.audio_devices = self._enumerate_audio_devices()

        # Create windows
        self.window1 = pyglet.window.Window(
            fullscreen=True,
            screen=self.displays[self.display_p1]
        )
        self.window2 = pyglet.window.Window(
            fullscreen=True,
            screen=self.displays[self.display_p2]
        )

    def cleanup(self):
        """Close windows and release devices."""
        if self.window1:
            self.window1.close()
        if self.window2:
            self.window2.close()

    def create_video_player(self, video_path, display_id, audio_device_id):
        """
        Factory method to create configured video player.

        Args:
            video_path: Path to video file
            display_id: 0 for P1, 1 for P2
            audio_device_id: Audio output device index

        Returns:
            SynchronizedPlayer instance
        """
        window = self.window1 if display_id == 0 else self.window2
        return SynchronizedPlayer(video_path, audio_device_id, window)

    def validate(self) -> List[str]:
        """
        Validate device configuration.

        Returns:
            List of error messages
        """
        errors = []

        # Check displays exist
        if self.display_p1 >= len(self.displays):
            errors.append(f"Display {self.display_p1} not found (only {len(self.displays)} displays)")
        if self.display_p2 >= len(self.displays):
            errors.append(f"Display {self.display_p2} not found (only {len(self.displays)} displays)")

        # Check audio devices exist
        if self.audio_device_p1 >= len(self.audio_devices):
            errors.append(f"Audio device {self.audio_device_p1} not found")
        if self.audio_device_p2 >= len(self.audio_devices):
            errors.append(f"Audio device {self.audio_device_p2} not found")

        return errors

    def _enumerate_displays(self) -> List:
        """Get list of available displays."""
        display = pyglet.canvas.get_display()
        return display.get_screens()

    def _enumerate_audio_devices(self) -> List[Dict]:
        """Get list of available audio output devices."""
        import sounddevice as sd
        devices = sd.query_devices()
        return [d for d in devices if d['max_output_channels'] > 0]

    def test_audio_device(self, device_id: int):
        """
        Play test tone on specified device.

        Args:
            device_id: Audio device index
        """
        import numpy as np
        import sounddevice as sd

        # Generate 1-second 440Hz tone
        duration = 1.0
        sample_rate = 44100
        t = np.linspace(0, duration, int(sample_rate * duration))
        tone = 0.5 * np.sin(2 * np.pi * 440 * t)

        # Play on specified device
        sd.play(tone, sample_rate, device=device_id)
        sd.wait()
```

---

## GUI Design

### Main Window: Experiment Builder

```
┌────────────────────────────────────────────────────────────────┐
│ DyadicSync Experiment Builder                      [_][□][X]  │
├────────────────────────────────────────────────────────────────┤
│ File  Edit  View  Run  Help                                   │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────┐  │
│ │ Experiment: "Emotional Contagion Study"                  │  │
│ │ Description: Dyadic emotional video viewing              │  │
│ │ Estimated Duration: 25 minutes                           │  │
│ └──────────────────────────────────────────────────────────┘  │
│                                                                │
│ ┌─ Timeline ──────────────────────────────────────────────┐   │
│ │                                                          │   │
│ │  Block 1: Baseline                        [Edit] [Del]  │   │
│ │  ├─ Type: Simple                                        │   │
│ │  ├─ Procedure: Fixation (240s)                          │   │
│ │  └─ Trials: 1                                           │   │
│ │                                                          │   │
│ │  Block 2: Emotional Videos                [Edit] [Del]  │   │
│ │  ├─ Type: Trial-based                                   │   │
│ │  ├─ Procedure: Fixation → Video → Rating               │   │
│ │  ├─ Trial List: video_pairs_extended.csv (20 trials)    │   │
│ │  └─ Randomization: Constrained (max 2 consecutive)      │   │
│ │                                                          │   │
│ │  Block 3: Post-Baseline                   [Edit] [Del]  │   │
│ │  ├─ Type: Simple                                        │   │
│ │  ├─ Procedure: Fixation (120s)                          │   │
│ │  └─ Trials: 1                                           │   │
│ │                                                          │   │
│ │  [+ Add Block]                                          │   │
│ └──────────────────────────────────────────────────────────┘   │
│                                                                │
│ ┌─ Devices ──────────────────────────────────────────────┐    │
│ │ Participant 1: Display 2, Audio Device 9              │    │
│ │ Participant 2: Display 3, Audio Device 7              │    │
│ │                                   [Configure Devices]  │    │
│ └──────────────────────────────────────────────────────────┘   │
│                                                                │
│ [Validate] [Save] [Load] [Run Experiment]                     │
└────────────────────────────────────────────────────────────────┘
```

### Block Editor Window

```
┌────────────────────────────────────────────────────────────────┐
│ Edit Block: "Emotional Videos"                    [_][□][X]   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ Block Name: [Emotional Videos                              ]  │
│                                                                │
│ Block Type: ○ Simple   ● Trial-based                          │
│                                                                │
│ ┌─ Procedure ────────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Phase 1: Fixation Cross              [↑] [↓] [Edit]  │    │
│ │  ├─ Duration: 3 seconds                                │    │
│ │  └─ Marker: None                                       │    │
│ │                                                         │    │
│ │  Phase 2: Video Playback              [↑] [↓] [Edit]  │    │
│ │  ├─ P1 Video: {video1}                                 │    │
│ │  ├─ P2 Video: {video2}                                 │    │
│ │  ├─ Duration: Auto                                     │    │
│ │  └─ Markers: 1000 (start), 2100 (end)                  │    │
│ │                                                         │    │
│ │  Phase 3: Rating Collection           [↑] [↓] [Edit]  │    │
│ │  ├─ Question: "How did this make you feel?"            │    │
│ │  ├─ Scale: 1-7 (Awful to Amazing)                      │    │
│ │  └─ Markers: 300000+rating (P1), 500000+rating (P2)    │    │
│ │                                                         │    │
│ │  [+ Add Phase]                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ Trial List ───────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Source: [video_pairs_extended.csv    ] [Browse...]   │    │
│ │                                                         │    │
│ │  Columns:                                              │    │
│ │  ✓ video1        ✓ video2        ✓ emotion            │    │
│ │  ✓ valence       ○ correct_resp  ○ duration           │    │
│ │                                                         │    │
│ │  Trials Loaded: 20                     [Preview...]   │    │
│ │                                                         │    │
│ │  Randomization:                                        │    │
│ │  Method: [Constrained Random    ▼]                    │    │
│ │  Seed: [12345                   ]  [Generate]         │    │
│ │                                                         │    │
│ │  Constraints:                          [+ Add]         │    │
│ │  • Max Consecutive: emotion="happy", limit=2          │    │
│ │  • Max Consecutive: emotion="sad", limit=2            │    │
│ │                                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ [Cancel] [OK]                                                 │
└────────────────────────────────────────────────────────────────┘
```

### Device Configurator

```
┌────────────────────────────────────────────────────────────────┐
│ Device Configuration                              [_][□][X]   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ ┌─ Displays ─────────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Available Displays:                                   │    │
│ │  0: [■] Primary Monitor (1920x1080)                    │    │
│ │  1: [■] Secondary Monitor (1920x1080)                  │    │
│ │  2: [■] Tertiary Monitor (1920x1080)                   │    │
│ │                                                         │    │
│ │  Participant 1: [Display 1 (Secondary) ▼]             │    │
│ │  Participant 2: [Display 2 (Tertiary)  ▼]             │    │
│ │                                                         │    │
│ │                                    [Test Displays]     │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ Audio Devices ────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Available Audio Outputs:                              │    │
│ │  7: [■] Headphones (USB Audio)                         │    │
│ │  9: [■] Speakers (Realtek)                             │    │
│ │  11: [■] Headset (Bluetooth)                           │    │
│ │                                                         │    │
│ │  Participant 1: [Device 9 (Speakers)    ▼] [Test 🔊]  │    │
│ │  Participant 2: [Device 7 (Headphones)  ▼] [Test 🔊]  │    │
│ │                                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ LSL Configuration ────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Stream Name: [ExpEvent_Markers                      ] │    │
│ │  Stream Type: [Markers                               ] │    │
│ │  Enabled: ☑                                            │    │
│ │                                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ [Test All Devices] [Save Configuration] [Close]              │
└────────────────────────────────────────────────────────────────┘
```

### Runtime Controller

```
┌────────────────────────────────────────────────────────────────┐
│ Experiment Running: "Emotional Contagion Study"   [_][□][X]   │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│ ┌─ Progress ─────────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Block 2 of 3: Emotional Videos                        │    │
│ │  Trial 12 of 20                                        │    │
│ │                                                         │    │
│ │  [████████████████░░░░░░░░] 60%                        │    │
│ │                                                         │    │
│ │  Current Phase: Rating Collection                      │    │
│ │  Elapsed: 15:23 / Remaining: ~9:37                     │    │
│ │                                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ Current Trial ────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  Trial ID: 12                                          │    │
│ │  Video 1: videos/sad_03.mp4                            │    │
│ │  Video 2: videos/sad_04.mp4                            │    │
│ │  Emotion: sad                                          │    │
│ │                                                         │    │
│ │  Sync Quality: ✓ Excellent (1.2ms spread)              │    │
│ │  Participant 1 Response: 2 (RT: 1.45s)                 │    │
│ │  Participant 2 Response: Waiting...                    │    │
│ │                                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ Controls ─────────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  [Pause]  [Skip Trial]  [Abort (Save Data)]           │    │
│ │                                                         │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
│ ┌─ Log ──────────────────────────────────────────────────┐    │
│ │                                                         │    │
│ │  15:23:12 - Trial 12 started                           │    │
│ │  15:23:12 - Fixation phase (3s)                        │    │
│ │  15:23:15 - Video playback started                     │    │
│ │  15:23:15 - [SYNC] Player 0: +0.8ms, Player 1: +1.2ms │    │
│ │  15:23:43 - Video playback ended                       │    │
│ │  15:23:43 - Rating phase started                       │    │
│ │  15:23:45 - Participant 1 responded: 2 (RT: 1.45s)     │    │
│ │  ▼                                                      │    │
│ └─────────────────────────────────────────────────────────┘    │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## File Formats

### Experiment Configuration (JSON)

```json
{
  "experiment": {
    "name": "Emotional Contagion Study",
    "description": "Dyadic emotional video viewing with rating collection",
    "version": "1.0",
    "author": "Researcher Name",
    "created": "2025-11-15T10:30:00Z"
  },

  "devices": {
    "participant_1": {
      "display": 1,
      "audio_device": 9,
      "input_keys": ["1", "2", "3", "4", "5", "6", "7"]
    },
    "participant_2": {
      "display": 2,
      "audio_device": 7,
      "input_keys": ["Q", "W", "E", "R", "T", "Y", "U"]
    },
    "lsl": {
      "enabled": true,
      "stream_name": "ExpEvent_Markers",
      "stream_type": "Markers",
      "channel_count": 1
    }
  },

  "timeline": {
    "blocks": [
      {
        "name": "Baseline",
        "type": "simple",
        "procedure": {
          "name": "Baseline Recording",
          "phases": [
            {
              "type": "FixationPhase",
              "name": "Baseline Fixation",
              "duration": 240,
              "marker_start": 8888,
              "marker_end": 9999
            }
          ]
        }
      },

      {
        "name": "Emotional Videos",
        "type": "trial_based",
        "procedure": {
          "name": "Standard Trial",
          "phases": [
            {
              "type": "FixationPhase",
              "name": "Pre-Video Fixation",
              "duration": 3,
              "marker_start": null
            },
            {
              "type": "VideoPhase",
              "name": "Video Playback",
              "participant_1_video": "{video1}",
              "participant_2_video": "{video2}",
              "marker_start": 1000,
              "marker_end": 2100,
              "auto_advance": true
            },
            {
              "type": "RatingPhase",
              "name": "Emotional Rating",
              "question": "How did this video make you feel?",
              "scale_min": 1,
              "scale_max": 7,
              "scale_labels": ["Awful", "Neutral", "Amazing"],
              "marker_template": {
                "participant_1": "300000 + {trial_index} * 100 + {response}",
                "participant_2": "500000 + {trial_index} * 100 + {response}"
              }
            }
          ]
        },

        "trial_list": {
          "source": "D:\\Projects\\DyadicSync\\video_pairs_extended.csv",
          "source_type": "csv"
        },

        "randomization": {
          "method": "constrained",
          "seed": 12345,
          "constraints": [
            {
              "type": "max_consecutive",
              "attribute": "emotion",
              "value": "happy",
              "limit": 2
            },
            {
              "type": "max_consecutive",
              "attribute": "emotion",
              "value": "sad",
              "limit": 2
            }
          ]
        }
      },

      {
        "name": "Post-Baseline",
        "type": "simple",
        "procedure": {
          "name": "Post Recording",
          "phases": [
            {
              "type": "FixationPhase",
              "name": "Post-Baseline Fixation",
              "duration": 120,
              "marker_start": 9998,
              "marker_end": 9997
            }
          ]
        }
      }
    ]
  },

  "data_output": {
    "directory": "D:\\Data\\DyadicSync",
    "filename_template": "exp_{date}_{time}.csv",
    "save_intermediate": true
  }
}
```

### Trial List (CSV)

```csv
trial_id,video1,video2,emotion,valence,arousal,category
1,D:\Videos\happy_01.mp4,D:\Videos\happy_02.mp4,happy,positive,high,social
2,D:\Videos\happy_03.mp4,D:\Videos\happy_04.mp4,happy,positive,high,achievement
3,D:\Videos\sad_01.mp4,D:\Videos\sad_02.mp4,sad,negative,low,loss
4,D:\Videos\sad_03.mp4,D:\Videos\sad_04.mp4,sad,negative,low,failure
5,D:\Videos\neutral_01.mp4,D:\Videos\neutral_02.mp4,neutral,neutral,low,object
6,D:\Videos\happy_05.mp4,D:\Videos\happy_06.mp4,happy,positive,high,humor
7,D:\Videos\sad_05.mp4,D:\Videos\sad_06.mp4,sad,negative,medium,separation
8,D:\Videos\neutral_03.mp4,D:\Videos\neutral_04.mp4,neutral,neutral,low,landscape
```

### Output Data (CSV)

```csv
experiment_name,participant_1_id,participant_2_id,timestamp,block_name,trial_id,trial_index,video1,video2,emotion,valence,p1_response,p1_rt,p2_response,p2_rt,sync_quality_ms,video_duration
Emotional Contagion Study,P001,P002,2025-11-15T14:23:12.345Z,Emotional Videos,1,0,happy_01.mp4,happy_02.mp4,happy,positive,6,1.234,7,1.456,0.8,28.5
Emotional Contagion Study,P001,P002,2025-11-15T14:24:05.678Z,Emotional Videos,2,1,happy_03.mp4,happy_04.mp4,happy,positive,5,2.123,6,1.987,1.2,31.2
Emotional Contagion Study,P001,P002,2025-11-15T14:25:12.901Z,Emotional Videos,3,2,sad_01.mp4,sad_02.mp4,sad,negative,2,1.678,3,1.543,0.9,26.8
```

---

## Implementation Roadmap

### Phase 1: Core Foundation (Week 1-2)

**Goal:** Create core classes and migrate current functionality

**Tasks:**
1. Create project structure
   - Set up directories (core/, gui/, io/, playback/, utils/)
   - Initialize git repository
   - Create requirements.txt

2. Implement core classes
   - `Experiment` class (basic structure)
   - `Timeline` class
   - `Block` class
   - `Procedure` class
   - `Phase` base class

3. Implement basic phases
   - `FixationPhase`
   - `VideoPhase` (without sync improvements yet)
   - `RatingPhase`

4. Port current script logic
   - Migrate WithBaseline.py logic into new classes
   - Ensure feature parity (same functionality, new structure)

**Deliverable:** Working experiment using new classes (no GUI yet, hardcoded config)

**Validation:** Run experiment, verify LSL markers, check data output

---

### Phase 2: Synchronization System (Week 3)

**Goal:** Eliminate 350ms manual offset with timestamp-based sync

**Tasks:**
1. Implement `SyncEngine` class
   - `calculate_sync_timestamp()`
   - `wait_until_timestamp()`
   - `play_synchronized()`
   - Verification logging

2. Modify `SynchronizedPlayer`
   - Add `play_at_timestamp()` method
   - Implement hybrid sleep + busy-wait
   - Add audio/video start logging

3. Update `VideoPhase`
   - Use SyncEngine instead of manual offset
   - Add sync quality reporting

4. Test synchronization
   - Create test video with metronome (visual + audio)
   - Measure actual sync quality
   - Tune buffer times if needed

**Deliverable:** Audio/video sync within 5ms, no manual offset

**Validation:** Console logs show <5ms drift, metronome test shows perfect sync

---

### Phase 3: Trial List & Randomization (Week 4)

**Goal:** Implement E-Prime-style procedure/list separation

**Tasks:**
1. Implement `TrialList` class
   - CSV loading
   - Column validation
   - Trial generation

2. Implement `Trial` class
   - Data storage
   - Result storage
   - Serialization

3. Implement randomization
   - Full shuffle
   - Constrained random (with constraint checking)
   - Seed support for reproducibility

4. Add template variable support
   - Variable extraction from phase configs
   - Variable replacement at runtime
   - Validation (ensure all variables present in trial list)

5. Update `VideoPhase` and other phases
   - Support template variables ({video1}, {video2})
   - `render()` method implementation

**Deliverable:** Experiments can load trial lists from CSV and randomize

**Validation:** Trial order changes with different seeds, constraints enforced

---

### Phase 4: Device Management (Week 5)

**Goal:** No more hardcoded device indices

**Tasks:**
1. Implement `DeviceManager` class
   - Display enumeration
   - Audio device enumeration
   - Device validation
   - Test methods

2. Create configuration save/load
   - JSON serialization
   - Device ID mapping (handle device changes)

3. Update experiment to use DeviceManager
   - Pass device_manager to all phases
   - Use factory methods for player creation

4. Add device testing
   - Audio test tones
   - Display test patterns

**Deliverable:** Device configuration in JSON, no code editing needed

**Validation:** Change devices in config, experiment uses new devices

---

### Phase 5: Experiment Serialization (Week 6)

**Goal:** Save/load complete experiments as JSON

**Tasks:**
1. Implement `ExperimentSerializer` class
   - `save()` method
   - `load()` method
   - Schema validation

2. Add serialization to all classes
   - `to_dict()` methods
   - `from_dict()` constructors

3. Create JSON schema
   - Define complete experiment format
   - Validation rules

4. Test round-trip
   - Save experiment → Load experiment → Verify identical

**Deliverable:** Complete experiments saved as human-readable JSON

**Validation:** Load saved experiment, run it, verify identical behavior

---

### Phase 6: Basic GUI (Week 7-8)

**Goal:** GUI for device configuration and experiment loading

**Tasks:**
1. Create `ExperimentBuilder` main window
   - Menu bar
   - Timeline display (read-only for now)
   - Device configuration button
   - Load/Save/Run buttons

2. Create `DeviceConfigurator` dialog
   - Display selection dropdowns
   - Audio device selection dropdowns
   - Test buttons
   - Save configuration

3. Create `RuntimeController` window
   - Progress display
   - Current trial info
   - Sync quality display
   - Pause/Abort controls

4. Integrate GUI with core
   - Load button → file dialog → load experiment
   - Run button → validate → start experiment
   - Display progress during execution

**Deliverable:** Functional GUI for loading and running experiments

**Validation:** Load experiment via GUI, configure devices, run successfully

---

### Phase 7: Timeline Editor (Week 9-10)

**Goal:** Visual timeline editing with drag-drop

**Tasks:**
1. Create `TimelineEditor` widget
   - Block list display
   - Add/remove/reorder blocks
   - Visual representation

2. Create `BlockEditor` dialog
   - Block type selection
   - Procedure editing
   - Trial list selection
   - Randomization configuration

3. Create `ProcedureEditor` widget
   - Phase list display
   - Add/remove/reorder phases
   - Phase property editing

4. Create `PhaseEditor` dialogs
   - Phase-specific property editors
   - Template variable support
   - Marker configuration

5. Implement drag-drop
   - Reorder blocks in timeline
   - Reorder phases in procedure

**Deliverable:** Complete visual experiment design

**Validation:** Create experiment from scratch using GUI, no code/JSON editing

---

### Phase 8: Advanced Features (Week 11-12)

**Goal:** Polish and extend functionality

**Tasks:**
1. Add more phase types
   - `InstructionPhase`
   - `BaselinePhase` (with physiological recording markers)
   - `BreakPhase` (wait for experimenter)

2. Add constraint editor
   - GUI for adding randomization constraints
   - Constraint templates (max consecutive, balance, etc.)

3. Add data viewer
   - Load and display collected data
   - Basic statistics (response distributions, RTs)

4. Add experiment templates
   - Pre-configured experiment types
   - Quick start wizard

5. Error handling improvements
   - Graceful failure recovery
   - Partial data saving on crash
   - Device hotplug handling

**Deliverable:** Production-ready framework

**Validation:** Run complete experiment with all features

---

### Phase 9: Documentation & Testing (Week 13)

**Goal:** Comprehensive documentation and testing

**Tasks:**
1. Write user manual
   - Installation guide
   - Tutorial (create first experiment)
   - Reference documentation

2. Write developer documentation
   - Architecture overview
   - Class reference
   - Extension guide (add new phase types)

3. Create unit tests
   - Test all core classes
   - Test synchronization
   - Test randomization constraints

4. Create integration tests
   - End-to-end experiment tests
   - Device mock testing

5. Create example experiments
   - Simple examples (baseline, single video)
   - Complex examples (multi-block, randomized)

**Deliverable:** Fully documented, tested framework

**Validation:** New user can create experiment following tutorial

---

### Phase 10: Deployment (Week 14)

**Goal:** Package and distribute

**Tasks:**
1. Create installer
   - Windows executable (PyInstaller)
   - Dependency bundling

2. Create distribution package
   - Pip-installable package
   - Requirements management

3. Set up version control
   - Git repository
   - Release tagging

4. Create release notes
   - Feature list
   - Known issues
   - Upgrade guide

**Deliverable:** Distributable package

**Validation:** Install on clean machine, run example experiment

---

## Testing Strategy

### Unit Tests

**Test Coverage:**
- Core classes (Experiment, Timeline, Block, Procedure, Phase)
- Synchronization engine
- Randomization algorithms
- Device enumeration
- Serialization (save/load)

**Framework:** pytest

**Example:**
```python
def test_sync_engine_precision():
    """Test SyncEngine achieves sub-5ms synchronization."""
    sync_timestamp = SyncEngine.calculate_sync_timestamp(100)

    actual_starts = []

    def mock_player(i):
        SyncEngine.wait_until_timestamp(sync_timestamp)
        actual_starts.append(time.perf_counter())

    threads = [threading.Thread(target=mock_player, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Check spread <5ms
    spread = (max(actual_starts) - min(actual_starts)) * 1000
    assert spread < 5.0, f"Sync spread {spread:.2f}ms exceeds 5ms limit"
```

### Integration Tests

**Scenarios:**
1. Load experiment from JSON → Validate → Run (dry run, no actual video)
2. Randomize trial list → Verify constraints satisfied
3. Device configuration → Test devices → Run experiment
4. Multi-block experiment → Verify phase execution order
5. Data collection → Verify output format correct

### Validation Tests

**Visual/Manual:**
1. Metronome sync test (flash + beep must align)
2. Dual video sync test (same video on both screens, check sync)
3. GUI usability test (new user creates experiment)
4. Error recovery test (unplug device during experiment)

---

## Migration Guide

### From WithBaseline.py to New Framework

#### Step 1: Create Experiment Configuration

```python
# Old (WithBaseline.py):
audio_device_1_index = 9
audio_device_2_index = 7
baseline_length = 240
csv_path = r"D:\Projects\DyadicSync\video_pairs_extended.csv"

# New (experiment_config.json):
{
  "devices": {
    "participant_1": {"audio_device": 9},
    "participant_2": {"audio_device": 7}
  },
  "timeline": {
    "blocks": [
      {"name": "Baseline", "procedure": {"phases": [{"type": "FixationPhase", "duration": 240}]}},
      {"name": "Videos", "trial_list": {"source": "video_pairs_extended.csv"}}
    ]
  }
}
```

#### Step 2: Define Procedure

```python
# Old (WithBaseline.py - implicit in code):
# Fixation → Video → Rating (hardcoded in run_video_audio_sync)

# New (in experiment_config.json):
{
  "procedure": {
    "phases": [
      {"type": "FixationPhase", "duration": 3},
      {"type": "VideoPhase", "participant_1_video": "{video1}", "participant_2_video": "{video2}"},
      {"type": "RatingPhase", "question": "How did you feel?", "scale_min": 1, "scale_max": 7}
    ]
  }
}
```

#### Step 3: Run New Framework

```python
# Old:
if __name__ == "__main__":
    show_welcome_screen()
    display_cross_for_duration(baseline_length, lambda: ...)
    play_video_pairs_consecutively(video_pairs, ...)

# New:
from core.experiment import Experiment

experiment = Experiment("experiment_config.json")
errors = experiment.validate()
if not errors:
    experiment.run()
```

---

## Future Extensions

### Multi-Language Support

- GUI text externalized to language files
- Support for non-English instructions

### Cloud Integration

- Upload experiment configurations to cloud
- Download from experiment repository
- Share experiments with collaborators

### Real-Time Monitoring Dashboard

- Web-based dashboard for live monitoring
- Multiple experiment instances
- Remote start/stop control

### Advanced Randomization

- Latin square counterbalancing
- Genetic algorithm for constraint satisfaction
- Adaptive randomization (based on previous responses)

### Physiological Integration

- Direct integration with ECG, EEG devices
- Synchronized recording triggers
- Real-time biofeedback

### Video Analysis

- Automatic emotion detection from participant faces
- Gaze tracking integration
- Post-hoc video annotation

### Statistical Analysis

- Built-in analysis pipeline
- Inter-rater reliability calculations
- Dyadic coupling metrics

---

## Appendix A: Dependencies

### Core Dependencies
```
python >= 3.8
pyglet >= 2.0
sounddevice >= 0.4
soundfile >= 0.12
ffmpeg-python >= 0.2
pandas >= 1.5
numpy >= 1.23
pylsl >= 1.16
```

### GUI Dependencies
```
tkinter (built-in)
pillow >= 9.0 (for image display in GUI)
```

### Development Dependencies
```
pytest >= 7.0
black >= 22.0 (code formatting)
mypy >= 0.990 (type checking)
```

---

## Appendix B: Performance Benchmarks

### Target Performance Metrics

| Metric | Target | Rationale |
|--------|--------|-----------|
| **Audio-Video Sync** | <5ms | Imperceptible to humans |
| **Inter-Player Sync** | <2ms | Ensures dyadic synchrony |
| **Frame Drop Rate** | <0.1% | Smooth playback |
| **GUI Responsiveness** | <100ms | Feels instantaneous |
| **Experiment Load Time** | <2s | Minimal wait |
| **Trial Transition** | <500ms | Smooth flow |

---

## Appendix C: Known Limitations

### Current Limitations

1. **Windows Only**: Pyglet and sounddevice work on other platforms, but multi-screen fullscreen behavior varies
2. **Requires Local Video Files**: No streaming support
3. **Two Participants Maximum**: Architecture could extend to N participants but not tested
4. **No Network Sync**: Can't synchronize across computers (LSL helps post-hoc)
5. **Limited Constraint Types**: Randomization constraints are basic

### Future Work

- Cross-platform testing (macOS, Linux)
- Network synchronization for distributed setups
- Video streaming support (HTTP, RTSP)
- More sophisticated constraint language
- Plugin architecture for custom phases

---

## Summary

This roadmap provides a comprehensive plan to transform the current hardcoded `WithBaseline.py` script into a professional, modular experiment framework. The architecture prioritizes:

1. **Precision synchronization** (timestamp-based, <5ms accuracy)
2. **E-Prime-style workflow** (procedure/list separation)
3. **GUI-driven design** (no code editing for experiments)
4. **Extensibility** (easy to add new phase types, constraints)
5. **Reliability** (validation, error handling, data safety)

**Estimated Total Development Time:** 14 weeks (3.5 months)

**Immediate Next Steps:**
1. Review and approve this architecture
2. Set up project structure
3. Begin Phase 1 implementation
4. Test synchronization improvements on existing script first (can be done in parallel)

---

**Document Version:** 1.0
**Last Updated:** 2025-11-15
**Status:** Architecture Complete, Ready for Implementation
