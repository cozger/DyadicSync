@echo off
REM Launch DyadicSync Timeline Editor with correct conda environment
REM This ensures all dependencies (pyglet, sounddevice, pylsl, etc.) are available

echo ========================================
echo DyadicSync Timeline Editor Launcher
echo ========================================
echo.
echo Activating 'sync' conda environment...
echo.

REM Activate the sync environment and run the timeline editor
call conda activate sync

if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to activate 'sync' environment
    echo.
    echo Please ensure the 'sync' conda environment exists:
    echo   conda env list
    echo.
    echo If missing, create it with:
    echo   conda create -n sync python=3.11
    echo   conda activate sync
    echo   pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Environment activated successfully
echo Python version:
python --version
echo.
echo Launching Timeline Editor...
echo.

python launch_timeline_editor.py

echo.
echo Timeline Editor closed.
pause
