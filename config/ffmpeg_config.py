"""
FFmpeg Configuration for DyadicSync

Automatically detects and configures FFmpeg executable paths.
Priority: Local installation (ffmpeg/bin/) → System PATH → Error

Usage:
    from config.ffmpeg_config import get_ffmpeg_cmd, get_ffprobe_cmd, verify_ffmpeg

    # In ffmpeg-python calls
    ffmpeg.input(video).output(audio).run(cmd=get_ffmpeg_cmd())
    probe = ffmpeg.probe(video, cmd=get_ffprobe_cmd())
"""

import os
import subprocess
import sys
from pathlib import Path


class FFmpegNotFoundError(Exception):
    """Raised when FFmpeg executable cannot be found."""
    pass


def _get_project_root():
    """
    Get the project root directory.

    Returns:
        Path: Absolute path to project root
    """
    # Try to find project root by looking for characteristic files
    current = Path(__file__).resolve().parent.parent

    # Check if this looks like the project root (has ffmpeg/ or FFMPEG_SETUP.md)
    if (current / 'ffmpeg').exists() or (current / 'FFMPEG_SETUP.md').exists():
        return current

    # Fallback: use parent of config directory
    return current


def _find_local_ffmpeg():
    """
    Check if FFmpeg exists in the local project directory.

    Returns:
        tuple: (ffmpeg_path, ffprobe_path) or (None, None) if not found
    """
    project_root = _get_project_root()

    # Windows executables
    if sys.platform == 'win32':
        ffmpeg_path = project_root / 'ffmpeg' / 'bin' / 'ffmpeg.exe'
        ffprobe_path = project_root / 'ffmpeg' / 'bin' / 'ffprobe.exe'
    else:
        # Linux/macOS
        ffmpeg_path = project_root / 'ffmpeg' / 'bin' / 'ffmpeg'
        ffprobe_path = project_root / 'ffmpeg' / 'bin' / 'ffprobe'

    if ffmpeg_path.exists() and ffprobe_path.exists():
        return str(ffmpeg_path), str(ffprobe_path)

    return None, None


def _find_system_ffmpeg():
    """
    Check if FFmpeg is available in system PATH.

    Returns:
        tuple: (ffmpeg_cmd, ffprobe_cmd) or (None, None) if not found
    """
    try:
        # Try to run ffmpeg -version
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            return 'ffmpeg', 'ffprobe'
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return None, None


def get_ffmpeg_cmd():
    """
    Get the FFmpeg executable path or command.

    Searches in order:
    1. Local installation: DyadicSync/ffmpeg/bin/ffmpeg[.exe]
    2. System PATH: ffmpeg command
    3. Raises FFmpegNotFoundError with installation instructions

    Returns:
        str: Path to ffmpeg executable or command name

    Raises:
        FFmpegNotFoundError: If FFmpeg cannot be found
    """
    # Try local installation first
    ffmpeg_local, _ = _find_local_ffmpeg()
    if ffmpeg_local:
        return ffmpeg_local

    # Try system PATH
    ffmpeg_system, _ = _find_system_ffmpeg()
    if ffmpeg_system:
        return ffmpeg_system

    # Not found - provide helpful error
    project_root = _get_project_root()
    error_msg = (
        "\n"
        "=" * 70 + "\n"
        "ERROR: FFmpeg not found!\n"
        "=" * 70 + "\n"
        "\n"
        "DyadicSync requires FFmpeg for audio/video processing.\n"
        "\n"
        "SOLUTION:\n"
        "1. Download FFmpeg from: https://www.gyan.dev/ffmpeg/builds/\n"
        "2. Extract the archive\n"
        f"3. Place extracted folder at: {project_root / 'ffmpeg'}\n"
        f"   (Should contain: {project_root / 'ffmpeg' / 'bin' / 'ffmpeg.exe'})\n"
        "\n"
        "For detailed instructions, see: FFMPEG_SETUP.md\n"
        "\n"
        "Alternative: Install FFmpeg system-wide and add to PATH\n"
        "=" * 70 + "\n"
    )
    raise FFmpegNotFoundError(error_msg)


def get_ffprobe_cmd():
    """
    Get the FFprobe executable path or command.

    Uses same search strategy as get_ffmpeg_cmd().

    Returns:
        str: Path to ffprobe executable or command name

    Raises:
        FFmpegNotFoundError: If FFprobe cannot be found
    """
    # Try local installation first
    _, ffprobe_local = _find_local_ffmpeg()
    if ffprobe_local:
        return ffprobe_local

    # Try system PATH
    _, ffprobe_system = _find_system_ffmpeg()
    if ffprobe_system:
        return ffprobe_system

    # Use same error as get_ffmpeg_cmd()
    get_ffmpeg_cmd()  # Will raise FFmpegNotFoundError


def verify_ffmpeg(verbose=True):
    """
    Verify FFmpeg installation and print diagnostic information.

    Args:
        verbose (bool): If True, print detailed information

    Returns:
        dict: Dictionary with installation details:
            - 'found': bool
            - 'ffmpeg_cmd': str or None
            - 'ffprobe_cmd': str or None
            - 'version': str or None
            - 'location': 'local' | 'system' | None
    """
    result = {
        'found': False,
        'ffmpeg_cmd': None,
        'ffprobe_cmd': None,
        'version': None,
        'location': None
    }

    try:
        # Get FFmpeg paths
        ffmpeg_cmd = get_ffmpeg_cmd()
        ffprobe_cmd = get_ffprobe_cmd()

        result['found'] = True
        result['ffmpeg_cmd'] = ffmpeg_cmd
        result['ffprobe_cmd'] = ffprobe_cmd

        # Determine location
        if 'ffmpeg' in str(ffmpeg_cmd) and ('bin' in str(ffmpeg_cmd) or '/' in str(ffmpeg_cmd) or '\\' in str(ffmpeg_cmd)):
            result['location'] = 'local'
        else:
            result['location'] = 'system'

        # Get version
        try:
            version_result = subprocess.run(
                [ffmpeg_cmd, '-version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if version_result.returncode == 0:
                # Extract version from first line
                first_line = version_result.stdout.split('\n')[0]
                result['version'] = first_line
        except:
            result['version'] = 'Unknown'

        if verbose:
            print("=" * 70)
            print("FFmpeg Configuration Status")
            print("=" * 70)
            print(f"[OK] FFmpeg found: {result['location']} installation")
            print(f"  FFmpeg:  {result['ffmpeg_cmd']}")
            print(f"  FFprobe: {result['ffprobe_cmd']}")
            print(f"  Version: {result['version']}")
            print("=" * 70)

        return result

    except FFmpegNotFoundError as e:
        if verbose:
            print(str(e))
        return result


if __name__ == '__main__':
    # Run verification when module is executed directly
    verify_ffmpeg(verbose=True)
