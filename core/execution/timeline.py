"""
Timeline class for DyadicSync Framework.

Manages the sequence of blocks in an experiment.
"""

from typing import List, Optional, Dict, Any
from .block import Block


class Timeline:
    """
    Manages the sequence of blocks in an experiment.

    A timeline is an ordered list of blocks that execute sequentially.
    Supports reordering, insertion, deletion via GUI.
    """

    def __init__(self, name: str = "Untitled Experiment"):
        """
        Initialize timeline with optional metadata.

        Args:
            name: Experiment name
        """
        self.blocks: List[Block] = []

        # Experiment-level metadata
        self.metadata: Dict[str, Any] = {
            'name': name,
            'description': '',
            # Display configuration
            'control_monitor': None,  # Control monitor index
            'participant_1_monitor': None,  # Participant 1 display index
            'participant_2_monitor': None,  # Participant 2 display index
            # Audio configuration
            'audio_device_1': None,  # Audio device index for participant 1
            'audio_device_2': None,  # Audio device index for participant 2
            # Experiment settings
            'baseline_duration': 240,  # Default baseline duration
            # LSL configuration
            'lsl_stream_name': 'ExpEvent_Markers',  # LSL stream name
            'lsl_enabled': True,  # Whether to send LSL markers
        }

    def add_block(self, block: Block, index: Optional[int] = None):
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
        """
        Remove block at index.

        Args:
            index: Block index to remove
        """
        del self.blocks[index]

    def reorder_block(self, old_index: int, new_index: int):
        """
        Move block from old_index to new_index.

        Args:
            old_index: Current block index
            new_index: Target block index
        """
        block = self.blocks.pop(old_index)
        self.blocks.insert(new_index, block)

    def validate(self) -> List[str]:
        """
        Validate all blocks in timeline.

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        for i, block in enumerate(self.blocks):
            block_errors = block.validate()
            errors.extend([f"Block {i} ({block.name}): {e}" for e in block_errors])
        return errors

    def get_total_trials(self) -> int:
        """
        Calculate total number of trials across all blocks.

        Returns:
            Total trial count
        """
        return sum(block.get_trial_count() for block in self.blocks)

    def get_estimated_duration(self) -> float:
        """
        Estimate total experiment duration in seconds.

        Returns:
            Total seconds (may be approximate for variable-duration phases)
        """
        return sum(block.get_estimated_duration() for block in self.blocks)

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize timeline to dictionary.

        Returns:
            Dictionary representation
        """
        return {
            'metadata': self.metadata,
            'blocks': [block.to_dict() for block in self.blocks]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Timeline':
        """
        Deserialize timeline from dictionary.

        Args:
            data: Dictionary representation

        Returns:
            Timeline instance
        """
        # Load metadata
        metadata = data.get('metadata', {})
        timeline = cls(name=metadata.get('name', 'Untitled Experiment'))

        # Update metadata with all fields
        timeline.metadata.update(metadata)

        # Load blocks
        for block_data in data.get('blocks', []):
            block = Block.from_dict(block_data)
            timeline.add_block(block)

        return timeline
