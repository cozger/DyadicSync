"""
Marker Logger System

Tracks all LSL markers sent during an experiment for:
- Post-experiment documentation
- Validation and debugging
- Export to CSV/text format
"""

import time
import csv
from dataclasses import dataclass, asdict
from typing import List, Union, Optional, Dict, Any
from pathlib import Path


@dataclass
class MarkerEvent:
    """Record of a single marker event"""
    timestamp: float              # Time when marker was sent (time.time())
    marker: Union[int, str]      # Marker value (integer or string)
    event_type: Optional[str] = None    # Event type (e.g., "video_start", "p1_response")
    phase_name: Optional[str] = None    # Phase that sent the marker
    trial_index: Optional[int] = None   # Trial number (if applicable)
    participant: Optional[int] = None   # Participant number (1 or 2, if applicable)
    additional_data: Optional[Dict[str, Any]] = None  # Extra context

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return asdict(self)


class MarkerLogger:
    """
    Logger for tracking all LSL markers sent during an experiment.

    Usage:
        # At experiment start
        logger = MarkerLogger(session_id="P001_session1")

        # During execution (called automatically by Phase.send_marker)
        logger.log_marker(marker=1001, event_type="video_start", phase_name="Video Playback")

        # At experiment end
        logger.export_to_csv("markers_log.csv")
        logger.export_summary("markers_summary.txt")
    """

    def __init__(self, session_id: str = "default"):
        """
        Initialize marker logger.

        Args:
            session_id: Unique identifier for this experiment session
        """
        self.session_id = session_id
        self.events: List[MarkerEvent] = []
        self.session_start_time = time.time()

    def log_marker(
        self,
        marker: Union[int, str],
        event_type: Optional[str] = None,
        phase_name: Optional[str] = None,
        trial_index: Optional[int] = None,
        participant: Optional[int] = None,
        **additional_data
    ):
        """
        Log a marker event.

        Args:
            marker: Marker value (integer or string)
            event_type: Event type (e.g., "video_start", "p1_response")
            phase_name: Name of phase that sent the marker
            trial_index: Trial number (if applicable)
            participant: Participant number (1 or 2, if applicable)
            **additional_data: Any extra context to record
        """
        event = MarkerEvent(
            timestamp=time.time(),
            marker=marker,
            event_type=event_type,
            phase_name=phase_name,
            trial_index=trial_index,
            participant=participant,
            additional_data=additional_data if additional_data else None
        )
        self.events.append(event)

    def get_events(
        self,
        marker: Optional[Union[int, str]] = None,
        event_type: Optional[str] = None,
        trial_index: Optional[int] = None
    ) -> List[MarkerEvent]:
        """
        Filter events by criteria.

        Args:
            marker: Filter by specific marker value
            event_type: Filter by event type
            trial_index: Filter by trial number

        Returns:
            List of matching MarkerEvent objects
        """
        filtered = self.events

        if marker is not None:
            filtered = [e for e in filtered if e.marker == marker]

        if event_type is not None:
            filtered = [e for e in filtered if e.event_type == event_type]

        if trial_index is not None:
            filtered = [e for e in filtered if e.trial_index == trial_index]

        return filtered

    def get_marker_counts(self) -> Dict[Union[int, str], int]:
        """
        Get count of how many times each marker was sent.

        Returns:
            Dictionary mapping marker value to count
        """
        counts = {}
        for event in self.events:
            counts[event.marker] = counts.get(event.marker, 0) + 1
        return counts

    def export_to_csv(self, output_path: str):
        """
        Export all marker events to CSV file.

        Args:
            output_path: Path to output CSV file

        CSV columns:
            timestamp, relative_time, marker, event_type, phase_name,
            trial_index, participant, additional_data
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', newline='') as f:
            writer = csv.writer(f)

            # Header
            writer.writerow([
                'timestamp',
                'relative_time_sec',
                'marker',
                'event_type',
                'phase_name',
                'trial_index',
                'participant',
                'additional_data'
            ])

            # Events
            for event in self.events:
                relative_time = event.timestamp - self.session_start_time
                writer.writerow([
                    event.timestamp,
                    f"{relative_time:.3f}",
                    event.marker,
                    event.event_type or '',
                    event.phase_name or '',
                    event.trial_index or '',
                    event.participant or '',
                    str(event.additional_data) if event.additional_data else ''
                ])

    def export_summary(self, output_path: str):
        """
        Export summary statistics to text file.

        Args:
            output_path: Path to output text file

        Includes:
            - Total marker count
            - Unique marker count
            - Marker frequency table
            - Event type breakdown
        """
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            f.write(f"Marker Logger Summary\n")
            f.write(f"Session ID: {self.session_id}\n")
            f.write(f"Session Start: {time.ctime(self.session_start_time)}\n")
            f.write(f"\n")

            # Total counts
            f.write(f"Total Events: {len(self.events)}\n")
            unique_markers = len(set(e.marker for e in self.events))
            f.write(f"Unique Markers: {unique_markers}\n")
            f.write(f"\n")

            # Marker frequency
            f.write(f"Marker Frequency:\n")
            f.write(f"-" * 50 + "\n")
            counts = self.get_marker_counts()
            for marker, count in sorted(counts.items(), key=lambda x: x[1], reverse=True):
                f.write(f"  {marker}: {count} occurrences\n")
            f.write(f"\n")

            # Event type breakdown
            event_types = {}
            for event in self.events:
                if event.event_type:
                    event_types[event.event_type] = event_types.get(event.event_type, 0) + 1

            if event_types:
                f.write(f"Event Type Breakdown:\n")
                f.write(f"-" * 50 + "\n")
                for event_type, count in sorted(event_types.items(), key=lambda x: x[1], reverse=True):
                    f.write(f"  {event_type}: {count} events\n")
                f.write(f"\n")

            # Trial breakdown (if applicable)
            trials = set(e.trial_index for e in self.events if e.trial_index is not None)
            if trials:
                f.write(f"Trial Coverage:\n")
                f.write(f"-" * 50 + "\n")
                f.write(f"  Trials with markers: {sorted(trials)}\n")
                f.write(f"  Total trials: {len(trials)}\n")
                f.write(f"\n")

    def clear(self):
        """Clear all logged events (useful between experiment blocks)"""
        self.events.clear()

    def get_event_count(self) -> int:
        """Get total number of logged events"""
        return len(self.events)

    def get_last_event(self) -> Optional[MarkerEvent]:
        """Get the most recently logged event"""
        return self.events[-1] if self.events else None
