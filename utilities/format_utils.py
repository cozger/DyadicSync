"""
Formatting utilities for display in GUI.

This module provides helper functions for formatting data for user-friendly
display in the timeline editor GUI.
"""


def format_duration(seconds: float) -> str:
    """
    Format duration in HH:MM:SS format.

    Args:
        seconds: Duration in seconds (can be fractional)

    Returns:
        Formatted string in HH:MM:SS format, or "--:--:--" if invalid

    Examples:
        >>> format_duration(125.5)
        '00:02:05'
        >>> format_duration(3661)
        '01:01:01'
        >>> format_duration(0)
        '00:00:00'
        >>> format_duration(-1)
        '--:--:--'
    """
    # Handle invalid durations
    if seconds is None or seconds < 0:
        return "--:--:--"

    # Convert to integer seconds (round down)
    total_seconds = int(seconds)

    # Calculate hours, minutes, seconds
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    # Format as HH:MM:SS
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def format_duration_compact(seconds: float) -> str:
    """
    Format duration in compact format (omit hours if zero).

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string as "MM:SS" or "HH:MM:SS" if hours > 0

    Examples:
        >>> format_duration_compact(125)
        '02:05'
        >>> format_duration_compact(3661)
        '01:01:01'
    """
    if seconds is None or seconds < 0:
        return "--:--"

    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    else:
        return f"{minutes:02d}:{secs:02d}"
