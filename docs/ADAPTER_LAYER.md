# Adapter Layer Documentation

## Overview

The **Adapter Layer** provides bidirectional conversion between two configuration formats used in the DyadicSync Framework:

1. **ExperimentConfig** - GUI format (flat, trial-based)
2. **Timeline** - Execution format (hierarchical, block-based)

This separation allows the Timeline Editor to use an intuitive, trial-based interface while the execution engine benefits from a flexible, block-based architecture.

## Architecture

### Two Formats, One Purpose

```
┌─────────────────────────────────┐
│    Timeline Editor (GUI)        │
│  ┌───────────────────────────┐  │
│  │   ExperimentConfig        │  │
│  │   - Flat trial list       │  │
│  │   - Simple editing        │  │
│  │   - User-friendly         │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
                ↓
        ExperimentConfigAdapter
          (Bidirectional)
                ↓
┌─────────────────────────────────┐
│   Execution Engine              │
│  ┌───────────────────────────┐  │
│  │   Timeline                │  │
│  │   - Block hierarchy       │  │
│  │   - Reusable procedures   │  │
│  │   - Flexible execution    │  │
│  └───────────────────────────┘  │
└─────────────────────────────────┘
```

### ExperimentConfig Format (GUI)

**Structure:**
```python
ExperimentConfig {
    name: str
    description: str
    baseline_duration: float  # seconds
    audio_device_p1: int
    audio_device_p2: int
    global_defaults: Question
    trials: List[Trial]
    metadata: Dict[str, str]
}

Trial {
    index: int
    video_path_1: str
    video_path_2: str
    fixation_duration: float
    audio_offset_ms: float (deprecated)
    rating_timeout: Optional[float]
    question_override: Optional[Question]
    enabled: bool
    notes: str
}
```

**Characteristics:**
- Each trial is a complete, independent unit
- Easy to visualize and edit
- Trials can be reordered, duplicated, enabled/disabled
- Question configuration can be global or per-trial

**Use Cases:**
- Visual timeline representation
- Drag-and-drop trial reordering
- Quick trial duplication
- Importing from CSV files

### Timeline Format (Execution)

**Structure:**
```python
Timeline {
    blocks: List[Block]
}

Block {
    name: str
    block_type: 'simple' | 'trial_based'
    procedure: Procedure
    trial_list: TrialList (for trial_based only)
    randomization: RandomizationConfig
}

Procedure {
    name: str
    phases: List[Phase]
}

Phase (abstract) {
    # Concrete implementations:
    - BaselinePhase
    - FixationPhase
    - VideoPhase
    - RatingPhase
    - InstructionPhase
}
```

**Characteristics:**
- Hierarchical structure (Timeline → Block → Procedure → Phase)
- Procedure acts as template for all trials in a block
- Supports template variables (`{video1}`, `{video2}`)
- Flexible randomization and constraints

**Use Cases:**
- Reusable procedures across trials
- Complex experiment structures
- Counterbalancing and randomization
- E-Prime style block-based designs

## Conversion Logic

### ExperimentConfig → Timeline

**File:** `core/adapters/experiment_config_adapter.py:to_timeline()`

**Algorithm:**

1. **Create Baseline Block** (if `baseline_duration > 0`)
   ```python
   Block("Baseline", block_type='simple')
     └─ Procedure
          └─ BaselinePhase(duration, markers 8888/9999)
   ```

2. **Group Trials by Question**
   - Trials with same question → single block
   - Trials with different questions → separate blocks
   - Future: Support multiple questions per trial

3. **Create Video Trial Block(s)**
   ```python
   Block("Video Trials", block_type='trial_based')
     ├─ Procedure (template for all trials)
     │    ├─ FixationPhase(duration=3s)
     │    ├─ VideoPhase(p1="{video1}", p2="{video2}")
     │    └─ RatingPhase(question, scale, keys)
     │
     └─ TrialList (data for each trial)
          ├─ Trial 0: {video1: "path1.mp4", video2: "path2.mp4", ...}
          ├─ Trial 1: {video1: "path3.mp4", video2: "path4.mp4", ...}
          └─ ...
   ```

