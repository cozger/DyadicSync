# FFmpeg Setup Instructions

The DyadicSync project requires FFmpeg for audio extraction from video files. Due to its large size (~435 MB), the FFmpeg binaries are not included in this repository.

**NEW:** DyadicSync now includes automatic FFmpeg detection! The system will automatically find and use FFmpeg from the local project directory or system PATH. No manual configuration needed.

## Download and Installation

### Option 1: Local Project Installation (Recommended)

This is the **recommended method** for DyadicSync as it ensures:
- Consistent FFmpeg version across all users
- No system PATH configuration needed
- Self-contained project that can be easily shared
- Automatic detection by the codebase

**Installation Steps:**

1. **Download FFmpeg** from the official website:
   - Visit: https://ffmpeg.org/download.html
   - For Windows: Use the builds from https://www.gyan.dev/ffmpeg/builds/
   - **IMPORTANT**: Download the "release builds" **SHARED** version (e.g., "ffmpeg-release-full-shared.7z")
   - **Do NOT use "essentials"** - it lacks the shared libraries (DLLs) required by Pyglet's video decoder

2. **Extract to Project Directory**:
   - Extract the downloaded archive
   - Rename the extracted folder to `ffmpeg`
   - Place it in the root directory of the DyadicSync project
   - The final structure should be: `DyadicSync/ffmpeg/bin/ffmpeg.exe`

3. **Verify Installation**:
   ```bash
   # From the DyadicSync directory
   python check_ffmpeg.py
   ```

   This validation script will:
   - Detect your FFmpeg installation
   - Verify version and codec support
   - Test basic functionality
   - Confirm you're ready to run experiments

### Option 2: System-wide FFmpeg Installation

Alternatively, you can install FFmpeg system-wide:

**Windows:**
1. Download FFmpeg **shared** build from https://www.gyan.dev/ffmpeg/builds/ (e.g., "ffmpeg-release-full-shared.7z")
2. Extract to a permanent location (e.g., `C:\Program Files\ffmpeg`)
3. Add the `bin` folder to your system PATH environment variable
4. Restart your terminal/IDE

**macOS (using Homebrew):**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install ffmpeg
```

## Expected Directory Structure

If using the local FFmpeg approach (Option 1), your project should have:

```
DyadicSync/
├── ffmpeg/
│   ├── bin/
│   │   ├── ffmpeg.exe
│   │   ├── ffplay.exe
│   │   ├── ffprobe.exe
│   │   ├── avutil-XX.dll      # Shared libraries (required for Pyglet)
│   │   ├── avcodec-XX.dll
│   │   ├── avformat-XX.dll
│   │   ├── swscale-XX.dll
│   │   └── swresample-XX.dll
│   ├── doc/
│   └── presets/
├── gui/
├── playback/
├── core/
└── ...
```

**Note**: The shared build includes both executables (.exe) and shared libraries (.dll). The DLL files are essential for Pyglet's video decoder to work with MPEG and other video formats.

## Troubleshooting

### "No decoders available for this file type" errors

If you get errors like `No decoders available for this file type: *.mpeg` when trying to play videos:

**Cause**: You have the FFmpeg "essentials" build instead of the "shared" build. The essentials build only contains executables (ffmpeg.exe) but lacks the shared libraries (DLLs) that Pyglet needs for video decoding.

**Solution**:
1. Download the **shared** build from https://www.gyan.dev/ffmpeg/builds/
   - Select: "release" → "full" → "ffmpeg-release-full-shared.7z"
2. Replace your current `ffmpeg/` folder with the new shared build
3. Verify that `ffmpeg/bin/` contains both `.exe` files AND `.dll` files (avutil, avcodec, avformat, etc.)
4. Test with `python utilities/videotester.py`

**Why this matters**: DyadicSync uses FFmpeg in two ways:
- Audio extraction: Uses `ffmpeg.exe` as a subprocess (works with essentials build)
- Video playback: Pyglet loads FFmpeg DLLs directly (requires shared build)

### "FFmpeg not found" errors

If you get errors about FFmpeg not being found:

1. **Run the validation script**:
   ```bash
   python check_ffmpeg.py
   ```
   This will diagnose the issue and provide specific instructions.

2. **Check the path**: Ensure the `ffmpeg` folder is in the correct location
   - Expected location: `DyadicSync/ffmpeg/bin/ffmpeg.exe`
   - Verify with: `ls ffmpeg/bin/` (should show ffmpeg.exe, ffprobe.exe, ffplay.exe)

3. **Verify binaries**: Make sure `ffmpeg.exe` (or `ffmpeg` on macOS/Linux) exists in `ffmpeg/bin/`

4. **Automatic Detection**: DyadicSync uses `config/ffmpeg_config.py` for automatic FFmpeg detection
   - Priority order: Local installation → System PATH → Error
   - The code automatically finds and uses the correct FFmpeg executable
   - No manual configuration required in Python files

### Version Requirements

- **Minimum version**: FFmpeg 4.0 or higher
- **Recommended version**: FFmpeg 5.0 or higher
- The system has been tested with FFmpeg 6.0

## Why FFmpeg?

DyadicSync uses FFmpeg to:
- Extract audio tracks from video files for independent audio routing
- Handle diverse video codecs (H.264, VP9, MPEG, etc.)
- Convert audio to WAV format for precise synchronization
- Provide Pyglet with codec libraries for video decoding (requires shared build)
- Ensure compatibility across different video formats

**Why the shared build is required**: Pyglet uses ctypes to dynamically load FFmpeg's shared libraries (DLLs on Windows) for video decoding. The "essentials" build only includes standalone executables and cannot be used by Pyglet's media decoder.

## Questions?

If you encounter issues with FFmpeg setup, please:
1. Check that you have the correct version installed
2. Verify the file paths match the expected structure
3. Ensure FFmpeg binaries are executable (on Linux/macOS: `chmod +x ffmpeg/bin/ffmpeg`)
