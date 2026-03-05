"""
Quick test to verify sync environment has all required dependencies.
Run with: conda activate sync && python test_environment.py
"""
import sys

print('=' * 60)
print('Testing sync environment dependencies')
print('=' * 60)
print()
print(f'Python version: {sys.version.split()[0]}')
print(f'Python executable: {sys.executable}')
print()

# Test imports
try:
    import pyglet
    print(f'[OK] Pyglet {pyglet.version} imported successfully')
except ImportError as e:
    print(f'[FAIL] Pyglet import failed: {e}')
    sys.exit(1)

try:
    import sounddevice as sd
    print(f'[OK] Sounddevice {sd.__version__} imported successfully')
except ImportError as e:
    print(f'[FAIL] Sounddevice import failed: {e}')
    sys.exit(1)

try:
    import pandas
    print(f'[OK] Pandas imported successfully')
except ImportError as e:
    print(f'[FAIL] Pandas import failed: {e}')
    sys.exit(1)

try:
    import pylsl
    print(f'[OK] PyLSL imported successfully')
except ImportError as e:
    print(f'[FAIL] PyLSL import failed: {e}')
    sys.exit(1)

try:
    import ffmpeg
    print(f'[OK] FFmpeg-python imported successfully')
except ImportError as e:
    print(f'[FAIL] FFmpeg-python import failed: {e}')
    sys.exit(1)

print()
print('=' * 60)
print('[SUCCESS] All dependencies available in sync environment!')
print('=' * 60)
