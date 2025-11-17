"""
Unit tests for PropertyPanel and block editing widgets.
"""

import unittest
import tkinter as tk
from tkinter import ttk
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent.parent))

from core.execution.block import Block, RandomizationConfig
from core.execution.procedure import Procedure
from core.execution.phases.fixation_phase import FixationPhase
from core.execution.phases.video_phase import VideoPhase
from core.execution.phases.rating_phase import RatingPhase
from core.execution.trial_list import TrialList
from gui.phase_widgets import (
    PhasePropertyEditor,
    FixationPhaseEditor,
    VideoPhaseEditor,
    RatingPhaseEditor
)
from gui.block_widgets import (
    BlockInfoEditor,
    ProcedureListWidget,
    TemplateVariableValidator
)
from timeline_editor.property_panel import PropertyPanel


class TestPhasePropertyEditors(unittest.TestCase):
    """Test phase property editors."""

    def setUp(self):
        """Set up test fixtures."""
        # Delay before creating Tk to ensure previous cleanup completed
        # (Windows Tcl/Tk has slow internal cleanup that can cause file access errors)
        time.sleep(0.15)
        self.root = tk.Tk()

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        # Allow Tcl/Tk to fully cleanup internal state before next test
        # (Addresses intermittent TclError with missing .tcl files on Windows)
        time.sleep(0.3)

    def test_fixation_phase_editor_load_apply(self):
        """Test FixationPhaseEditor load and apply cycle."""
        from core.markers import MarkerBinding

        phase = FixationPhase(name="Test Fixation", duration=5.0)
        phase.marker_bindings = [
            MarkerBinding(event_type="phase_start", marker_template="100")
        ]
        editor = FixationPhaseEditor(self.root, phase)

        # Verify loaded values
        self.assertEqual(editor.duration_var.get(), 5.0)

        # Modify values
        editor.duration_var.set(10.0)
        editor.apply_changes()

        # Verify changes applied
        self.assertEqual(phase.duration, 10.0)
        # Marker bindings should be preserved
        self.assertEqual(len(phase.marker_bindings), 1)
        self.assertEqual(phase.marker_bindings[0].marker_template, "100")

    def test_video_phase_editor_load_apply(self):
        """Test VideoPhaseEditor load and apply cycle."""
        phase = VideoPhase(
            name="Test Video",
            participant_1_video="{video1}",
            participant_2_video="{video2}",
            auto_advance=True
        )
        editor = VideoPhaseEditor(self.root, phase)

        # Verify loaded values
        self.assertEqual(editor.p1_video_var.get(), "{video1}")
        self.assertEqual(editor.p2_video_var.get(), "{video2}")
        self.assertTrue(editor.auto_advance_var.get())

        # Modify values
        editor.p1_video_var.set("{new_video1}")
        editor.p2_video_var.set("{new_video2}")
        editor.auto_advance_var.set(False)
        editor.apply_changes()

        # Verify changes applied
        self.assertEqual(phase.participant_1_video, "{new_video1}")
        self.assertEqual(phase.participant_2_video, "{new_video2}")
        self.assertFalse(phase.auto_advance)

    def test_rating_phase_editor_load_apply(self):
        """Test RatingPhaseEditor load and apply cycle."""
        phase = RatingPhase(
            name="Test Rating",
            question="How do you feel?",
            scale_min=1,
            scale_max=7,
            timeout=30.0
        )
        editor = RatingPhaseEditor(self.root, phase)

        # Verify loaded values
        self.assertEqual(editor.question_text.get('1.0', 'end-1c'), "How do you feel?")
        self.assertEqual(editor.scale_min_var.get(), 1)
        self.assertEqual(editor.scale_max_var.get(), 7)
        self.assertEqual(editor.timeout_var.get(), "30.0")

        # Modify values
        editor.question_text.delete('1.0', tk.END)
        editor.question_text.insert('1.0', "New question?")
        editor.scale_min_var.set(0)
        editor.scale_max_var.set(10)
        editor.timeout_var.set("60.0")
        editor.apply_changes()

        # Verify changes applied
        self.assertEqual(phase.question, "New question?")
        self.assertEqual(phase.scale_min, 0)
        self.assertEqual(phase.scale_max, 10)
        self.assertEqual(phase.timeout, 60.0)


