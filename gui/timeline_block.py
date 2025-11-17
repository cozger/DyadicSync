"""
Timeline block widget representing trial phases in the visual timeline.
"""

import tkinter as tk
from tkinter import Canvas
from enum import Enum
from typing import Optional, Callable


class BlockType(Enum):
    """Types of blocks that can appear in the timeline."""
    WELCOME = "welcome"
    BASELINE = "baseline"
    FIXATION = "fixation"
    VIDEO = "video"
    RATING = "rating"


# Color scheme for E-Prime style blocks
BLOCK_COLORS = {
    BlockType.WELCOME: "#4A90E2",     # Blue
    BlockType.BASELINE: "#F5A623",    # Orange/Yellow
    BlockType.FIXATION: "#7ED321",    # Green
    BlockType.VIDEO: "#D0021B",       # Red
    BlockType.RATING: "#BD10E0"       # Purple
}

BLOCK_TEXT_COLOR = {
    BlockType.WELCOME: "#FFFFFF",
    BlockType.BASELINE: "#FFFFFF",
    BlockType.FIXATION: "#FFFFFF",
    BlockType.VIDEO: "#FFFFFF",
    BlockType.RATING: "#FFFFFF"
}


class TimelineBlock:
    """
    Visual representation of a trial phase block in the timeline.

    A trial consists of multiple blocks: Fixation → Video → Rating
    """

    def __init__(self, canvas: Canvas, block_type: BlockType, trial_index: int,
                 x: int, y: int, width: int, height: int = 60,
                 on_click: Optional[Callable] = None,
                 on_double_click: Optional[Callable] = None):
        """
        Initialize a timeline block.

        Args:
            canvas: Tkinter Canvas to draw on
            block_type: Type of block (welcome, baseline, fixation, video, rating)
            trial_index: Index of the trial this block belongs to (-1 for welcome/baseline)
            x: X coordinate of block's left edge
            y: Y coordinate of block's top edge
            width: Width of block in pixels
            height: Height of block in pixels
            on_click: Callback function when block is clicked
            on_double_click: Callback function when block is double-clicked
        """
        self.canvas = canvas
        self.block_type = block_type
        self.trial_index = trial_index
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.on_click = on_click
        self.on_double_click = on_double_click

        self.selected = False
        self.hovered = False

        # Canvas item IDs
        self.rect_id = None
        self.text_id = None
        self.duration_text_id = None

        self._draw()

    def _draw(self):
        """Draw the block on the canvas."""
        # Determine color based on selection and hover state
        base_color = BLOCK_COLORS[self.block_type]
        text_color = BLOCK_TEXT_COLOR[self.block_type]

        fill_color = base_color
        outline_color = "#333333"
        outline_width = 1

        if self.selected:
            outline_color = "#FFD700"  # Gold outline for selected
            outline_width = 3
        elif self.hovered:
            # Lighten color on hover
            fill_color = self._lighten_color(base_color)

        # Draw rectangle
        self.rect_id = self.canvas.create_rectangle(
            self.x, self.y,
            self.x + self.width, self.y + self.height,
            fill=fill_color,
            outline=outline_color,
            width=outline_width,
            tags=("block", f"block_{self.trial_index}_{self.block_type.value}")
        )

        # Draw label text
        label = self._get_label()
        self.text_id = self.canvas.create_text(
            self.x + self.width // 2,
            self.y + self.height // 2 - 8,
            text=label,
            fill=text_color,
            font=("Arial", 10, "bold"),
            tags=("block_text", f"text_{self.trial_index}_{self.block_type.value}")
        )

        # Draw duration text (if applicable)
        duration = self._get_duration_text()
        if duration:
            self.duration_text_id = self.canvas.create_text(
                self.x + self.width // 2,
                self.y + self.height // 2 + 10,
                text=duration,
                fill=text_color,
                font=("Arial", 8),
                tags=("duration_text", f"duration_{self.trial_index}_{self.block_type.value}")
            )

        # Bind events
        self.canvas.tag_bind(self.rect_id, "<Button-1>", self._handle_click)
        self.canvas.tag_bind(self.text_id, "<Button-1>", self._handle_click)
        self.canvas.tag_bind(self.rect_id, "<Double-Button-1>", self._handle_double_click)
        self.canvas.tag_bind(self.text_id, "<Double-Button-1>", self._handle_double_click)
        self.canvas.tag_bind(self.rect_id, "<Enter>", self._handle_enter)
        self.canvas.tag_bind(self.text_id, "<Enter>", self._handle_enter)
        self.canvas.tag_bind(self.rect_id, "<Leave>", self._handle_leave)
        self.canvas.tag_bind(self.text_id, "<Leave>", self._handle_leave)

    def _get_label(self) -> str:
        """Get display label for this block."""
        if self.block_type == BlockType.WELCOME:
            return "Welcome"
        elif self.block_type == BlockType.BASELINE:
            return "Baseline"
        elif self.block_type == BlockType.FIXATION:
            return f"Trial {self.trial_index + 1}: Fixation"
        elif self.block_type == BlockType.VIDEO:
            return f"Trial {self.trial_index + 1}: Video"
        elif self.block_type == BlockType.RATING:
            return f"Trial {self.trial_index + 1}: Rating"
        return ""

    def _get_duration_text(self) -> str:
        """Get duration display text (placeholder for now)."""
        # This will be filled in with actual durations from config
        return ""

    def _lighten_color(self, hex_color: str, factor: float = 0.2) -> str:
        """Lighten a hex color by a factor."""
        # Remove '#' if present
        hex_color = hex_color.lstrip('#')

        # Convert to RGB
        r = int(hex_color[0:2], 16)
        g = int(hex_color[2:4], 16)
        b = int(hex_color[4:6], 16)

        # Lighten
        r = min(255, int(r + (255 - r) * factor))
        g = min(255, int(g + (255 - g) * factor))
        b = min(255, int(b + (255 - b) * factor))

        return f"#{r:02x}{g:02x}{b:02x}"

    def _update_colors(self):
        """Update block colors based on state (selected/hovered) without redrawing."""
        base_color = BLOCK_COLORS[self.block_type]

        if self.selected:
            outline_color = "#FFD700"  # Gold
            outline_width = 3
            fill_color = base_color
        elif self.hovered:
            outline_color = "#333333"
            outline_width = 1
            fill_color = self._lighten_color(base_color)
        else:
            outline_color = "#333333"
            outline_width = 1
            fill_color = base_color

        # Update existing items without redrawing
        if self.rect_id:
            self.canvas.itemconfig(self.rect_id, fill=fill_color, outline=outline_color, width=outline_width)

    def _handle_click(self, event):
        """Handle single click event."""
        if self.on_click:
            self.on_click(self)

    def _handle_double_click(self, event):
        """Handle double click event."""
        if self.on_double_click:
            self.on_double_click(self)

    def _handle_enter(self, event):
        """Handle mouse enter event."""
        self.hovered = True
        # Just update colors, don't redraw (prevents event handler deadlock)
        self._update_colors()

    def _handle_leave(self, event):
        """Handle mouse leave event."""
        self.hovered = False
        # Just update colors, don't redraw (prevents event handler deadlock)
        self._update_colors()

    def set_selected(self, selected: bool):
        """
        Set selection state of this block.

        Args:
            selected: True to select, False to deselect
        """
        if self.selected != selected:
            self.selected = selected
            # Just update colors, don't redraw (more efficient)
            self._update_colors()

    def set_template_mode(self, is_template: bool = True):
        """
        Set block to template mode (dimmed appearance for trial-based blocks with no trials).

        Args:
            is_template: True to show as template, False for normal appearance
        """
        if is_template and self.rect_id:
            # Use stipple pattern to indicate template/placeholder
            self.canvas.itemconfig(self.rect_id, stipple='gray50')
            # Add text indicator
            if self.text_id:
                current_text = self.canvas.itemcget(self.text_id, 'text')
                self.canvas.itemconfig(self.text_id, text=f"{current_text} (Template)")

    def set_position(self, x: int, y: int):
        """
        Move block to new position.

        Args:
            x: New X coordinate
            y: New Y coordinate
        """
        dx = x - self.x
        dy = y - self.y

        self.x = x
        self.y = y

        # Move canvas items
        self.canvas.move(self.rect_id, dx, dy)
        self.canvas.move(self.text_id, dx, dy)
        if self.duration_text_id:
            self.canvas.move(self.duration_text_id, dx, dy)

    def set_width(self, width: int):
        """
        Update block width.

        Args:
            width: New width in pixels
        """
        self.width = width
        self.redraw()

    def redraw(self):
        """Redraw the block (useful after state changes)."""
        # Unbind events before deleting to prevent memory leaks
        event_types = ["<Button-1>", "<Double-Button-1>", "<Enter>", "<Leave>"]

        if self.rect_id:
            for event_type in event_types:
                try:
                    self.canvas.tag_unbind(self.rect_id, event_type)
                except Exception:
                    pass  # Ignore if binding doesn't exist

        if self.text_id:
            for event_type in event_types:
                try:
                    self.canvas.tag_unbind(self.text_id, event_type)
                except Exception:
                    pass

        if self.duration_text_id:
            for event_type in event_types:
                try:
                    self.canvas.tag_unbind(self.duration_text_id, event_type)
                except Exception:
                    pass

        # Delete old elements
        self.canvas.delete(self.rect_id)
        self.canvas.delete(self.text_id)
        if self.duration_text_id:
            self.canvas.delete(self.duration_text_id)

        # Redraw
        self._draw()

    def delete(self):
        """Remove this block from the canvas."""
        # Unbind events before deleting
        event_types = ["<Button-1>", "<Double-Button-1>", "<Enter>", "<Leave>"]

        if self.rect_id:
            for event_type in event_types:
                try:
                    self.canvas.tag_unbind(self.rect_id, event_type)
                except Exception:
                    pass

        if self.text_id:
            for event_type in event_types:
                try:
                    self.canvas.tag_unbind(self.text_id, event_type)
                except Exception:
                    pass

        if self.duration_text_id:
            for event_type in event_types:
                try:
                    self.canvas.tag_unbind(self.duration_text_id, event_type)
                except Exception:
                    pass

        # Delete canvas items
        self.canvas.delete(self.rect_id)
        self.canvas.delete(self.text_id)
        if self.duration_text_id:
            self.canvas.delete(self.duration_text_id)
