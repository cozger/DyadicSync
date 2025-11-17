"""
Timestamp-based synchronization engine for precise multi-player video/audio sync.

This module provides high-precision synchronization (<5ms target) for launching
multiple SynchronizedPlayer instances at the exact same timestamp, eliminating
the need for manual audio offset configuration.

Key Features:
- Timestamp-based coordination (shared clock)
- Hybrid sleep approach (coarse sleep + busy-wait)
- Sync quality verification and logging
- <5ms audio-video sync, <2ms inter-player sync target

Example Usage:
    from playback.sync_engine import SyncEngine
    from playback.synchronized_player import SynchronizedPlayer

    # Create players
    player1 = SynchronizedPlayer(video_path1, audio_device_1)
    player2 = SynchronizedPlayer(video_path2, audio_device_2)

    # Synchronize playback
    sync_result = SyncEngine.play_synchronized([player1, player2])
    print(f"Sync quality: {sync_result['max_drift_ms']:.2f}ms drift")
"""

import time
import threading
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class SyncEngine:
    """
    High-precision synchronization engine for multi-player video/audio playback.

    Uses timestamp-based coordination to ensure all players start at the exact
    same time, with verification logging to confirm <5ms synchronization quality.
    """

    # Timing constants
    BUSY_WAIT_THRESHOLD_MS = 5.0  # Switch from sleep to busy-wait at 5ms before target
    DEFAULT_PREP_TIME_MS = 100    # Default preparation time before sync point

    @staticmethod
    def calculate_sync_timestamp(prep_time_ms: float = DEFAULT_PREP_TIME_MS) -> float:
        """
        Calculate a future timestamp for synchronized playback start.

        Args:
            prep_time_ms: Milliseconds in the future to schedule the sync point.
                         Should be long enough for all players to prepare (load,
                         position threads, etc.) but not so long that drift accumulates.
                         Default: 100ms (adequate for 2-4 players)

        Returns:
            Absolute timestamp (time.perf_counter() value) for the sync point

        Example:
            >>> sync_ts = SyncEngine.calculate_sync_timestamp(prep_time_ms=150)
            >>> # sync_ts is now 150ms in the future
        """
        return time.perf_counter() + (prep_time_ms / 1000.0)

    @staticmethod
    def wait_until_timestamp(target_timestamp: float) -> float:
        """
        Wait until a specific timestamp with high precision using hybrid sleep.

        Strategy:
        1. Coarse sleep until 5ms before target (OS scheduler, low CPU)
        2. Busy-wait for final 5ms (high precision, high CPU)

        This approach balances CPU efficiency with timing precision, achieving
        <1ms accuracy on most systems.

        Args:
            target_timestamp: Absolute timestamp to wait until (from perf_counter)

        Returns:
            Actual timestamp when wait completed (for drift measurement)

        Example:
            >>> target = time.perf_counter() + 0.1  # 100ms from now
            >>> actual = SyncEngine.wait_until_timestamp(target)
            >>> drift = (actual - target) * 1000  # Convert to ms
            >>> print(f"Drift: {drift:.3f}ms")
        """
        # Phase 1: Coarse sleep (low CPU, moderate precision)
        busy_wait_threshold = SyncEngine.BUSY_WAIT_THRESHOLD_MS / 1000.0
        while True:
            time_remaining = target_timestamp - time.perf_counter()
            if time_remaining <= busy_wait_threshold:
                break
            if time_remaining > 0.010:  # Sleep if >10ms remaining
                time.sleep(time_remaining - busy_wait_threshold)

        # Phase 2: Busy-wait (high CPU, high precision)
        while time.perf_counter() < target_timestamp:
            pass  # Spin until target reached

        return time.perf_counter()

    @staticmethod
    def trigger_synchronized_playback(players: List[Any]) -> Dict[str, Any]:
        """
        Trigger playback for pre-armed players (INSTANT execution, zero-ISI).

        This method implements the TRIGGER phase of the arm/trigger pattern.
        All players must have armed_timestamp already set via arm_sync_timestamp().

        Unlike play_synchronized(), this method does NO preparation or calculation -
        it simply triggers all pre-armed players for instant synchronized start.
        This enables true zero-ISI when called after resources are loaded and
        sync timestamps are pre-calculated.

        Args:
            players: List of SynchronizedPlayer instances that are already armed

        Returns:
            Dictionary with sync quality metrics (same as play_synchronized)

        Raises:
            RuntimeError: If any player is not armed

        Example:
            # During previous phase (STAGE 2):
            sync_ts = SyncEngine.calculate_sync_timestamp(150)
            player1.arm_sync_timestamp(sync_ts)
            player2.arm_sync_timestamp(sync_ts)

            # ... fixation continues for 150ms ...

            # At phase transition (INSTANT):
            result = SyncEngine.trigger_synchronized_playback([player1, player2])
            # <1ms execution time, videos start immediately
        """
        # Validate all players are armed
        for i, player in enumerate(players):
            if not hasattr(player, 'armed_timestamp') or player.armed_timestamp is None:
                raise RuntimeError(
                    f"Player {i} is not armed! Must call arm_sync_timestamp() first. "
                    f"This should happen during STAGE 2 of the previous phase."
                )

        # Extract target timestamp from first player
        target_timestamp = players[0].armed_timestamp

        # CRITICAL FIX: Validate all players have the SAME timestamp
        # Silent desynchronization if timestamps differ!
        for i, player in enumerate(players[1:], 1):
            timestamp_diff = abs(player.armed_timestamp - target_timestamp)
            if timestamp_diff > 0.001:  # >1ms difference is problematic
                raise RuntimeError(
                    f"Player {i} armed with different timestamp! "
                    f"Player 0: {target_timestamp:.6f}, Player {i}: {player.armed_timestamp:.6f} "
                    f"(diff: {(player.armed_timestamp - target_timestamp)*1000:.3f}ms). "
                    f"All players must be armed with the same sync timestamp."
                )

        logger.info(f"SyncEngine: Triggering {len(players)} pre-armed players at "
                   f"t={target_timestamp:.6f}")

        # Storage for actual start times
        actual_starts = [None] * len(players)

        def trigger_player(index: int, player: Any):
            """Thread worker: trigger one pre-armed player."""
            try:
                actual_start = player.trigger_playback()
                actual_starts[index] = actual_start
            except Exception as e:
                logger.error(f"SyncEngine: Player {index} trigger failed: {e}")
                actual_starts[index] = None

        # Launch all players in parallel threads
        threads = []
        for i, player in enumerate(players):
            thread = threading.Thread(target=trigger_player, args=(i, player))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete (with timeout protection)
        for i, thread in enumerate(threads):
            thread.join(timeout=5.0)  # 5 second timeout
            if thread.is_alive():
                logger.error(f"SyncEngine: Player {i} trigger timeout after 5 seconds")
                actual_starts[i] = None  # Mark as failed

        # Verify sync quality
        sync_result = SyncEngine._verify_sync(actual_starts, target_timestamp)

        return sync_result

    @staticmethod
    def play_synchronized(
        players: List[Any],
        prep_time_ms: float = DEFAULT_PREP_TIME_MS
    ) -> Dict[str, Any]:
        """
        Start multiple SynchronizedPlayer instances at the exact same timestamp.

        This is the main entry point for synchronized playback. It:
        1. Calculates a future sync timestamp
        2. Launches all players in parallel threads
        3. Each player waits until the sync timestamp, then starts playback
        4. Verifies sync quality and logs results

        Args:
            players: List of SynchronizedPlayer instances (must have play_at_timestamp method)
            prep_time_ms: Preparation time before sync point (default: 100ms)

        Returns:
            Dictionary with sync quality metrics:
            {
                'sync_timestamp': float,      # Target timestamp
                'actual_starts': List[float], # Actual start times per player
                'max_drift_ms': float,        # Maximum drift from target
                'spread_ms': float,           # Range between first/last player
                'success': bool               # True if all drifts < 5ms
            }

        Example:
            >>> result = SyncEngine.play_synchronized([player1, player2], prep_time_ms=120)
            >>> if result['success']:
            ...     print(f"Sync achieved: {result['max_drift_ms']:.2f}ms drift")
            ... else:
            ...     print(f"WARNING: Sync quality degraded: {result['max_drift_ms']:.2f}ms")
        """
        # Validate prep_time_ms
        if prep_time_ms < 10:
            logger.warning(f"SyncEngine: prep_time_ms={prep_time_ms:.1f}ms is very low "
                          f"(<10ms), synchronization quality may be degraded")

        # Calculate sync point
        sync_timestamp = SyncEngine.calculate_sync_timestamp(prep_time_ms)

        logger.info(f"SyncEngine: Scheduling {len(players)} players for sync at "
                   f"t+{prep_time_ms:.1f}ms")

        # Storage for actual start times
        actual_starts = [None] * len(players)

        def launch_player(index: int, player: Any):
            """Thread worker: launch one player at sync timestamp."""
            try:
                actual_start = player.play_at_timestamp(sync_timestamp)
                actual_starts[index] = actual_start
            except Exception as e:
                logger.error(f"SyncEngine: Player {index} failed to start: {e}")
                actual_starts[index] = None

        # Launch all players in parallel threads
        threads = []
        for i, player in enumerate(players):
            thread = threading.Thread(target=launch_player, args=(i, player))
            thread.start()
            threads.append(thread)

        # Wait for all threads to complete (with timeout protection)
        for i, thread in enumerate(threads):
            thread.join(timeout=5.0)  # 5 second timeout
            if thread.is_alive():
                logger.error(f"SyncEngine: Player {i} thread timeout after 5 seconds")
                actual_starts[i] = None  # Mark as failed

        # Verify sync quality
        sync_result = SyncEngine._verify_sync(actual_starts, sync_timestamp)

        return sync_result

    @staticmethod
    def _verify_sync(
        actual_starts: List[Optional[float]],
        target_timestamp: float
    ) -> Dict[str, Any]:
        """
        Verify synchronization quality and log metrics.

        Calculates:
        - Drift: How far each player deviated from target timestamp
        - Spread: Time range between first and last player
        - Success: Whether all players achieved <5ms drift

        Args:
            actual_starts: List of actual start timestamps (None if player failed)
            target_timestamp: Target sync timestamp

        Returns:
            Dictionary with sync quality metrics (same as play_synchronized)
        """
        # Filter out failed players
        valid_starts = [s for s in actual_starts if s is not None]

        if not valid_starts:
            logger.error("SyncEngine: All players failed to start!")
            return {
                'sync_timestamp': target_timestamp,
                'actual_starts': actual_starts,
                'max_drift_ms': float('inf'),
                'spread_ms': float('inf'),
                'success': False
            }

        # Calculate drift for each player (deviation from target)
        drifts_ms = [(actual - target_timestamp) * 1000 for actual in valid_starts]
        max_drift_ms = max(abs(d) for d in drifts_ms)

        # Calculate spread (range between earliest and latest)
        spread_ms = (max(valid_starts) - min(valid_starts)) * 1000

        # Success criteria: all drifts < 5ms
        success = max_drift_ms < 5.0

        # Log results
        status = "SUCCESS" if success else "WARNING"
        logger.info(f"SyncEngine: {status} - Max drift: {max_drift_ms:.3f}ms, "
                   f"Spread: {spread_ms:.3f}ms, Players: {len(valid_starts)}/{len(actual_starts)}")

        # Log per-player details at debug level
        for i, drift in enumerate(drifts_ms):
            logger.debug(f"  Player {i}: {drift:+.3f}ms from target")

        return {
            'sync_timestamp': target_timestamp,
            'actual_starts': actual_starts,
            'max_drift_ms': max_drift_ms,
            'spread_ms': spread_ms,
            'success': success
        }
