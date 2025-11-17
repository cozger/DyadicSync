# FFmpeg Setup Instructions

The DyadicSync project requires FFmpeg for audio extraction from video files. Due to its large size (~435 MB), the FFmpeg binaries are not included in this repository.

## Download and Installation

### Option 1: Download FFmpeg Binaries (Recommended)

1. **Download FFmpeg** from the official website:
   - Visit: https://ffmpeg.org/download.html
   - For Windows: Use the builds from https://www.gyan.dev/ffmpeg/builds/
   - Download the "release builds" full version

2. **Extract to Project Directory**:
   - Extract the downloaded archive
   - Rename the extracted folder to `ffmpeg`
   - Place it in the root directory of the DyadicSync project
   - The final structure should be: `DyadicSync/ffmpeg/bin/ffmpeg.exe`

3. **Verify Installation**:
   ```bash
   # From the DyadicSync directory
   ./ffmpeg/bin/ffmpeg -version
   ```

### Option 2: System-wide FFmpeg Installation

Alternatively, you can install FFmpeg system-wide:

**Windows:**
1. Download FFmpeg from https://www.gyan.dev/ffmpeg/builds/
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
│   │   └── ffprobe.exe
│   ├── doc/
│   └── presets/
├── gui/
├── playback/
├── core/
└── ...
```

## Troubleshooting

### "FFmpeg not found" errors

If you get errors about FFmpeg not being found:

1. **Check the path**: Ensure the `ffmpeg` folder is in the correct location
2. **Verify binaries**: Make sure `ffmpeg.exe` (or `ffmpeg` on macOS/Linux) exists in `ffmpeg/bin/`
3. **Check code references**: The code uses FFmpeg for audio extraction - verify the path in `playback/synchronized_player.py`

### Version Requirements

- **Minimum version**: FFmpeg 4.0 or higher
- **Recommended version**: FFmpeg 5.0 or higher
- The system has been tested with FFmpeg 6.0

## Why FFmpeg?

DyadicSync uses FFmpeg to:
- Extract audio tracks from video files for independent audio routing
- Handle diverse video codecs (H.264, VP9, etc.)
- Convert audio to WAV format for precise synchronization
- Ensure compatibility across different video formats

## Questions?

If you encounter issues with FFmpeg setup, please:
1. Check that you have the correct version installed
2. Verify the file paths match the expected structure
3. Ensure FFmpeg binaries are executable (on Linux/macOS: `chmod +x ffmpeg/bin/ffmpeg`)
