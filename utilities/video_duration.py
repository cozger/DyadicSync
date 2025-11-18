"""
Video duration extraction utility using FFprobe.

This module provides functions to extract video duration metadata from video files
using FFprobe (part of FFmpeg). Results are cached to improve performance when
the same video is referenced multiple times.
"""

import os
from functools import lru_cache
from typing import Optional
import ffmpeg
from config.ffmpeg_config import get_ffprobe_cmd


@lru_cache(maxsize=128)
def get_video_duration(video_path: str) -> Optional[float]:
    """
    Get video duration in seconds using FFprobe.

    This function is cached to avoid repeated file I/O for the same video.

    Args:
        video_path: Absolute path to video file

    Returns:
        Duration in seconds, or None if unable to read

    Example:
        >>> duration = get_video_duration("C:/videos/sample.mp4")
        >>> print(f"Video is {duration:.2f} seconds long")
        Video is 125.50 seconds long
    """
    print(f"[VIDEO_DURATION] Probing video: {video_path}")

    # Check if file exists
    if not os.path.exists(video_path):
        print(f"[VIDEO_DURATION] ✗ File not found: {video_path}")
        return None

    try:
        # Probe video file
        probe = ffmpeg.probe(video_path, cmd=get_ffprobe_cmd())

        # Extract duration from format metadata
        # Duration is in seconds as a string (e.g., "125.500000")
        duration_str = probe.get('format', {}).get('duration')

        if duration_str is None:
            print(f"[VIDEO_DURATION] ✗ No duration metadata found in: {video_path}")
            return None

        duration = float(duration_str)
        print(f"[VIDEO_DURATION] ✓ Duration: {duration:.2f}s for {os.path.basename(video_path)}")
        return duration

    except ffmpeg.Error as e:
        # FFmpeg error (corrupt file, unsupported codec, etc.)
        print(f"[VIDEO_DURATION] ✗ FFmpeg error for {video_path}: {e}")
        return None

    except (KeyError, ValueError, TypeError) as e:
        # Missing duration metadata or invalid format
        print(f"[VIDEO_DURATION] ✗ Invalid metadata for {video_path}: {e}")
        return None

    except Exception as e:
        # Catch-all for unexpected errors
        print(f"[VIDEO_DURATION] ✗ Unexpected error for {video_path}: {e}")
        return None


def get_max_video_duration(video1_path: str, video2_path: str) -> Optional[float]:
    """
    Get maximum duration between two videos.

    This is useful for synchronized dual-video playback where both videos
    play simultaneously and the trial continues until the longer video finishes.

    Args:
        video1_path: Path to first video (Participant 1)
        video2_path: Path to second video (Participant 2)

    Returns:
        Maximum duration in seconds, or None if both videos are unreadable

    Example:
        >>> duration = get_max_video_duration("video1.mp4", "video2.mp4")
        >>> print(f"Trial will last {duration:.1f} seconds")
        Trial will last 130.5 seconds
    """
    print(f"[MAX_DURATION] Comparing video pair:")
    print(f"  P1: {os.path.basename(video1_path)}")
    print(f"  P2: {os.path.basename(video2_path)}")

    duration1 = get_video_duration(video1_path)
    duration2 = get_video_duration(video2_path)

    # If both are None, return None
    if duration1 is None and duration2 is None:
        print(f"[MAX_DURATION] ✗ Both videos unreadable")
        return None

    # If one is None, use the other
    if duration1 is None:
        print(f"[MAX_DURATION] Using P2 duration: {duration2:.2f}s (P1 unreadable)")
        return duration2
    if duration2 is None:
        print(f"[MAX_DURATION] Using P1 duration: {duration1:.2f}s (P2 unreadable)")
        return duration1

    # Both valid, return maximum
    max_duration = max(duration1, duration2)
    which = "P1" if duration1 >= duration2 else "P2"
    print(f"[MAX_DURATION] ✓ Max duration: {max_duration:.2f}s ({which} is longer)")
    return max_duration


def clear_duration_cache():
    """
    Clear the LRU cache for video durations.

    Call this if video files have been modified or replaced and you need
    to force re-reading of metadata.
    """
    get_video_duration.cache_clear()