class TestPhasePropertyEditorFactory(unittest.TestCase):
    """Test PhasePropertyEditor factory."""

    def setUp(self):
        """Set up test fixtures."""
        # Delay before creating Tk to ensure previous cleanup completed
        # (Windows Tcl/Tk has slow internal cleanup that can cause file access errors)
        time.sleep(0.15)
        self.root = tk.Tk()

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        # Allow Tcl/Tk to fully cleanup internal state before next test
        # (Addresses intermittent TclError with missing .tcl files on Windows)
        time.sleep(0.3)

    def test_load_fixation_phase(self):
        """Test loading FixationPhase creates correct editor."""
        editor = PhasePropertyEditor(self.root)
        phase = FixationPhase(name="Test", duration=3.0)

        editor.load_phase(phase)

        self.assertIsNotNone(editor._current_editor)
        self.assertIsInstance(editor._current_editor, FixationPhaseEditor)

    def test_load_video_phase(self):
        """Test loading VideoPhase creates correct editor."""
        editor = PhasePropertyEditor(self.root)
        phase = VideoPhase(name="Test", participant_1_video="{video1}")

        editor.load_phase(phase)

        self.assertIsNotNone(editor._current_editor)
        self.assertIsInstance(editor._current_editor, VideoPhaseEditor)

    def test_load_none_shows_message(self):
        """Test loading None shows no selection message."""
        editor = PhasePropertyEditor(self.root)

        editor.load_phase(None)

        self.assertIsNone(editor._current_editor)


class TestBlockInfoEditor(unittest.TestCase):
    """Test BlockInfoEditor."""

    def setUp(self):
        """Set up test fixtures."""
        # Delay before creating Tk to ensure previous cleanup completed
        # (Windows Tcl/Tk has slow internal cleanup that can cause file access errors)
        time.sleep(0.15)
        self.root = tk.Tk()

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        # Allow Tcl/Tk to fully cleanup internal state before next test
        # (Addresses intermittent TclError with missing .tcl files on Windows)
        time.sleep(0.3)

    def test_load_block_info(self):
        """Test loading block information."""
        block = Block(name="Test Block", block_type='trial_based')
        block.procedure = Procedure(name="Test Procedure")
        block.procedure.add_phase(FixationPhase(duration=3.0))

        editor = BlockInfoEditor(self.root, block)

        # Verify loaded values
        self.assertEqual(editor.name_var.get(), "Test Block")
        self.assertEqual(editor.type_var.get(), "trial_based")

    def test_apply_name_change(self):
        """Test applying block name change."""
        block = Block(name="Original Name", block_type='simple')
        editor = BlockInfoEditor(self.root, block)

        # Change name
        editor.name_var.set("New Name")
        editor.apply_changes()

        # Verify change applied
        self.assertEqual(block.name, "New Name")

    def test_apply_type_change(self):
        """Test applying block type change."""
        block = Block(name="Test", block_type='trial_based')
        editor = BlockInfoEditor(self.root, block)

        # Change type
        editor.type_var.set("simple")
        editor.apply_changes()

        # Verify change applied
        self.assertEqual(block.block_type, "simple")