4. **Build TrialList**
   - Create temporary CSV from trial data
   - Load TrialList from CSV
   - Store cleanup reference

**Template Variables:**
- `{video1}` → `trial_data['VideoPath1']` or `trial_data['video1']`
- `{video2}` → `trial_data['VideoPath2']` or `trial_data['video2']`
- `{trial_index}` → Trial number (0-based)

**LSL Markers:**
- Baseline: 8888 (start), 9999 (end)
- Video start: 1000 + trial_index
- Video end: 2100 + trial_index (P1), 2200 + trial_index (P2)
- Ratings: 300000 + trial_index*100 + rating (P1), 500000 + trial_index*100 + rating (P2)

### Timeline → ExperimentConfig

**File:** `core/adapters/experiment_config_adapter.py:from_timeline()`

**Algorithm:**

1. **Extract Baseline Duration**
   - Search for BaselinePhase in simple blocks
   - Set `config.baseline_duration` from phase duration

2. **Flatten Trial Blocks**
   - Iterate through trial-based blocks
   - Extract fixation duration from FixationPhase
   - Extract video paths from TrialList data
   - Extract question from RatingPhase

3. **Reconstruct Trials**
   ```python
   for block in timeline.blocks:
       if block.block_type == 'trial_based':
           fixation_duration = extract_from_FixationPhase()
           question = extract_from_RatingPhase()

           for trial in block.trial_list.trials:
               config_trial = Trial(
                   video_path_1=trial.data['VideoPath1'],
                   video_path_2=trial.data['VideoPath2'],
                   fixation_duration=fixation_duration,
                   question_override=question if different_from_global
               )
   ```

4. **Set Global Defaults**
   - First question encountered becomes global default
   - Subsequent different questions become overrides (future feature)

## Usage Examples

### Basic Conversion

```python
from core.adapters.experiment_config_adapter import ExperimentConfigAdapter
from config.experiment import ExperimentConfig
from config.trial import Trial

# Create experiment config in GUI
config = ExperimentConfig(
    name="Emotion Study",
    baseline_duration=240.0,
    audio_device_p1=9,
    audio_device_p2=7
)

# Add trials
config.add_trial(Trial(
    index=0,
    video_path_1="/videos/happy1.mp4",
    video_path_2="/videos/happy2.mp4",
    fixation_duration=3.0
))

# Convert to timeline for execution
timeline = ExperimentConfigAdapter.to_timeline(config)

# Execute experiment
from core.execution.experiment import Experiment
experiment = Experiment(timeline)
experiment.run()
```

### Round-Trip Conversion

```python
# Load config from GUI
config = load_config("my_experiment.json")

# Convert to timeline
timeline = ExperimentConfigAdapter.to_timeline(config)

# Save timeline format (for advanced users)
with open("my_experiment_timeline.json", 'w') as f:
    json.dump(timeline.to_dict(), f)

# Load timeline
with open("my_experiment_timeline.json", 'r') as f:
    timeline = Timeline.from_dict(json.load(f))

# Convert back to config for editing in GUI
config = ExperimentConfigAdapter.from_timeline(timeline)
```

### Validation

```python
# Validate before conversion
errors = ExperimentConfigAdapter.validate_conversion(config)
if errors:
    print("Validation errors:")
    for error in errors:
        print(f"  - {error}")
else:
    timeline = ExperimentConfigAdapter.to_timeline(config)
```

### Cleanup

```python
# Convert config to timeline
timeline = ExperimentConfigAdapter.to_timeline(config)

# Execute experiment
experiment = Experiment(timeline)
experiment.run()

# Clean up temporary files
ExperimentConfigAdapter.cleanup_timeline(timeline)
```

## Design Decisions

### Why Two Formats?

