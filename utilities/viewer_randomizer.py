"""
Viewer Randomizer Utility for DyadicSync Turn-Taking Conditions.

Provides balanced randomization of viewer assignment for turn-taking trials.
When the viewer column is empty for turn_taking condition trials, this utility
assigns viewer role (1 or 2) with approximately 50/50 balance.
"""

import random
from typing import List, Dict, Any, Optional


def assign_viewers(trials: List[Dict[str, Any]], seed: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Assign viewer role to turn_taking trials with balanced randomization.

    For trials where:
    - condition == 'turn_taking' (case-insensitive)
    - viewer is empty, None, or not set

    This function assigns 'viewer' = 1 or 2 with balanced randomization,
    ensuring approximately 50/50 split of P1 vs P2 as viewer.

    Args:
        trials: List of trial dictionaries (from CSV loading)
        seed: Optional random seed for reproducibility

    Returns:
        List of trial dictionaries with 'viewer' assigned for turn_taking trials.
        Modifies trials in-place AND returns the list.

    Example:
        >>> trials = [
        ...     {'condition': 'turn_taking', 'video1': 'a.mp4'},
        ...     {'condition': 'turn_taking', 'video1': 'b.mp4'},
        ...     {'condition': 'joint', 'video1': 'c.mp4'},
        ...     {'condition': 'turn_taking', 'video1': 'd.mp4', 'viewer': 1},  # pre-assigned
        ... ]
        >>> assign_viewers(trials, seed=42)
        >>> # First and second turn_taking trials get viewer assigned
        >>> # Third (joint) is unchanged
        >>> # Fourth already has viewer=1, so unchanged
    """
    # Find indices of turn_taking trials that need viewer assignment
    turn_taking_indices = []
    for i, trial in enumerate(trials):
        condition = str(trial.get('condition', '')).lower().strip()
        viewer = trial.get('viewer')

        # Check if this is a turn_taking trial without a viewer assigned
        if condition == 'turn_taking':
            # Viewer is unset if it's None, empty string, or NaN
            viewer_unset = (
                viewer is None or
                viewer == '' or
                (isinstance(viewer, float) and str(viewer).lower() == 'nan')
            )
            if viewer_unset:
                turn_taking_indices.append(i)

    if not turn_taking_indices:
        print("[ViewerRandomizer] No turn_taking trials need viewer assignment")
        return trials

    # Create balanced assignments (approximately 50/50 split)
    n = len(turn_taking_indices)
    n_viewer_1 = n // 2
    n_viewer_2 = n - n_viewer_1

    assignments = [1] * n_viewer_1 + [2] * n_viewer_2

    # Shuffle assignments
    rng = random.Random(seed)
    rng.shuffle(assignments)

    # Apply assignments
    for idx, viewer in zip(turn_taking_indices, assignments):
        trials[idx]['viewer'] = viewer

    print(f"[ViewerRandomizer] Assigned viewers to {n} turn_taking trials "
          f"(P1 viewer: {n_viewer_1}, P2 viewer: {n_viewer_2}, seed: {seed})")

    return trials


def compute_participant_modes(trial_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute participant display modes based on condition and viewer assignment.

    For turn_taking trials, sets:
    - Viewer: mode="video"
    - Observer: mode="instruction"

    For joint trials, both participants get mode="video".

    Args:
        trial_data: Dictionary with 'condition' and optionally 'viewer' keys

    Returns:
        Dictionary with added/modified keys:
        - p1_mode: "video" or "instruction"
        - p2_mode: "video" or "instruction"
        - role_p1: "viewer", "observer", or "joint"
        - role_p2: "viewer", "observer", or "joint"

    Example:
        >>> data = {'condition': 'turn_taking', 'viewer': 1}
        >>> result = compute_participant_modes(data)
        >>> result['p1_mode']
        'video'
        >>> result['p2_mode']
        'instruction'
        >>> result['role_p1']
        'viewer'
        >>> result['role_p2']
        'observer'
    """
    condition = str(trial_data.get('condition', 'joint')).lower().strip()
    viewer = trial_data.get('viewer')

    # Default to joint mode
    result = trial_data.copy()

    if condition == 'turn_taking' and viewer is not None:
        try:
            viewer_num = int(viewer)
        except (ValueError, TypeError):
            viewer_num = None

        if viewer_num == 1:
            # P1 is viewer, P2 is observer
            result['p1_mode'] = 'video'
            result['p2_mode'] = 'instruction'
            result['role_p1'] = 'viewer'
            result['role_p2'] = 'observer'
        elif viewer_num == 2:
            # P2 is viewer, P1 is observer
            result['p1_mode'] = 'instruction'
            result['p2_mode'] = 'video'
            result['role_p1'] = 'observer'
            result['role_p2'] = 'viewer'
        else:
            # Unknown viewer value - default to joint
            result['p1_mode'] = 'video'
            result['p2_mode'] = 'video'
            result['role_p1'] = 'joint'
            result['role_p2'] = 'joint'
    else:
        # Joint condition or no viewer specified
        result['p1_mode'] = 'video'
        result['p2_mode'] = 'video'
        result['role_p1'] = 'joint'
        result['role_p2'] = 'joint'

    return result


def get_viewer_balance_stats(trials: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Get statistics about viewer assignment balance.

    Args:
        trials: List of trial dictionaries

    Returns:
        Dictionary with statistics:
        - total_trials: Total number of trials
        - turn_taking_count: Number of turn_taking trials
        - joint_count: Number of joint trials
        - viewer_1_count: Number of trials where P1 is viewer
        - viewer_2_count: Number of trials where P2 is viewer
        - unassigned_count: Turn-taking trials without viewer assigned
        - balance_ratio: Ratio of P1/P2 viewer assignments (1.0 = perfectly balanced)
    """
    total = len(trials)
    turn_taking = 0
    joint = 0
    viewer_1 = 0
    viewer_2 = 0
    unassigned = 0

    for trial in trials:
        condition = str(trial.get('condition', 'joint')).lower().strip()
        viewer = trial.get('viewer')

        if condition == 'turn_taking':
            turn_taking += 1
            if viewer == 1 or viewer == '1':
                viewer_1 += 1
            elif viewer == 2 or viewer == '2':
                viewer_2 += 1
            else:
                unassigned += 1
        else:
            joint += 1

    # Calculate balance ratio (avoid division by zero)
    if viewer_2 > 0:
        balance_ratio = viewer_1 / viewer_2
    elif viewer_1 > 0:
        balance_ratio = float('inf')  # All P1, none P2
    else:
        balance_ratio = 1.0  # No turn-taking trials

    return {
        'total_trials': total,
        'turn_taking_count': turn_taking,
        'joint_count': joint,
        'viewer_1_count': viewer_1,
        'viewer_2_count': viewer_2,
        'unassigned_count': unassigned,
        'balance_ratio': balance_ratio
    }
