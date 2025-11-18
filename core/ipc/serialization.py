"""
Serialization helpers for inter-process communication.

Provides tools to serialize Timeline and experiment configuration
for passing between GUI process and experiment subprocess.
"""

from typing import Dict, Any
from core.execution.timeline import Timeline


class ExperimentConfig:
    """
    Serializable configuration for experiment subprocess.

    Wraps Timeline and runtime configuration (subject ID, session, etc.)
    for transmission to subprocess via multiprocessing Queue.
    """

    def __init__(self, timeline: Timeline, subject_id: int, session: int,
                 headset: str, output_dir: str,
                 labrecorder_enabled: bool = False,
                 labrecorder_host: str = 'localhost',
                 labrecorder_port: int = 22345):
        """
        Initialize experiment configuration.

        Args:
            timeline: Timeline object with experiment structure
            subject_id: Subject identifier (0 = disable saving)
            session: Session number (0 = disable saving)
            headset: Headset selection ('B16' or 'B1A')
            output_dir: Directory for data output
            labrecorder_enabled: Enable LabRecorder auto-start
            labrecorder_host: LabRecorder RCS host
            labrecorder_port: LabRecorder RCS port
        """
        self.timeline = timeline
        self.subject_id = subject_id
        self.session = session
        self.headset = headset
        self.output_dir = output_dir
        self.labrecorder_enabled = labrecorder_enabled
        self.labrecorder_host = labrecorder_host
        self.labrecorder_port = labrecorder_port

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize configuration to dictionary.

        Uses Timeline's existing to_dict() method for serialization.
        All values are picklable for multiprocessing.Queue transport.

        Returns:
            Dictionary with all configuration data
        """
        return {
            'timeline': self.timeline.to_dict(),
            'subject_id': self.subject_id,
            'session': self.session,
            'headset': self.headset,
            'output_dir': self.output_dir,
            'labrecorder_enabled': self.labrecorder_enabled,
            'labrecorder_host': self.labrecorder_host,
            'labrecorder_port': self.labrecorder_port
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExperimentConfig':
        """
        Deserialize configuration from dictionary.

        Reconstructs Timeline from dict using Timeline.from_dict().
        Called in subprocess to recreate experiment configuration.

        Args:
            data: Dictionary from to_dict()

        Returns:
            ExperimentConfig instance
        """
        timeline = Timeline.from_dict(data['timeline'])
        return cls(
            timeline=timeline,
            subject_id=data['subject_id'],
            session=data['session'],
            headset=data['headset'],
            output_dir=data['output_dir'],
            labrecorder_enabled=data.get('labrecorder_enabled', False),
            labrecorder_host=data.get('labrecorder_host', 'localhost'),
            labrecorder_port=data.get('labrecorder_port', 22345)
        )

    def __repr__(self):
        return (
            f"ExperimentConfig("
            f"timeline={self.timeline.metadata.get('name', 'Untitled')}, "
            f"subject={self.subject_id}, "
            f"session={self.session}, "
            f"headset={self.headset})"
        )