**Option 1:** Single format for both GUI and execution
- ❌ GUI would be complex (editing hierarchical structures)
- ❌ Execution would be inflexible (changing structure requires GUI changes)

**Option 2:** GUI uses simplified format, execution uses flexible format
- ✅ GUI remains user-friendly
- ✅ Execution engine remains flexible
- ✅ Adapter bridges the gap automatically
- ✅ Each layer optimized for its purpose

### Trial Grouping Strategy

**Current Implementation:** Group trials by question text
- Trials with same question → single block
- Trials with different question_override → separate blocks

**Future Enhancement:** Support multiple questions per trial
- Multiple RatingPhases in single procedure
- Question order configurable
- Conditional questions based on responses

### Audio Offset Handling

**Decision:** Ignore `audio_offset_ms` during conversion
- **Rationale:** Phase 2 will implement timestamp-based synchronization (SyncEngine)
- **Current Approach:** Manual 350ms offset hardcoded in original script
- **Future Approach:** Automatic synchronization using hardware timestamps

### Fixation Duration Variability

**Current Implementation:** Use first trial's fixation duration for all
- **Limitation:** All trials in block must have same fixation
- **Workaround:** Create separate blocks for different fixation durations
- **Future Enhancement:** Make fixation_duration a template variable

## Edge Cases

### Empty Experiment

```python
config = ExperimentConfig(baseline_duration=60.0)  # No trials
timeline = ExperimentConfigAdapter.to_timeline(config)

# Result: Timeline with only baseline block
assert len(timeline.blocks) == 1
assert timeline.blocks[0].block_type == 'simple'
```

### No Baseline

```python
config = ExperimentConfig(baseline_duration=0.0)
timeline = ExperimentConfigAdapter.to_timeline(config)

# Result: Timeline with only video block
assert len(timeline.blocks) == 1
assert timeline.blocks[0].block_type == 'trial_based'
```

### Disabled Trials

```python
config.add_trial(Trial(..., enabled=False))
timeline = ExperimentConfigAdapter.to_timeline(config)

# Disabled trials excluded from timeline
assert timeline.get_total_trials() == num_enabled_trials
```

### Question Overrides

```python
# Trial 1: Uses global question
config.add_trial(Trial(..., question_override=None))

# Trial 2: Uses custom question
config.add_trial(Trial(..., question_override=custom_question))

timeline = ExperimentConfigAdapter.to_timeline(config)

# Result: 2 separate blocks (1 per question type)
assert len([b for b in timeline.blocks if b.block_type == 'trial_based']) == 2
```

## Testing

### Unit Tests

**File:** `tests/unit/test_adapters.py`
- 19 tests covering all conversion scenarios
- Validation, round-trip, edge cases

**Coverage:**
- Basic conversion (ExperimentConfig → Timeline)
- Reverse conversion (Timeline → ExperimentConfig)
- Round-trip preservation
- Validation errors
- Edge cases (empty, large, disabled trials)

### Integration Tests

**File:** `tests/integration/test_gui_integration.py`
- 10 tests covering GUI workflow
- Save/load, conversion pipeline

**Coverage:**
- GUI-created config → Timeline conversion
- Save/load preserves convertibility
- Workflow: config → timeline → config
- Validation catches errors before conversion
- Large experiments (20+ trials)

### Running Tests

```bash
# Run adapter tests only
pytest tests/unit/test_adapters.py -v

# Run GUI integration tests
pytest tests/integration/test_gui_integration.py -v

# Run all tests
pytest tests/ -v
```

## Future Enhancements

### Phase 2: Multiple Questions Per Trial

**Goal:** Support multiple rating questions per trial

**Implementation:**
```python
# Config format
trial.questions = [
    Question("How intense?"),
    Question("How pleasant?"),
    Question("How arousing?")
]

# Timeline format
procedure.add_phase(RatingPhase("How intense?"))
procedure.add_phase(RatingPhase("How pleasant?"))
procedure.add_phase(RatingPhase("How arousing?"))
```

