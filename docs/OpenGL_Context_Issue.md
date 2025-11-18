# OpenGL Context Issue: Error 0x1282

## Problem Overview

When refactoring the DyadicSync experiment system from WithBaseline.py's blocking event loop pattern to a callback-based architecture with a single persistent Pyglet event loop, we encountered a critical OpenGL error:

```
pyglet.gl.lib.GLException: (0x1282): Invalid operation.
The specified operation is not allowed in the current state.
```

**Symptoms:**
- Text briefly appeared on experiment screens, then crashed
- Error occurred when calling `batch.draw()` in `on_draw()` handlers
- Stack trace pointed to `glBindVertexArray()` failing

## Root Cause

### OpenGL Context Binding in Pyglet

In Pyglet, graphics objects (Batches, Labels, VAOs, textures) are **bound to the OpenGL context that is active when they are created**. When you create multiple windows:

1. Creating `window1` activates window1's OpenGL context
2. Creating `window2` activates window2's OpenGL context (window1's context is now inactive)
3. Any graphics objects created after step 2 are bound to window2's context

### The Problem in Our Code

```python
# In device_manager.initialize():
self.window1 = pyglet.window.Window(fullscreen=True, screen=screens[1])
self.window1.set_exclusive_keyboard(False)
# window1's context is ACTIVE

self.window2 = pyglet.window.Window(fullscreen=True, screen=screens[2])
self.window2.set_exclusive_keyboard(False)
# window2's context is now ACTIVE (window1's context is inactive)

# Later, in InstructionPhase.execute():
window1 = device_manager.window1
window2 = device_manager.window2

# Create batches - which context are they in?
self.instruction_batch1 = pyglet.graphics.Batch()  # Created in window2's context!
self.instruction_batch2 = pyglet.graphics.Batch()  # Created in window2's context!

# Create labels
self.label1 = pyglet.text.Label(..., batch=self.instruction_batch1)  # In window2's context

# Then in on_draw handler:
@window1.event
def on_draw():
    window1.clear()  # SWITCHES TO WINDOW1'S CONTEXT
    self.instruction_batch1.draw()  # ERROR! Batch's VAO is bound to window2's context
```

### Why Text Flashed Briefly

The text appeared for one frame because:
1. First draw happened in window2's context (worked correctly)
2. Next draw switched to window1's context via `on_draw()` callback
3. Now `batch1.draw()` tried to use a VAO from the wrong context → OpenGL error 0x1282

## Why WithBaseline.py Didn't Have This Issue

WithBaseline.py avoided this problem through a different architecture:

1. **Separate event loops per phase**: Each phase created windows, ran `pyglet.app.run()`, then closed windows
2. **Fresh contexts**: Windows were created and destroyed for each phase, avoiding context reuse issues
3. **Local variable lifetime**: Batches remained in scope during the blocking `pyglet.app.run()` call

Our refactored code:
1. **Single event loop**: One `pyglet.app.run()` for entire experiment
2. **Persistent windows**: Windows created once in DeviceManager, reused across all phases
3. **Callback-based execution**: Phases return immediately after setup, requiring instance variables

## The Solution: Explicit Context Switching

Call `window.switch_to()` before creating graphics objects for each window to ensure they're created in the correct OpenGL context.

### Pattern to Follow

```python
# Get windows from device manager
window1 = device_manager.window1
window2 = device_manager.window2

# CRITICAL: Switch to window1's OpenGL context before creating its graphics
window1.switch_to()
self.batch1 = pyglet.graphics.Batch()
self.label1 = pyglet.text.Label(..., batch=self.batch1)

# CRITICAL: Switch to window2's OpenGL context before creating its graphics
window2.switch_to()
self.batch2 = pyglet.graphics.Batch()
self.label2 = pyglet.text.Label(..., batch=self.batch2)

# Draw handlers work correctly now
@window1.event
def on_draw():
    window1.clear()
    self.batch1.draw()  # ✅ Works! Batch created in window1's context

@window2.event
def on_draw():
    window2.clear()
    self.batch2.draw()  # ✅ Works! Batch created in window2's context
```

## Implementation

### Files Modified

**1. InstructionPhase** (`core/execution/phases/instruction_phase.py`)
```python
# Lines 91-121
window1.switch_to()
self.instruction_batch1 = pyglet.graphics.Batch()
self.label1 = pyglet.text.Label(..., batch=self.instruction_batch1)

window2.switch_to()
self.instruction_batch2 = pyglet.graphics.Batch()
self.label2 = pyglet.text.Label(..., batch=self.instruction_batch2)
```