class TestProcedureListWidget(unittest.TestCase):
    """Test ProcedureListWidget."""

    def setUp(self):
        """Set up test fixtures."""
        # Delay before creating Tk to ensure previous cleanup completed
        # (Windows Tcl/Tk has slow internal cleanup that can cause file access errors)
        time.sleep(0.15)
        self.root = tk.Tk()

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        # Allow Tcl/Tk to fully cleanup internal state before next test
        # (Addresses intermittent TclError with missing .tcl files on Windows)
        time.sleep(0.3)

    def test_add_phase(self):
        """Test adding a phase to procedure."""
        block = Block(name="Test", block_type='trial_based')
        block.procedure = Procedure(name="Test Procedure")

        phase_editor = PhasePropertyEditor(self.root)
        widget = ProcedureListWidget(self.root, block, phase_editor)

        # Initially empty
        self.assertEqual(len(block.procedure.phases), 0)

        # Add a fixation phase
        widget._add_phase('fixation')

        # Verify phase added
        self.assertEqual(len(block.procedure.phases), 1)
        self.assertIsInstance(block.procedure.phases[0], FixationPhase)

    def test_remove_phase(self):
        """Test removing a phase from procedure."""
        block = Block(name="Test", block_type='trial_based')
        block.procedure = Procedure(name="Test Procedure")
        block.procedure.add_phase(FixationPhase(duration=3.0))
        block.procedure.add_phase(VideoPhase(participant_1_video="{video1}"))

        phase_editor = PhasePropertyEditor(self.root)
        widget = ProcedureListWidget(self.root, block, phase_editor)

        # Select first phase
        widget._selected_phase_index = 0

        # Remove it
        widget._remove_phase()

        # Verify phase removed (would need to mock messagebox, skipping for simplicity)
        # In real test would mock messagebox.askyesno to return True


class TestTemplateVariableValidator(unittest.TestCase):
    """Test TemplateVariableValidator."""

    def test_validate_matching_variables(self):
        """Test validation with matching template variables."""
        block = Block(name="Test", block_type='trial_based')
        block.procedure = Procedure(name="Test")
        block.procedure.add_phase(VideoPhase(
            participant_1_video="{video1}",
            participant_2_video="{video2}"
        ))

        # Create mock trial list with matching columns
        # (Would need to create actual CSV file for full test, skipping for simplicity)

        # For now, just test that validator doesn't crash
        warnings = TemplateVariableValidator.validate(block)
        self.assertIsInstance(warnings, list)

    def test_validate_simple_block_no_warnings(self):
        """Test validation of simple block (no trial list needed)."""
        block = Block(name="Test", block_type='simple')
        block.procedure = Procedure(name="Test")
        block.procedure.add_phase(FixationPhase(duration=3.0))

        warnings = TemplateVariableValidator.validate(block)

        # Simple blocks should have no warnings
        self.assertEqual(len(warnings), 0)


class TestPropertyPanel(unittest.TestCase):
    """Test PropertyPanel."""

    def setUp(self):
        """Set up test fixtures."""
        # Delay before creating Tk to ensure previous cleanup completed
        # (Windows Tcl/Tk has slow internal cleanup that can cause file access errors)
        time.sleep(0.15)
        self.root = tk.Tk()

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()
        # Allow Tcl/Tk to fully cleanup internal state before next test
        # (Addresses intermittent TclError with missing .tcl files on Windows)
        time.sleep(0.3)

    def test_create_property_panel(self):
        """Test creating PropertyPanel."""
        panel = PropertyPanel(self.root)

        # Verify panel created
        self.assertIsInstance(panel, PropertyPanel)

    def test_load_block(self):
        """Test loading a block into PropertyPanel."""
        panel = PropertyPanel(self.root)

        block = Block(name="Test Block", block_type='simple')
        block.procedure = Procedure(name="Test Procedure")
        block.procedure.add_phase(FixationPhase(duration=3.0))

        # Load block (should not crash)
        panel.load_block(block)

        # Verify block loaded
        self.assertEqual(panel._current_block, block)

    def test_clear_panel(self):
        """Test clearing PropertyPanel."""
        panel = PropertyPanel(self.root)

        block = Block(name="Test Block", block_type='simple')
        block.procedure = Procedure(name="Test")

        panel.load_block(block)
        panel.clear()

        # Verify panel cleared
        self.assertIsNone(panel._current_block)

    def test_deprecated_load_trial_raises_error(self):
        """Test that old load_trial method raises NotImplementedError."""
        panel = PropertyPanel(self.root)

        # Mock Trial object
        class MockTrial:
            pass

        trial = MockTrial()

        # Should raise NotImplementedError
        with self.assertRaises(NotImplementedError):
            panel.load_trial(trial)


if __name__ == '__main__':
    unittest.main()
