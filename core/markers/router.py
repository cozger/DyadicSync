"""
MarkerRouter - Dual-stream LSL marker routing.

Routes markers to participant-specific LSL streams based on MarkerBinding.participant:
- participant=1  → P1 stream only
- participant=2  → P2 stream only
- participant=None → both streams (shared markers like baseline, trial start)
"""

from typing import Optional
from pylsl import StreamInfo, StreamOutlet


class MarkerRouter:
    """
    Wraps two StreamOutlet instances (P1 and P2) and routes markers
    based on participant ownership.

    Passed through the execution chain as `lsl_outlet` — no signature
    changes needed anywhere downstream.
    """

    def __init__(self, outlet_p1: StreamOutlet, outlet_p2: StreamOutlet):
        self._outlet_p1 = outlet_p1
        self._outlet_p2 = outlet_p2

    def send(self, marker_str: str, participant: Optional[int] = None):
        """
        Send a marker to the appropriate stream(s).

        Args:
            marker_str: Marker value as string
            participant: 1 (P1 only), 2 (P2 only), or None (both)
        """
        sample = [marker_str]
        if participant == 1:
            self._outlet_p1.push_sample(sample)
        elif participant == 2:
            self._outlet_p2.push_sample(sample)
        else:
            # Shared marker → both streams
            self._outlet_p1.push_sample(sample)
            self._outlet_p2.push_sample(sample)

    @staticmethod
    def create(headset_selection: Optional[str] = None) -> 'MarkerRouter':
        """
        Factory that creates two participant-specific StreamOutlets.

        Args:
            headset_selection: P1 headset ID ('B16' or 'B1A'), or None

        Returns:
            MarkerRouter instance with two configured outlets
        """
        p2_headset = None
        if headset_selection:
            p2_headset = 'B1A' if headset_selection == 'B16' else 'B16'

        # --- P1 stream ---
        info_p1 = StreamInfo(
            name='ExpEvent_Markers_P1',
            type='Markers',
            channel_count=1,
            channel_format='string',
            source_id='dyadicsync_exp_p1'
        )
        desc_p1 = info_p1.desc()
        desc_p1.append_child_value('experiment_system', 'DyadicSync')
        desc_p1.append_child_value('version', '2.0')
        desc_p1.append_child_value('participant', '1')
        if headset_selection:
            desc_p1.append_child_value('headset_id', headset_selection)

        # --- P2 stream ---
        info_p2 = StreamInfo(
            name='ExpEvent_Markers_P2',
            type='Markers',
            channel_count=1,
            channel_format='string',
            source_id='dyadicsync_exp_p2'
        )
        desc_p2 = info_p2.desc()
        desc_p2.append_child_value('experiment_system', 'DyadicSync')
        desc_p2.append_child_value('version', '2.0')
        desc_p2.append_child_value('participant', '2')
        if p2_headset:
            desc_p2.append_child_value('headset_id', p2_headset)

        outlet_p1 = StreamOutlet(info_p1)
        outlet_p2 = StreamOutlet(info_p2)

        print("[MarkerRouter] Created dual LSL streams: ExpEvent_Markers_P1, ExpEvent_Markers_P2")
        if headset_selection:
            print(f"[MarkerRouter] Metadata: P1={headset_selection}, P2={p2_headset}")

        return MarkerRouter(outlet_p1, outlet_p2)
