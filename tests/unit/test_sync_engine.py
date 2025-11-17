"""
Unit tests for SyncEngine timing precision.

Tests the timestamp-based synchronization system to ensure <5ms accuracy.
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from playback.sync_engine import SyncEngine


# ==================== TIMESTAMP CALCULATION TESTS ====================

@pytest.mark.unit
def test_calculate_sync_timestamp_default():
    """SyncEngine should calculate timestamp 100ms in future by default."""
    before = time.perf_counter()
    sync_ts = SyncEngine.calculate_sync_timestamp()
    after = time.perf_counter()

    # sync_ts should be ~100ms after before
    expected_min = before + 0.090  # 90ms (allowing 10ms tolerance)
    expected_max = after + 0.110   # 110ms (allowing 10ms tolerance)

    assert expected_min <= sync_ts <= expected_max


@pytest.mark.unit
def test_calculate_sync_timestamp_custom_prep_time():
    """SyncEngine should calculate timestamp with custom prep time."""
    before = time.perf_counter()
    sync_ts = SyncEngine.calculate_sync_timestamp(prep_time_ms=200)
    after = time.perf_counter()

    # sync_ts should be ~200ms after before
    expected_min = before + 0.190  # 190ms
    expected_max = after + 0.210   # 210ms

    assert expected_min <= sync_ts <= expected_max


@pytest.mark.unit
def test_calculate_sync_timestamp_zero_prep_time():
    """SyncEngine should handle zero prep time (immediate sync)."""
    before = time.perf_counter()
    sync_ts = SyncEngine.calculate_sync_timestamp(prep_time_ms=0)
    after = time.perf_counter()

    # sync_ts should be essentially now
    assert before <= sync_ts <= after + 0.001  # Within 1ms


# ==================== WAIT UNTIL TIMESTAMP TESTS ====================

@pytest.mark.unit
def test_wait_until_timestamp_precision():
    """wait_until_timestamp should achieve <5ms precision."""
    target = time.perf_counter() + 0.050  # 50ms from now
    actual = SyncEngine.wait_until_timestamp(target)

    drift = abs(actual - target) * 1000  # Convert to ms

    # Should achieve <5ms precision
    assert drift < 5.0, f"Drift {drift:.3f}ms exceeds 5ms target"


@pytest.mark.unit
def test_wait_until_timestamp_past_time():
    """wait_until_timestamp should handle past timestamps gracefully."""
    # Target is already in the past
    target = time.perf_counter() - 0.100  # 100ms ago
    actual = SyncEngine.wait_until_timestamp(target)

    # Should return immediately (actual >= target)
    # Since target is in past, busy-wait will exit immediately
    assert actual >= target


@pytest.mark.unit
def test_wait_until_timestamp_various_delays():
    """wait_until_timestamp should work for different delay amounts."""
    delays_ms = [10, 20, 50, 100, 200]

    for delay_ms in delays_ms:
        target = time.perf_counter() + (delay_ms / 1000.0)
        actual = SyncEngine.wait_until_timestamp(target)

        drift = abs(actual - target) * 1000
        assert drift < 5.0, f"Drift {drift:.3f}ms exceeds 5ms for {delay_ms}ms delay"


# ==================== VERIFY SYNC TESTS ====================

@pytest.mark.unit
def test_verify_sync_success():
    """_verify_sync should report success for good sync (<5ms drift)."""
    target = 1000.0
    actual_starts = [1000.001, 1000.002, 1000.0015]  # All within 2ms

    result = SyncEngine._verify_sync(actual_starts, target)

    assert result['success'] is True
    assert result['max_drift_ms'] < 5.0
    assert result['spread_ms'] < 5.0
    assert result['sync_timestamp'] == target
    assert len(result['actual_starts']) == 3


@pytest.mark.unit
def test_verify_sync_failure():
    """_verify_sync should report failure for poor sync (>5ms drift)."""
    target = 1000.0
    actual_starts = [1000.000, 1000.010, 1000.002]  # 10ms drift

    result = SyncEngine._verify_sync(actual_starts, target)

    assert result['success'] is False
    assert result['max_drift_ms'] >= 5.0


@pytest.mark.unit
def test_verify_sync_with_failed_players():
    """_verify_sync should handle None values for failed players."""
    target = 1000.0
    actual_starts = [1000.001, None, 1000.002]  # Player 2 failed

    result = SyncEngine._verify_sync(actual_starts, target)

    # Should calculate metrics based only on successful players
    assert len(result['actual_starts']) == 3  # Original list preserved
    assert result['max_drift_ms'] < 5.0  # Based on successful players only


@pytest.mark.unit
def test_verify_sync_all_players_failed():
    """_verify_sync should handle all players failing."""
    target = 1000.0
    actual_starts = [None, None, None]

    result = SyncEngine._verify_sync(actual_starts, target)

    assert result['success'] is False
    assert result['max_drift_ms'] == float('inf')
    assert result['spread_ms'] == float('inf')


# ==================== PLAY SYNCHRONIZED TESTS ====================

@pytest.mark.unit
def test_play_synchronized_with_mock_players():
    """play_synchronized should coordinate multiple players."""
    # Create mock players with play_at_timestamp method
    player1 = MagicMock()
    player2 = MagicMock()

    # Mock returns actual start times (simulate 1ms drift)
    base_time = time.perf_counter() + 0.1
    player1.play_at_timestamp.return_value = base_time + 0.001
    player2.play_at_timestamp.return_value = base_time + 0.002

    result = SyncEngine.play_synchronized([player1, player2], prep_time_ms=50)

    # Verify both players were called
    assert player1.play_at_timestamp.called
    assert player2.play_at_timestamp.called

    # Verify both called with same timestamp
    ts1 = player1.play_at_timestamp.call_args[0][0]
    ts2 = player2.play_at_timestamp.call_args[0][0]
    assert abs(ts1 - ts2) < 0.001  # Same timestamp (within 1ms)

    # Verify result structure
    assert 'sync_timestamp' in result
    assert 'actual_starts' in result
    assert 'max_drift_ms' in result
    assert 'spread_ms' in result
    assert 'success' in result
    assert len(result['actual_starts']) == 2


@pytest.mark.unit
def test_play_synchronized_prep_time():
    """play_synchronized should respect custom prep_time_ms."""
    player1 = MagicMock()
    player1.play_at_timestamp.return_value = time.perf_counter()

    before = time.perf_counter()
    result = SyncEngine.play_synchronized([player1], prep_time_ms=150)

    # sync_timestamp should be ~150ms after before
    sync_ts = result['sync_timestamp']
    assert sync_ts >= before + 0.140  # At least 140ms (allowing some tolerance)


@pytest.mark.unit
def test_play_synchronized_empty_player_list():
    """play_synchronized should handle empty player list."""
    result = SyncEngine.play_synchronized([], prep_time_ms=100)

    # Should complete without error
    assert result['actual_starts'] == []
    assert result['success'] is False  # No players = failure


@pytest.mark.unit
def test_play_synchronized_player_exception():
    """play_synchronized should handle player exceptions gracefully."""
    player1 = MagicMock()
    player2 = MagicMock()

    # Player 1 succeeds
    player1.play_at_timestamp.return_value = time.perf_counter()

    # Player 2 raises exception
    player2.play_at_timestamp.side_effect = Exception("Playback failed")

    result = SyncEngine.play_synchronized([player1, player2], prep_time_ms=50)

    # Should complete without crashing
    assert len(result['actual_starts']) == 2
    assert result['actual_starts'][0] is not None  # Player 1 succeeded
    assert result['actual_starts'][1] is None      # Player 2 failed


# ==================== INTEGRATION/TIMING TESTS ====================

@pytest.mark.unit
def test_sync_engine_end_to_end_timing():
    """Test complete sync flow with timing validation."""
    # Create real mock players that respect timing
    class TimedMockPlayer:
        def play_at_timestamp(self, sync_timestamp):
            SyncEngine.wait_until_timestamp(sync_timestamp)
            return time.perf_counter()

    player1 = TimedMockPlayer()
    player2 = TimedMockPlayer()

    # Run synchronization
    result = SyncEngine.play_synchronized([player1, player2], prep_time_ms=80)

    # Verify sync quality
    assert result['success'] is True, f"Sync failed: {result['max_drift_ms']:.3f}ms drift"
    assert result['max_drift_ms'] < 5.0
    assert result['spread_ms'] < 5.0  # Both players within 5ms of each other

    # Verify actual starts are close to sync timestamp
    for actual in result['actual_starts']:
        drift = abs(actual - result['sync_timestamp']) * 1000
        assert drift < 5.0


@pytest.mark.unit
def test_sync_engine_constants():
    """Verify SyncEngine constants are set correctly."""
    assert SyncEngine.BUSY_WAIT_THRESHOLD_MS == 5.0
    assert SyncEngine.DEFAULT_PREP_TIME_MS == 100


# ==================== STRESS TESTS ====================

@pytest.mark.unit
def test_sync_engine_multiple_rounds():
    """Test sync engine across multiple synchronization rounds."""
    class TimedMockPlayer:
        def play_at_timestamp(self, sync_timestamp):
            SyncEngine.wait_until_timestamp(sync_timestamp)
            return time.perf_counter()

    players = [TimedMockPlayer() for _ in range(3)]

    # Run 5 synchronization rounds
    for round_num in range(5):
        result = SyncEngine.play_synchronized(players, prep_time_ms=60)

        assert result['success'] is True, f"Round {round_num} failed: {result['max_drift_ms']:.3f}ms"
        assert result['max_drift_ms'] < 5.0
        assert result['spread_ms'] < 5.0

        # Small delay between rounds
        time.sleep(0.01)


@pytest.mark.unit
def test_sync_engine_many_players():
    """Test sync engine with many players (stress test)."""
    class TimedMockPlayer:
        def play_at_timestamp(self, sync_timestamp):
            SyncEngine.wait_until_timestamp(sync_timestamp)
            return time.perf_counter()

    # Test with 10 players
    players = [TimedMockPlayer() for _ in range(10)]

    result = SyncEngine.play_synchronized(players, prep_time_ms=150)

    # With many players, allow slightly higher spread
    assert result['success'] is True
    assert result['max_drift_ms'] < 10.0  # Still under 10ms for 10 players
    assert len(result['actual_starts']) == 10