**2. FixationPhase** (`core/execution/phases/fixation_phase.py`)
```python
# Lines 76-82
window1.switch_to()
self.cross1 = self._create_cross_display(window1)

window2.switch_to()
self.cross2 = self._create_cross_display(window2)
```

**3. RatingPhase** (`core/execution/phases/rating_phase.py`)
```python
# Lines 108-168
window1.switch_to()
self.instruction_batch1 = pyglet.graphics.Batch()
self.instruction1 = pyglet.text.Label(..., batch=self.instruction_batch1)
self.response1_label = pyglet.text.Label(..., batch=self.instruction_batch1)

window2.switch_to()
self.instruction_batch2 = pyglet.graphics.Batch()
self.instruction2 = pyglet.text.Label(..., batch=self.instruction_batch2)
self.response2_label = pyglet.text.Label(..., batch=self.instruction_batch2)
```

## Best Practices for Multi-Window Pyglet Applications

### 1. Always Use Explicit Context Switching

When working with multiple windows, **never assume which context is active**. Always call `window.switch_to()` before creating graphics objects.

```python
# ❌ WRONG - Assumes context
batch = pyglet.graphics.Batch()
label = pyglet.text.Label(..., batch=batch)

# ✅ CORRECT - Explicit context
window.switch_to()
batch = pyglet.graphics.Batch()
label = pyglet.text.Label(..., batch=batch)
```

### 2. Create Graphics for Each Window in Its Own Context

```python
# ✅ CORRECT Pattern
for window in [window1, window2]:
    window.switch_to()
    # Create all graphics for this window
    batch = pyglet.graphics.Batch()
    labels = [...]
```

### 3. Store Graphics as Instance Variables

In callback-based architectures, graphics objects must persist after the setup function returns:

```python
# ❌ WRONG - Local variables die when function returns
def setup():
    batch = pyglet.graphics.Batch()  # Dies when setup() returns
    @window.event
    def on_draw():
        batch.draw()  # References dead object

# ✅ CORRECT - Instance variables persist
def setup(self):
    self.batch = pyglet.graphics.Batch()  # Persists as long as self exists
    @window.event
    def on_draw():
        self.batch.draw()  # Always valid
```

### 4. Document Context Requirements

When creating reusable components that create graphics, document which context must be active:

```python
def _create_cross_display(self, window):
    """
    Create a cross display object for a window.

    Args:
        window: Pyglet window

    Returns:
        CrossDisplay object

    IMPORTANT: window.switch_to() must be called BEFORE calling this method
    to ensure graphics are created in the correct OpenGL context.
    """
```

## Testing for Context Issues

### Symptoms of Context Problems

1. **Intermittent crashes**: Works sometimes, crashes other times
2. **Flashing content**: Content appears briefly then crashes
3. **Error 0x1282**: "Invalid operation" when calling draw methods
4. **VAO/VBO errors**: Errors related to vertex arrays or buffers

### How to Test

```python
# Add logging to verify correct context
def setup_graphics(window, name):
    window.switch_to()
    print(f"Creating graphics for {name} in context: {window.context}")
    batch = pyglet.graphics.Batch()
    # ... create graphics ...
    return batch
```

### Verification

After implementing context switching, verify:
- ✅ No OpenGL errors during execution
- ✅ Content displays correctly on both windows
- ✅ No crashes during phase transitions
- ✅ Abort mechanism works without hanging

## References

- **Pyglet Window Documentation**: https://pyglet.readthedocs.io/en/latest/modules/window.html
- **OpenGL Context Management**: https://www.khronos.org/opengl/wiki/OpenGL_Context
- **Pyglet Graphics Guide**: https://pyglet.readthedocs.io/en/latest/programming_guide/graphics.html

## Related Issues

This issue is related to but distinct from:
1. **Variable Lifetime Issue**: Local variables going out of scope (also fixed by using instance variables)
2. **Event Loop Pattern**: Blocking vs. non-blocking execution (solved by callback architecture)
3. **Window Management**: Creating vs. reusing windows across phases

All three issues were discovered and resolved during the refactoring from WithBaseline.py to the new modular architecture.

## Conclusion

OpenGL context management is critical when working with multiple windows in Pyglet. The key principle is: **Always explicitly activate the target window's context before creating graphics objects for that window.**

By following the pattern of calling `window.switch_to()` before creating batches, labels, and other graphics primitives, we ensure that all OpenGL objects are created in the correct context and can be used reliably during rendering.
