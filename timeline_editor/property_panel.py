"""
Property panel for displaying and editing block properties.

Redesigned for hierarchical block-based experiment structure.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from core.execution.block import Block
from core.execution.branch_block import BranchBlock
from gui.phase_widgets import PhasePropertyEditor
from gui.block_widgets import (
    BlockInfoEditor,
    ProcedureListWidget,
    TrialListConfigEditor,
    RandomizationConfigEditor,
    TemplateVariableValidator,
    BranchBlockInfoEditor,
    SelectionConfigEditor,
    VariantListWidget
)


class PropertyPanel(ttk.Frame):
    """
    Panel for editing properties of the selected block.

    Supports:
    - Block information (name, type)
    - Procedure editing (phase list)
    - Phase property editing
    - Trial list configuration (for trial_based blocks)
    - Randomization settings (for trial_based blocks)
    - Template variable validation
    - Branch block editing (variants, selection config)
    """

    def __init__(self, parent, timeline=None, on_change: Optional[callable] = None):
        """
        Initialize property panel.

        Args:
            parent: Parent widget
            timeline: Timeline object (for name validation)
            on_change: Callback when properties change
        """
        super().__init__(parent, relief=tk.RAISED, borderwidth=1)

        self.timeline = timeline
        self.on_change = on_change
        self._current_block = None  # Can be Block or BranchBlock
        self._configure_scheduled_block = False  # Flag to prevent Configure loop for block section
        self._configure_scheduled_phase = False  # Flag to prevent Configure loop for phase section

        # Title with validation indicator
        title_frame = ttk.Frame(self)
        title_frame.pack(fill=tk.X, padx=10, pady=10)

        self.title_label = ttk.Label(
            title_frame,
            text="Block Properties",
            font=("Arial", 12, "bold")
        )
        self.title_label.pack(side=tk.LEFT)

        self.validation_label = ttk.Label(
            title_frame,
            text="",
            font=("Arial", 16)
        )
        self.validation_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Create horizontal PanedWindow for side-by-side layout
        # Using tk.PanedWindow (not ttk) because it supports minsize parameter
        self.paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=5, bg='#E0E0E0')

        # Left pane: Block Info section
        left_pane = ttk.Frame(self.paned_window, relief=tk.SUNKEN, borderwidth=1)
        left_pane.pack_propagate(True)  # Ensure geometry propagation is enabled
        self.paned_window.add(left_pane, stretch='always', minsize=400)  # Expands with window, min 400px to keep all elements visible

        # Create scrollable canvas for left pane (with initial minimum width)
        self.block_canvas = tk.Canvas(left_pane, bg="#FFFFFF", width=200, highlightthickness=0)
        self.block_scrollbar = ttk.Scrollbar(left_pane, orient=tk.VERTICAL, command=self.block_canvas.yview)
        self.block_scrollable_frame = ttk.Frame(self.block_canvas)
        self.block_scrollable_frame.bind("<Configure>", self._on_configure_block_section)
        # Store window ID so we can update its width during resize
        self.block_canvas_window = self.block_canvas.create_window((0, 0), window=self.block_scrollable_frame, anchor=tk.NW)
        self.block_canvas.configure(yscrollcommand=self.block_scrollbar.set)

        # Pack left pane components
        self.block_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.block_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind left pane resize to update canvas width dynamically
        left_pane.bind("<Configure>", lambda e: self._on_left_pane_resize(e))

        # Enable mousewheel scrolling for left pane
        # Using widget-specific bind() instead of bind_all() to avoid destroying other widget bindings
        self.block_canvas.bind("<Enter>", self._on_block_canvas_enter)
        self.block_canvas.bind("<Leave>", self._on_block_canvas_leave)

        # Right pane: Phase Properties section
        right_pane = ttk.Frame(self.paned_window, relief=tk.SUNKEN, borderwidth=1)
        right_pane.pack_propagate(True)  # Ensure geometry propagation is enabled
        self.paned_window.add(right_pane, stretch='always', minsize=560)  # Expands with window, min 560px to keep all elements visible

        # Create scrollable canvas for right pane (with initial minimum width)
        self.phase_canvas = tk.Canvas(right_pane, bg="#FFFFFF", width=200, highlightthickness=0)
        self.phase_scrollbar = ttk.Scrollbar(right_pane, orient=tk.VERTICAL, command=self.phase_canvas.yview)
        self.phase_scrollable_frame = ttk.Frame(self.phase_canvas)
        self.phase_scrollable_frame.bind("<Configure>", self._on_configure_phase_section)
        # Store window ID so we can update its width during resize
        self.phase_canvas_window = self.phase_canvas.create_window((0, 0), window=self.phase_scrollable_frame, anchor=tk.NW)
        self.phase_canvas.configure(yscrollcommand=self.phase_scrollbar.set)

        # Header for phase properties (inside scrollable frame, will be added when content loads)
        self.phase_header = ttk.Label(
            self.phase_scrollable_frame,
            text="Phase Properties",
            font=("Arial", 10, "bold"),
            background="#FFFFFF"
        )
        self.phase_header.pack(fill=tk.X, padx=10, pady=10)

        # Pack right pane components
        self.phase_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.phase_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind right pane resize to update canvas width dynamically
        right_pane.bind("<Configure>", lambda e: self._on_right_pane_resize(e))

        # Enable mousewheel scrolling for right pane
        # Using widget-specific bind() instead of bind_all() to avoid destroying other widget bindings
        self.phase_canvas.bind("<Enter>", self._on_phase_canvas_enter)
        self.phase_canvas.bind("<Leave>", self._on_phase_canvas_leave)

        # Create editor widgets (will be shown/hidden dynamically)
        self._create_editors()

        # No selection message
        self.no_selection_label = ttk.Label(
            self,
            text="No block selected.\n\nClick on a block in the timeline to edit its properties.",
            justify=tk.CENTER,
            font=("Arial", 10, "italic")
        )

        self._show_no_selection()

    def _create_editors(self):
        """Create all editor widgets."""
        # Widgets for left pane (Block Info section)
        block_container = self.block_scrollable_frame

        # Block Info Editor
        self.block_info_editor = BlockInfoEditor(
            block_container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            timeline=self.timeline,
            on_change=self._handle_change
        )
        # Don't pack yet

        # Separator
        self.separator1 = ttk.Separator(block_container, orient=tk.HORIZONTAL)

        # Widgets for right pane (Phase Properties section)
        phase_container = self.phase_scrollable_frame

        # Phase Property Editor (for selected phase)
        self.phase_editor = PhasePropertyEditor(
            phase_container,
            on_change=self._handle_change
        )

        # Procedure List Widget (in left pane, but connected to phase editor in right pane)
        self.procedure_widget = ProcedureListWidget(
            block_container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            phase_editor=self.phase_editor,
            on_change=self._handle_change
        )

        # Separator
        self.separator2 = ttk.Separator(block_container, orient=tk.HORIZONTAL)

        # Trial List Config Editor (only for trial_based blocks)
        self.trial_list_editor = TrialListConfigEditor(
            block_container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            on_change=self._handle_change,
            block_info_editor=self.block_info_editor,  # For refreshing stats after duration calc
            on_duration_calculated=self._refresh_display_only,  # For canvas refresh after duration calc
            timeline=self.timeline
        )

        # Separator
        self.separator3 = ttk.Separator(block_container, orient=tk.HORIZONTAL)

        # Randomization Config Editor (only for trial_based blocks)
        self.randomization_editor = RandomizationConfigEditor(
            block_container,
            block=Block("Placeholder", 'trial_based'),  # Dummy block
            on_change=self._handle_change
        )

        # Separator
        self.separator4 = ttk.Separator(block_container, orient=tk.HORIZONTAL)

        # Validation warnings
        self.validation_frame = ttk.Frame(block_container)
        self.validation_text = tk.Text(
            self.validation_frame,
            height=3,
            wrap=tk.WORD,
            bg='#FFF3CD',
            fg='#856404',
            font=('Arial', 9),
            relief=tk.FLAT,
            state=tk.DISABLED
        )

        # === Branch Block Editors ===
        # Branch Block Info Editor
        self.branch_info_editor = BranchBlockInfoEditor(
            block_container,
            branch_block=BranchBlock("Placeholder"),  # Dummy
            timeline=self.timeline,
            on_change=self._handle_change
        )

        # Separator for branch block
        self.branch_separator1 = ttk.Separator(block_container, orient=tk.HORIZONTAL)

        # Variant List Widget
        self.variant_list_widget = VariantListWidget(
            block_container,
            branch_block=BranchBlock("Placeholder"),  # Dummy
            on_change=self._handle_change,
            on_variant_select=self._on_variant_select,
            timeline=self.timeline  # For extract operation
        )

        # Separator for branch block
        self.branch_separator2 = ttk.Separator(block_container, orient=tk.HORIZONTAL)

        # Selection Config Editor
        self.selection_editor = SelectionConfigEditor(
            block_container,
            branch_block=BranchBlock("Placeholder"),  # Dummy
            on_change=self._handle_change
        )

        # Branch block trial list (shared)
        self.branch_separator3 = ttk.Separator(block_container, orient=tk.HORIZONTAL)
        self.branch_trial_list_editor = TrialListConfigEditor(
            block_container,
            block=Block("Placeholder", 'trial_based'),  # Dummy
            on_change=self._handle_change,
            timeline=self.timeline
        )

        # Currently selected variant (for phase editing)
        self._selected_variant: Optional[Block] = None

    def _on_configure_block_section(self, event):
        """Handle configure event for block section (debounced)."""
        if not self._configure_scheduled_block:
            self._configure_scheduled_block = True
            self.after(10, self._update_block_scroll_region)

    def _update_block_scroll_region(self):
        """Update scroll region for block section (debounced)."""
        self.block_canvas.configure(scrollregion=self.block_canvas.bbox("all"))
        self._configure_scheduled_block = False

    def _on_configure_phase_section(self, event):
        """Handle configure event for phase section (debounced)."""
        if not self._configure_scheduled_phase:
            self._configure_scheduled_phase = True
            self.after(10, self._update_phase_scroll_region)

    def _update_phase_scroll_region(self):
        """Update scroll region for phase section (debounced)."""
        self.phase_canvas.configure(scrollregion=self.phase_canvas.bbox("all"))
        self._configure_scheduled_phase = False

    def _on_mousewheel_block(self, event):
        """Handle mousewheel scrolling for block section."""
        self.block_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_mousewheel_phase(self, event):
        """Handle mousewheel scrolling for phase section."""
        self.phase_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_block_canvas_enter(self, event):
        """
        Bind mousewheel to block canvas when mouse enters.

        Uses widget-specific bind() instead of bind_all() to preserve
        mousewheel bindings of child widgets (Listbox, Combobox, etc.).
        """
        self.block_canvas.bind("<MouseWheel>", self._on_mousewheel_block)

    def _on_block_canvas_leave(self, event):
        """
        Unbind mousewheel from block canvas when mouse leaves.

        Uses widget-specific unbind() instead of unbind_all() to preserve
        mousewheel bindings of child widgets.
        """
        self.block_canvas.unbind("<MouseWheel>")

    def _on_phase_canvas_enter(self, event):
        """
        Bind mousewheel to phase canvas when mouse enters.

        Uses widget-specific bind() instead of bind_all() to preserve
        mousewheel bindings of child widgets (Listbox, Combobox, etc.).
        """
        self.phase_canvas.bind("<MouseWheel>", self._on_mousewheel_phase)

    def _on_phase_canvas_leave(self, event):
        """
        Unbind mousewheel from phase canvas when mouse leaves.

        Uses widget-specific unbind() instead of unbind_all() to preserve
        mousewheel bindings of child widgets.
        """
        self.phase_canvas.unbind("<MouseWheel>")

    def _on_left_pane_resize(self, event):
        """
        Handle left pane resize - update canvas width to fill pane.

        NOTE: This Configure binding is necessary and follows Tkinter best practices.
        When a Frame is placed inside a Canvas using create_window(), the Frame does not
        automatically track the Canvas's size changes. The Frame sizes itself based on its
        children, not its parent. This binding explicitly updates the Canvas width to match
        the parent frame's width whenever a resize occurs.

        This is the recommended solution from official Tkinter documentation and community
        consensus (TkDocs, Stack Overflow). There is no automatic alternative.
        """
        # Account for scrollbar width (typically ~17 pixels)
        scrollbar_width = self.block_scrollbar.winfo_width() if self.block_scrollbar.winfo_width() > 1 else 17
        new_width = max(100, event.width - scrollbar_width - 4)  # -4 for padding/border
        # Update both the Canvas widget width AND the embedded frame width
        self.block_canvas.config(width=new_width)
        self.block_canvas.itemconfigure(self.block_canvas_window, width=new_width)

    def _on_right_pane_resize(self, event):
        """
        Handle right pane resize - update canvas width to fill pane.

        See _on_left_pane_resize() for detailed explanation of why this binding is necessary.
        """
        # Account for scrollbar width (typically ~17 pixels)
        scrollbar_width = self.phase_scrollbar.winfo_width() if self.phase_scrollbar.winfo_width() > 1 else 17
        new_width = max(100, event.width - scrollbar_width - 4)  # -4 for padding/border
        # Update both the Canvas widget width AND the embedded frame width
        self.phase_canvas.config(width=new_width)
        self.phase_canvas.itemconfigure(self.phase_canvas_window, width=new_width)

    def _show_no_selection(self):
        """Show the 'no selection' message."""
        self.paned_window.pack_forget()
        self.no_selection_label.pack(expand=True)

    def _show_editor(self):
        """Show the property editor."""
        self.no_selection_label.pack_forget()
        self.paned_window.pack(fill=tk.BOTH, expand=True)

    def _handle_change(self):
        """Handle property change."""
        # Sync branch block trial list from wrapper if applicable
        if (self._current_block and isinstance(self._current_block, BranchBlock)
                and hasattr(self, '_branch_trial_wrapper')):
            self._current_block.trial_list = self._branch_trial_wrapper.trial_list

        # Refresh validation
        if self._current_block:
            if isinstance(self._current_block, BranchBlock):
                # Refresh branch block stats
                self.branch_info_editor.refresh_stats()
                self.selection_editor.refresh()
            else:
                self._update_validation()
                # Refresh stats in block info editor
                self.block_info_editor.refresh_stats()

        if self.on_change:
            self.on_change()

    def _refresh_display_only(self):
        """
        Refresh the display without invalidating the duration cache.

        Used after duration calculation to update the timeline canvas
        without triggering another cache invalidation.
        """
        if self.on_change:
            self.on_change()

    def _on_variant_select(self, variant: Block):
        """Handle variant selection in branch block - load variant's procedure for editing."""
        self._selected_variant = variant
        if variant and variant.procedure:
            # Update procedure widget to show variant's procedure
            self.procedure_widget.block = variant
            self.procedure_widget.refresh()
            # Clear phase selection
            self.phase_editor.load_phase(None)

    def load_block(self, block):
        """
        Load a block for editing.

        Args:
            block: Block or BranchBlock object to edit
        """
        self._current_block = block

        # Clear any previous state
        self._hide_all_editors()

        # Handle BranchBlock
        if isinstance(block, BranchBlock):
            self._load_branch_block(block)
            return

        # Handle regular Block
        self._load_regular_block(block)

    def _hide_all_editors(self):
        """Hide all editor widgets."""
        # Regular block editors
        self.block_info_editor.pack_forget()
        self.separator1.pack_forget()
        self.procedure_widget.pack_forget()
        self.separator2.pack_forget()
        self.trial_list_editor.pack_forget()
        self.separator3.pack_forget()
        self.randomization_editor.pack_forget()
        self.validation_frame.pack_forget()

        # Branch block editors
        self.branch_info_editor.pack_forget()
        self.branch_separator1.pack_forget()
        self.variant_list_widget.pack_forget()
        self.branch_separator2.pack_forget()
        self.selection_editor.pack_forget()
        self.branch_separator3.pack_forget()
        self.branch_trial_list_editor.pack_forget()

    def _load_regular_block(self, block: Block):
        """Load a regular Block for editing."""
        # Calculate duration if block has CSV trial list and duration not cached
        if (block.trial_list and block.trial_list.source and
            block.trial_list.source_type == 'csv' and
            not (hasattr(block, '_cached_duration') and block._cached_duration is not None)):
            print(f"[PROPERTY_PANEL] Calculating duration for block: {block.name}")
            block.calculate_accurate_duration()

        # Update title
        self.title_label.config(text=f"Block: {block.name}")

        # Show editor
        self._show_editor()

        # Update block reference in all editors
        self.block_info_editor.load_block(block)
        self.procedure_widget.block = block
        self.trial_list_editor.block = block
        self.randomization_editor.block = block

        # Load block info in left pane
        self.block_info_editor.pack(fill=tk.X, padx=10, pady=5)

        # Load procedure
        self.separator1.pack(fill=tk.X, padx=10, pady=10)
        self.procedure_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.procedure_widget.refresh()

        # Show/hide trial-based widgets based on block type
        if block.block_type == 'trial_based':
            self.separator2.pack(fill=tk.X, padx=10, pady=10)
            self.trial_list_editor.pack(fill=tk.X, padx=10, pady=5)
            self.trial_list_editor.refresh()

            self.separator3.pack(fill=tk.X, padx=10, pady=10)
            self.randomization_editor.pack(fill=tk.X, padx=10, pady=5)
            self.randomization_editor.refresh()

        # Validation frame
        self._update_validation()

        # Load phase editor in right pane
        self.phase_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.phase_editor.load_phase(None)

        # Force update scroll regions
        self.after(50, self._update_block_scroll_region)
        self.after(50, self._update_phase_scroll_region)

    def _load_branch_block(self, branch_block: BranchBlock):
        """Load a BranchBlock for editing."""
        # Update title
        self.title_label.config(text=f"Branch Block: {branch_block.name}")

        # Show editor
        self._show_editor()

        # Update branch block reference in editors
        self.branch_info_editor.branch_block = branch_block
        self.branch_info_editor._original_name = branch_block.name
        self.branch_info_editor.name_var.set(branch_block.name)
        self.branch_info_editor.refresh_stats()

        self.variant_list_widget.branch_block = branch_block
        self.variant_list_widget.timeline = self.timeline  # Update timeline reference for extract operation
        self.variant_list_widget.refresh()

        self.selection_editor.branch_block = branch_block
        self.selection_editor.refresh()

        # Pack branch block editors
        self.branch_info_editor.pack(fill=tk.X, padx=10, pady=5)

        self.branch_separator1.pack(fill=tk.X, padx=10, pady=10)
        self.variant_list_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.branch_separator2.pack(fill=tk.X, padx=10, pady=10)
        self.selection_editor.pack(fill=tk.X, padx=10, pady=5)

        # Shared trial list - always show so user can load a CSV
        # Create a wrapper block that syncs trial_list with the branch block
        self._branch_trial_wrapper = Block("Shared Trial List", 'trial_based')
        self._branch_trial_wrapper.trial_list = branch_block.trial_list
        self._branch_trial_wrapper_branch = branch_block  # Reference for syncing back
        self.branch_trial_list_editor.block = self._branch_trial_wrapper
        self.branch_separator3.pack(fill=tk.X, padx=10, pady=10)
        self.branch_trial_list_editor.pack(fill=tk.X, padx=10, pady=5)
        self.branch_trial_list_editor.refresh()

        # Set up procedure widget for variant editing
        # Initially show first variant's procedure if available
        self._selected_variant = None
        if branch_block.variant_blocks:
            first_variant = branch_block.variant_blocks[0]
            self._selected_variant = first_variant
            self.procedure_widget.block = first_variant
            self.separator1.pack(fill=tk.X, padx=10, pady=10)
            self.procedure_widget.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
            self.procedure_widget.refresh()
            # Programmatically select first variant in listbox for visual feedback
            self.variant_list_widget.variant_listbox.selection_set(0)
            self.variant_list_widget._selected_variant_index = 0

        # Phase editor in right pane
        self.phase_editor.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.phase_editor.load_phase(None)

        # Update validation icon (green for branch blocks)
        self.validation_label.config(text="⎇", foreground='#2ECC71')

        # Force update scroll regions
        self.after(50, self._update_block_scroll_region)
        self.after(50, self._update_phase_scroll_region)

    def _update_validation(self):
        """Update validation warnings."""
        if not self._current_block:
            return

        warnings = TemplateVariableValidator.validate(self._current_block)

        if warnings:
            # Show validation frame
            self.validation_frame.pack(fill=tk.X, padx=10, pady=5)
            self.validation_text.pack(fill=tk.X, padx=5, pady=5)

            # Update text
            self.validation_text.config(state=tk.NORMAL)
            self.validation_text.delete('1.0', tk.END)
            self.validation_text.insert('1.0', "⚠ Validation Warnings:\n" + "\n".join(f"• {w}" for w in warnings))
            self.validation_text.config(state=tk.DISABLED)

            # Update icon in title
            self.validation_label.config(text="⚠", foreground='orange')
        else:
            # Hide validation frame
            self.validation_frame.pack_forget()

            # Update icon in title
            self.validation_label.config(text="✓", foreground='green')

    def clear(self):
        """Clear the property panel."""
        self._current_block = None
        self._selected_variant = None
        self.title_label.config(text="Block Properties")
        self.validation_label.config(text="")

        # Hide all editors
        self._hide_all_editors()
        self.phase_editor.pack_forget()

        self._show_no_selection()


# Backward compatibility alias (for any code still referencing load_trial)
# This will raise a clear error if old code tries to use it
def _deprecated_load_trial(self, trial):
    raise NotImplementedError(
        "PropertyPanel.load_trial() is deprecated. "
        "Use PropertyPanel.load_block() instead. "
        "The PropertyPanel has been redesigned for block-based experiments."
    )

PropertyPanel.load_trial = _deprecated_load_trial