### Phase 2: Template Variable Expansion

**Goal:** Support more template variables

**Examples:**
- `{fixation_duration}` - Per-trial fixation
- `{audio_offset}` - Per-trial audio offset
- `{condition}` - Experimental condition label
- `{emotion}` - Emotion category from CSV

### Phase 3: Constraint Support

**Goal:** Convert randomization constraints

**Implementation:**
```python
# Config format
config.randomization.constraints = [
    NoConsecutiveRepeat(column='emotion'),
    MaxRuns(column='valence', max_length=3)
]

# Timeline format
block.randomization.constraints = [
    Constraint(type='no_consecutive', column='emotion'),
    Constraint(type='max_runs', column='valence', max=3)
]
```

## Troubleshooting

### Common Issues

**Issue:** "Missing video paths" validation error
- **Cause:** Trial has empty video_path_1 or video_path_2
- **Solution:** Ensure all trials have valid video paths

**Issue:** Conversion creates extra baseline block
- **Cause:** `baseline_duration > 0`
- **Solution:** Set `baseline_duration = 0.0` if no baseline needed

**Issue:** Timeline.get_total_trials() doesn't match trial count
- **Cause:** Baseline block counts as 1 trial
- **Solution:** Expected = num_video_trials + (1 if baseline else 0)

**Issue:** Temporary CSV files not cleaned up
- **Cause:** `ExperimentConfigAdapter.cleanup_timeline()` not called
- **Solution:** Call cleanup after execution or use try/finally

### Debug Tips

```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Inspect timeline structure
timeline = ExperimentConfigAdapter.to_timeline(config)
print(f"Blocks: {len(timeline.blocks)}")
for i, block in enumerate(timeline.blocks):
    print(f"  Block {i}: {block.name} ({block.block_type})")
    print(f"    Trials: {block.get_trial_count()}")
    print(f"    Duration: {block.get_estimated_duration()}s")

# Validate before execution
errors = timeline.validate()
if errors:
    print("Timeline validation errors:")
    for error in errors:
        print(f"  - {error}")
```

## API Reference

### ExperimentConfigAdapter

**Methods:**

```python
@staticmethod
def to_timeline(config: ExperimentConfig) -> Timeline
    """Convert ExperimentConfig to Timeline."""

@staticmethod
def from_timeline(timeline: Timeline) -> ExperimentConfig
    """Convert Timeline to ExperimentConfig."""

@staticmethod
def validate_conversion(config: ExperimentConfig) -> List[str]
    """Validate that config can be converted. Returns error list."""

@staticmethod
def cleanup_timeline(timeline: Timeline)
    """Clean up temporary resources (CSV files)."""
```

**Example:**
```python
from core.adapters.experiment_config_adapter import ExperimentConfigAdapter

# Convert
timeline = ExperimentConfigAdapter.to_timeline(config)

# Validate
errors = ExperimentConfigAdapter.validate_conversion(config)

# Clean up
ExperimentConfigAdapter.cleanup_timeline(timeline)
```

## Related Documentation

- `ARCHITECTURE_ROADMAP.md` - Overall project architecture and phases
- `TEST_REPORT.md` - Comprehensive test coverage report
- `PHASE1_PROGRESS.md` - Phase 1 implementation progress
- `GUI_INTEGRATION_GUIDE.md` - How to use Timeline Editor with execution engine

## Summary

The Adapter Layer enables seamless integration between the user-friendly Timeline Editor and the powerful execution engine. By supporting bidirectional conversion, it allows users to design experiments visually while benefiting from the flexibility of the block-based execution architecture.

**Key Takeaways:**
- ExperimentConfig (GUI) and Timeline (execution) serve different purposes
- Adapter provides automatic bidirectional conversion
- Trial grouping and template variables enable flexible execution
- Comprehensive test coverage ensures reliability
- Future enhancements will expand capabilities

For questions or issues, see the troubleshooting section or file an issue in the project repository.
