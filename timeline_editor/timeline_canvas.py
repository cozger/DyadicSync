"""
Interactive timeline canvas for visualizing and editing experiment structure.
"""

import tkinter as tk
from tkinter import ttk, Canvas, Frame, Menu
from typing import List, Optional, Callable
import sys
from pathlib import Path
import time

sys.path.append(str(Path(__file__).parent.parent))

from gui.timeline_block import TimelineBlock, BlockType
from core.execution.timeline import Timeline
from core.execution.block import Block
from core.execution.phase import Phase


class TimelineCanvas(Frame):
    """
    Scrollable, zoomable timeline canvas for visualizing and editing blocks.

    Features:
    - Visual blocks for each phase in timeline
    - Click to select blocks
    - Double-click to edit block properties
    - Right-click context menu (or during drag to cancel)
    - Drag-and-drop to reorder blocks (click and drag blocks horizontally)
    - Drag outside bounds to cancel drag operation
    """

    PIXELS_PER_SECOND = 20  # Base scale: 20 pixels = 1 second
    BLOCK_HEIGHT = 60
    BLOCK_SPACING = 10
    RULER_HEIGHT = 30
    MIN_ZOOM = 0.25
    MAX_ZOOM = 4.0
    MAX_COMFORTABLE_DURATION = 20.0  # Max duration before showing break indicator (seconds)

    def __init__(self, parent, timeline: Timeline,
                 on_block_select: Optional[Callable] = None,
                 on_block_edit: Optional[Callable] = None):
        """
        Initialize timeline canvas.

        Args:
            parent: Parent tkinter widget
            timeline: Timeline object to visualize
            on_block_select: Callback when block is selected (receives Block object)
            on_block_edit: Callback when block is double-clicked for editing
        """
        print(f"[DEBUG {time.time():.3f}] TimelineCanvas.__init__ START")
        super().__init__(parent)

        self.timeline = timeline
        self.on_block_select = on_block_select
        self.on_block_edit = on_block_edit

        self.zoom_level = 0.25
        self.selected_block_index = None
        self.blocks: List[TimelineBlock] = []
        self._updating_zoom = False  # Flag to prevent recursion
        self._refreshing = False  # Flag to prevent refresh loops

        # Drag state
        self._dragging_block = None
        self._drag_original_index = None
        self._drag_current_index = None

        print(f"[DEBUG {time.time():.3f}] TimelineCanvas calling _setup_ui...")
        self._setup_ui()
        print(f"[DEBUG {time.time():.3f}] TimelineCanvas DEFERRING _build_timeline with after()...")
        # Defer timeline building to allow window to show first (prevents UI freeze)
        self.after(100, self._build_timeline)
        print(f"[DEBUG {time.time():.3f}] TimelineCanvas.__init__ COMPLETE (timeline will build in 100ms)")

    def _setup_ui(self):
        """Set up the canvas and scrollbars."""
        # Create frame for canvas and scrollbars
        self.canvas_frame = Frame(self)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        # Horizontal scrollbar
        self.h_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.HORIZONTAL)
        self.h_scrollbar.pack(side=tk.BOTTOM, fill=tk.X)

        # Vertical scrollbar
        self.v_scrollbar = ttk.Scrollbar(self.canvas_frame, orient=tk.VERTICAL)
        self.v_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Canvas
        self.canvas = Canvas(
            self.canvas_frame,
            bg="#F5F5F5",
            xscrollcommand=self.h_scrollbar.set,
            yscrollcommand=self.v_scrollbar.set
        )
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.h_scrollbar.config(command=self.canvas.xview)
        self.v_scrollbar.config(command=self.canvas.yview)

        # Control frame for zoom and other controls
        self.control_frame = Frame(self)
        self.control_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)

        # Zoom controls
        ttk.Label(self.control_frame, text="Zoom:").pack(side=tk.LEFT, padx=5)

        self.zoom_out_btn = ttk.Button(
            self.control_frame,
            text="-",
            width=3,
            command=self.zoom_out
        )
        self.zoom_out_btn.pack(side=tk.LEFT, padx=2)

        self.zoom_label = ttk.Label(self.control_frame, text="100%", width=6)
        self.zoom_label.pack(side=tk.LEFT, padx=2)

        self.zoom_in_btn = ttk.Button(
            self.control_frame,
            text="+",
            width=3,
            command=self.zoom_in
        )
        self.zoom_in_btn.pack(side=tk.LEFT, padx=2)

        # Zoom slider - set value BEFORE binding command to avoid initial callback
        self.zoom_slider = ttk.Scale(
            self.control_frame,
            from_=self.MIN_ZOOM,
            to=self.MAX_ZOOM,
            orient=tk.HORIZONTAL,
            value=0.25
        )
        self.zoom_slider.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)

        # Bind command AFTER setting initial value
        self.zoom_slider.configure(command=self._on_zoom_slider_change)

        # Context menu
        self.context_menu = Menu(self, tearoff=0)
        self.context_menu.add_command(label="Edit Trial", command=self._edit_selected_trial)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="Duplicate Trial", command=self._duplicate_selected_trial)
        self.context_menu.add_command(label="Delete Trial", command=self._delete_selected_trial)

        # Bind right-click for context menu
        self.canvas.bind("<Button-3>", self._show_context_menu)

    def _phase_to_block_type(self, phase: Phase) -> BlockType:
        """
        Map Phase class to visual BlockType enum.

        Args:
            phase: Phase object

        Returns:
            BlockType enum value
        """
        from core.execution.phases.fixation_phase import FixationPhase
        from core.execution.phases.video_phase import VideoPhase
        from core.execution.phases.rating_phase import RatingPhase
        from core.execution.phases.baseline_phase import BaselinePhase
        from core.execution.phases.instruction_phase import InstructionPhase

        if isinstance(phase, BaselinePhase):
            return BlockType.BASELINE
        elif isinstance(phase, InstructionPhase):
            return BlockType.INSTRUCTION
        elif isinstance(phase, FixationPhase):
            return BlockType.FIXATION
        elif isinstance(phase, VideoPhase):
            return BlockType.VIDEO
        elif isinstance(phase, RatingPhase):
            return BlockType.RATING
        else:
            # Default fallback
            return BlockType.FIXATION

    def _create_visual_block(self, block_type: BlockType, block_idx: int,
                            actual_duration: float, x: int, y: int) -> TimelineBlock:
        """
        Create a visual timeline block with automatic duration capping for long blocks.

        Args:
            block_type: Type of block to create
            block_idx: Index of parent block
            actual_duration: Actual duration in seconds
            x: X position
            y: Y position

        Returns:
            TimelineBlock instance
        """
        # Cap duration for display if it exceeds comfortable threshold
        display_duration = min(actual_duration, self.MAX_COMFORTABLE_DURATION)
        width = self._duration_to_pixels(display_duration)

        visual_block = TimelineBlock(
            self.canvas,
            block_type,
            trial_index=block_idx,
            x=x,
            y=y,
            width=width,
            height=self.BLOCK_HEIGHT,
            on_click=self._on_block_click,
            on_double_click=self._on_block_double_click,
            on_drag_start=self._on_block_drag_start,
            on_drag_motion=self._on_block_drag_motion,
            on_drag_end=self._on_block_drag_end
        )

        # Add visual break indicator if duration was capped
        if actual_duration > self.MAX_COMFORTABLE_DURATION:
            self._add_break_indicator(visual_block, actual_duration)

        return visual_block

    def _add_break_indicator(self, visual_block: TimelineBlock, actual_duration: float):
        """
        Add a visual break indicator to a block that exceeds comfortable duration.

        Args:
            visual_block: The TimelineBlock to add indicator to
            actual_duration: The actual duration (not capped)
        """
        # Add text overlay showing "/---/ (actual duration)"
        mins = int(actual_duration // 60)
        secs = int(actual_duration % 60)
        duration_text = f"{mins}m{secs}s" if mins > 0 else f"{secs}s"

        # Draw break indicator in center of block
        self.canvas.create_text(
            visual_block.x + visual_block.width // 2,
            visual_block.y + visual_block.height // 2 + 12,
            text=f"/---/ ({duration_text})",
            fill="#FFFFFF",
            font=("Arial", 8, "bold"),
            tags=(f"break_indicator_{id(visual_block)}")
        )

    def _build_timeline(self):
        """Build the visual timeline from Timeline/Block/Phase structure."""
        print(f"[DEBUG {time.time():.3f}] _build_timeline START (blocks: {len(self.timeline.blocks)})")

        # Clear existing blocks
        print(f"[DEBUG {time.time():.3f}] Clearing {len(self.blocks)} existing blocks...")
        for block in self.blocks:
            block.delete()
        self.blocks.clear()

        # Clear canvas
        print(f"[DEBUG {time.time():.3f}] Clearing canvas...")
        self.canvas.delete("all")

        # Starting position
        x = 20
        y = self.RULER_HEIGHT + 20

        # Draw time ruler
        print(f"[DEBUG {time.time():.3f}] Drawing ruler...")
        self._draw_ruler()

        # Iterate over blocks in timeline
        print(f"[DEBUG {time.time():.3f}] Creating blocks from timeline...")
        for block_idx, block in enumerate(self.timeline.blocks):
            print(f"[DEBUG {time.time():.3f}] Processing block {block_idx}: {block.name} (type={block.block_type})")

            if not block.procedure or not block.procedure.phases:
                print(f"[DEBUG {time.time():.3f}] Block {block_idx} has no procedure or phases, skipping...")
                continue

            # Handle trial-based blocks differently from simple blocks
            if block.block_type == 'trial_based':
                trial_count = block.get_trial_count()
                print(f"[DEBUG {time.time():.3f}] Trial-based block with {trial_count} trials")

                # If no trials, show procedure template once (prevents block from disappearing)
                if trial_count == 0:
                    print(f"[DEBUG {time.time():.3f}] Trial-based block has 0 trials, showing template placeholder")
                    for phase in block.procedure.phases:
                        phase_duration = phase.get_estimated_duration()
                        if phase_duration < 0:
                            phase_duration = 30.0  # Default placeholder for unknown durations

                        block_type = self._phase_to_block_type(phase)
                        visual_block = self._create_visual_block(block_type, block_idx, phase_duration, x, y)
                        # Add visual indicator that this is a template (stippled pattern)
                        visual_block.set_template_mode(True)
                        self.blocks.append(visual_block)
                        x += visual_block.width + self.BLOCK_SPACING
                else:
                    # Normal trial-based rendering: Collapse to single template with "xN" label
                    print(f"[DEBUG {time.time():.3f}] Rendering collapsed trial template with {trial_count} repetitions")

                    # Track starting position for centering the label
                    trial_start_x = x

                    # Render procedure template once (NOT in a loop)
                    for phase in block.procedure.phases:
                        phase_duration = phase.get_estimated_duration()
                        if phase_duration < 0:
                            phase_duration = 30.0  # Default placeholder for unknown durations

                        block_type = self._phase_to_block_type(phase)
                        visual_block = self._create_visual_block(block_type, block_idx, phase_duration, x, y)
                        self.blocks.append(visual_block)
                        x += visual_block.width + self.BLOCK_SPACING

                    # Calculate center position for repetition label
                    trial_end_x = x
                    trial_center_x = (trial_start_x + trial_end_x) // 2

                    # Add "xN" repetition label above the trial sequence
                    self.canvas.create_text(
                        trial_center_x,
                        y - 15,  # 15 pixels above the blocks
                        text=f"x{trial_count}",
                        fill="#FF6600",  # Orange for visibility
                        font=("Arial", 12, "bold"),
                        tags=(f"repetition_label_{block_idx}", "repetition_label")
                    )

                    # Add duration display if calculated
                    if hasattr(block, '_cached_duration') and block._cached_duration is not None:
                        from utilities.format_utils import format_duration_compact
                        duration_text = format_duration_compact(block._cached_duration)
                        self.canvas.create_text(
                            trial_center_x,
                            y + self.BLOCK_HEIGHT + 15,  # Below the blocks
                            text=f"({duration_text})",
                            fill="#666666",  # Gray for subtle display
                            font=("Arial", 9),
                            tags=(f"duration_label_{block_idx}", "duration_label")
                        )

                    # Extra spacing after the collapsed trial
                    x += self.BLOCK_SPACING

            else:
                # Simple block (single execution) - iterate through phases once
                simple_start_x = x
                for phase in block.procedure.phases:
                    phase_duration = phase.get_estimated_duration()

                    # Handle variable duration (-1)
                    if phase_duration < 0:
                        phase_duration = 30.0  # Default placeholder for unknown durations

                    block_type = self._phase_to_block_type(phase)

                    print(f"[DEBUG {time.time():.3f}] Simple block, phase={phase.name}, duration={phase_duration}s")
                    visual_block = self._create_visual_block(block_type, block_idx, phase_duration, x, y)
                    self.blocks.append(visual_block)
                    x += visual_block.width + self.BLOCK_SPACING

                # Add duration display if calculated for simple blocks too
                if hasattr(block, '_cached_duration') and block._cached_duration is not None:
                    from utilities.format_utils import format_duration_compact
                    simple_end_x = x
                    simple_center_x = (simple_start_x + simple_end_x) // 2
                    duration_text = format_duration_compact(block._cached_duration)
                    self.canvas.create_text(
                        simple_center_x,
                        y + self.BLOCK_HEIGHT + 15,  # Below the blocks
                        text=f"({duration_text})",
                        fill="#666666",  # Gray for subtle display
                        font=("Arial", 9),
                        tags=(f"duration_label_{block_idx}", "duration_label")
                    )

        # Update scroll region
        print(f"[DEBUG {time.time():.3f}] Updating scroll region...")
        self.canvas.config(scrollregion=self.canvas.bbox("all"))
        print(f"[DEBUG {time.time():.3f}] _build_timeline COMPLETE (created {len(self.blocks)} visual blocks)")

    def _draw_ruler(self):
        """Draw time ruler at the top of the timeline."""
        # Calculate total duration from timeline
        total_duration = self.timeline.get_estimated_duration()

        ruler_y = 10
        ruler_height = self.RULER_HEIGHT - 10

        # Draw ruler background
        ruler_width = self._duration_to_pixels(total_duration) + 40
        self.canvas.create_rectangle(
            0, 0, ruler_width, self.RULER_HEIGHT,
            fill="#E0E0E0",
            outline="#CCCCCC"
        )

        # Draw time markers every 10 seconds
        marker_interval = 10.0  # seconds
        x = 20
        time = 0.0

        while time <= total_duration:
            marker_x = x + self._duration_to_pixels(time)

            # Draw tick mark
            self.canvas.create_line(
                marker_x, ruler_y + ruler_height - 10,
                marker_x, ruler_y + ruler_height,
                fill="#333333",
                width=1
            )

            # Draw time label
            time_label = self._format_time(time)
            self.canvas.create_text(
                marker_x,
                ruler_y + 5,
                text=time_label,
                fill="#333333",
                font=("Arial", 8),
                anchor=tk.N
            )

            time += marker_interval

    def _duration_to_pixels(self, duration: float) -> int:
        """Convert duration in seconds to pixels."""
        return int(duration * self.PIXELS_PER_SECOND * self.zoom_level)

    def _pixels_to_duration(self, pixels: int) -> float:
        """Convert pixels to duration in seconds."""
        return pixels / (self.PIXELS_PER_SECOND * self.zoom_level)

    def _format_time(self, seconds: float) -> str:
        """Format time in seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"

    def _on_block_click(self, block: TimelineBlock):
        """Handle block click - select all phases in same block."""
        # Deselect all visual blocks
        for b in self.blocks:
            b.set_selected(False)

        # Select all visual blocks belonging to same parent Block
        block_idx = block.trial_index  # Repurposed for block index
        for b in self.blocks:
            if b.trial_index == block_idx and block_idx >= 0:
                b.set_selected(True)

        self.selected_block_index = block_idx

        # Notify callback with bounds checking
        if self.on_block_select and 0 <= block_idx < len(self.timeline.blocks):
            timeline_block = self.timeline.blocks[block_idx]
            self.on_block_select(timeline_block)
        elif block_idx >= len(self.timeline.blocks):
            # Index out of bounds - refresh timeline to fix
            print(f"Warning: Block index {block_idx} out of bounds, refreshing timeline")
            self.refresh()

    def _on_block_double_click(self, block: TimelineBlock):
        """Handle block double-click - edit block."""
        block_idx = block.trial_index  # Repurposed for block index
        if self.on_block_edit and 0 <= block_idx < len(self.timeline.blocks):
            timeline_block = self.timeline.blocks[block_idx]
            self.on_block_edit(timeline_block)

    def _show_context_menu(self, event):
        """Show right-click context menu."""
        # Check if we're over a block
        item = self.canvas.find_withtag(tk.CURRENT)
        if item:
            self.context_menu.post(event.x_root, event.y_root)

    def _edit_selected_trial(self):
        """Edit the currently selected block."""
        if (self.selected_block_index is not None and self.on_block_edit and
            0 <= self.selected_block_index < len(self.timeline.blocks)):
            block = self.timeline.blocks[self.selected_block_index]
            self.on_block_edit(block)

    def _duplicate_selected_trial(self):
        """Duplicate the currently selected block."""
        if self.selected_block_index is not None and 0 <= self.selected_block_index < len(self.timeline.blocks):
            import copy
            block = self.timeline.blocks[self.selected_block_index]
            duplicate = copy.deepcopy(block)

            # Generate unique name for the duplicate
            duplicate.name = self._generate_unique_block_name(block.name)

            self.timeline.blocks.insert(self.selected_block_index + 1, duplicate)
            self.refresh()

    def _delete_selected_trial(self):
        """Delete the currently selected block."""
        if self.selected_block_index is not None and 0 <= self.selected_block_index < len(self.timeline.blocks):
            self.timeline.blocks.pop(self.selected_block_index)
            # Update selection to avoid invalid index
            if self.selected_block_index >= len(self.timeline.blocks):
                self.selected_block_index = len(self.timeline.blocks) - 1 if self.timeline.blocks else None
            self.refresh()

    def zoom_in(self):
        """Increase zoom level."""
        new_zoom = min(self.MAX_ZOOM, self.zoom_level * 1.25)
        self.set_zoom(new_zoom)

    def zoom_out(self):
        """Decrease zoom level."""
        new_zoom = max(self.MIN_ZOOM, self.zoom_level / 1.25)
        self.set_zoom(new_zoom)

    def set_zoom(self, zoom: float):
        """Set zoom level and rebuild timeline."""
        if self._updating_zoom:
            return

        self._updating_zoom = True
        try:
            new_zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
            # Only refresh if zoom actually changed
            if abs(new_zoom - self.zoom_level) > 0.001:
                self.zoom_level = new_zoom
                self.zoom_slider.set(self.zoom_level)
                self.zoom_label.config(text=f"{int(self.zoom_level * 100)}%")
                self.refresh()
        finally:
            self._updating_zoom = False

    def _on_zoom_slider_change(self, value):
        """Handle zoom slider value change."""
        if not self._updating_zoom:
            self.set_zoom(float(value))

    def _generate_unique_block_name(self, base_name: str) -> str:
        """
        Generate a unique block name by appending a number if needed.

        Args:
            base_name: Base name to use (e.g., "Baseline")

        Returns:
            Unique name (e.g., "Baseline" or "Baseline2" if "Baseline" exists)
        """
        existing_names = {block.name for block in self.timeline.blocks}

        # If base name doesn't exist, use it as-is
        if base_name not in existing_names:
            return base_name

        # Find next available number
        counter = 2
        while f"{base_name}{counter}" in existing_names:
            counter += 1

        return f"{base_name}{counter}"

    def refresh(self):
        """Rebuild timeline from current config."""
        if self._refreshing:
            print(f"[DEBUG {time.time():.3f}] TimelineCanvas.refresh() BLOCKED (already refreshing)")
            return

        print(f"[DEBUG {time.time():.3f}] TimelineCanvas.refresh() called")
        self._refreshing = True
        try:
            self._build_timeline()
        finally:
            self._refreshing = False

    def add_trial_after_selected(self):
        """Add a new block after the currently selected block."""
        from core.execution.procedure import Procedure
        from core.execution.phases.instruction_phase import InstructionPhase

        insert_index = self.selected_block_index + 1 if self.selected_block_index is not None else len(self.timeline.blocks)

        # Create new simple block with instruction phase and unique name
        unique_name = self._generate_unique_block_name("New Block")
        new_block = Block(name=unique_name, block_type='simple')
        new_proc = Procedure("New Procedure")
        new_proc.add_phase(InstructionPhase(
            text="New instruction...",
            wait_for_key=True,
            continue_key='space'
        ))
        new_block.procedure = new_proc
        self.timeline.blocks.insert(insert_index, new_block)
        self.refresh()

    def _on_block_drag_start(self, block: TimelineBlock, block_index: int):
        """
        Handle block drag start.

        Args:
            block: The TimelineBlock being dragged
            block_index: Index of the parent Block in timeline
        """
        print(f"[DEBUG] Drag started for block at index {block_index}")
        self._dragging_block = block
        self._drag_original_index = block_index
        self._drag_current_index = block_index

    def _on_block_drag_motion(self, block: TimelineBlock, x_root: int):
        """
        Handle block drag motion - calculate potential drop position.

        Args:
            block: The TimelineBlock being dragged
            x_root: Root X coordinate of mouse
        """
        # Convert root coordinates to canvas coordinates
        canvas_x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()

        # Check if dragging outside canvas bounds (cancel drag)
        canvas_width = self.canvas.winfo_width()
        if canvas_x < 0 or canvas_x > canvas_width:
            # Outside bounds - will be handled by block's right-click or release handler
            return

        # Calculate which block index this position corresponds to
        new_index = self._calculate_drop_index(canvas_x)
        if new_index != self._drag_current_index:
            self._drag_current_index = new_index
            print(f"[DEBUG] Drag motion: potential drop at index {new_index}")

    def _on_block_drag_end(self, block: TimelineBlock):
        """
        Handle block drag end - perform reordering.

        Args:
            block: The TimelineBlock that was dragged
        """
        if self._drag_original_index is None or self._drag_current_index is None:
            # Invalid state, reset
            self._reset_drag_state()
            return

        # Check if block was dragged outside bounds
        canvas_x = self.canvas.winfo_pointerx() - self.canvas.winfo_rootx()
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        canvas_y = self.canvas.winfo_pointery() - self.canvas.winfo_rooty()

        if canvas_x < -50 or canvas_x > canvas_width + 50 or canvas_y < -50 or canvas_y > canvas_height + 50:
            # Dragged far outside bounds - cancel drag
            print(f"[DEBUG] Drag cancelled: outside bounds")
            block.set_position(block._original_x, block._original_y)
            self._reset_drag_state()
            return

        old_index = self._drag_original_index
        new_index = self._calculate_drop_index(canvas_x)

        print(f"[DEBUG] Drag ended: reordering from {old_index} to {new_index}")

        if old_index != new_index and 0 <= new_index < len(self.timeline.blocks):
            # Perform reordering in timeline data model
            block_to_move = self.timeline.blocks.pop(old_index)
            self.timeline.blocks.insert(new_index, block_to_move)

            # Refresh visual timeline
            self.refresh()

            # Update selection to follow the moved block
            self.selected_block_index = new_index
        else:
            # No reordering needed or invalid index - just refresh to restore positions
            self.refresh()

        self._reset_drag_state()

    def _calculate_drop_index(self, canvas_x: int) -> int:
        """
        Calculate which block index corresponds to a canvas X position.

        Args:
            canvas_x: X coordinate on canvas

        Returns:
            Block index where drop would occur
        """
        # Find which block the X coordinate falls into
        # Skip visual blocks that belong to the dragged timeline block
        for idx, visual_block in enumerate(self.blocks):
            # Skip blocks belonging to the dragged timeline block
            if visual_block.trial_index == self._drag_original_index:
                continue

            # Check if X is within this block's bounds (before its midpoint)
            if canvas_x < visual_block.x + visual_block.width // 2:
                return visual_block.trial_index

        # If past all blocks, return last position
        return len(self.timeline.blocks)

    def _reset_drag_state(self):
        """Reset drag state after drag operation completes or cancels."""
        self._dragging_block = None
        self._drag_original_index = None
        self._drag_current_index = None
