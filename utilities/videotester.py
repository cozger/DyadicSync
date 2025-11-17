import threading
import time
import os
import tempfile
import sounddevice as sd
import soundfile as sf
import ffmpeg
import pyglet
import pandas as pd
from pathlib import Path

def debug_print(message):
    print(f"DEBUG: {message}")

def analyze_video_file(video_path):
    try:
        probe = ffmpeg.probe(video_path)
        video_stream = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        audio_stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        
        details = {
            'codec': video_stream['codec_name'],
            'profile': video_stream.get('profile', 'unknown'),
            'pixel_format': video_stream.get('pix_fmt', 'unknown'),
            'resolution': f"{video_stream['width']}x{video_stream['height']}",
            'frame_rate': eval(video_stream['r_frame_rate']),  # Convert string fraction to number
            'audio_codec': audio_stream['codec_name'],
            'audio_sample_rate': audio_stream['sample_rate'],
            'container': probe['format']['format_name'],
            'duration': float(probe['format']['duration']),
            'bit_rate': int(probe['format'].get('bit_rate', 0)) // 1000,  # Convert to kbps
            'size_mb': round(float(probe['format']['size']) / (1024*1024), 2)
        }
        
        debug_print(f"\nVideo Analysis for {os.path.basename(video_path)}:")
        debug_print(f"Video Codec: {details['codec']} (Profile: {details['profile']})")
        debug_print(f"Pixel Format: {details['pixel_format']}")
        debug_print(f"Resolution: {details['resolution']}")
        debug_print(f"Frame Rate: {details['frame_rate']:.2f} fps")
        debug_print(f"Audio: {details['audio_codec']} @ {details['audio_sample_rate']}Hz")
        debug_print(f"Container: {details['container']}")
        debug_print(f"Duration: {details['duration']:.2f}s")
        debug_print(f"Bitrate: {details['bit_rate']}kbps")
        debug_print(f"File Size: {details['size_mb']}MB")
        
        return details
        
    except Exception as e:
        debug_print(f"Error analyzing {video_path}: {str(e)}")
        return None

class VideoTester:
    def __init__(self, video_path):
        self.video_path = video_path
        self.player = None
        self.window = None
        self.playback_success = False
        self.error_message = None
        
    def prepare(self):
        try:
            # Prepare video
            source = pyglet.media.load(self.video_path)
            self.player = pyglet.media.Player()
            self.player.queue(source)
            debug_print(f"Successfully loaded video: {self.video_path}")
            return True
        except Exception as e:
            self.error_message = str(e)
            debug_print(f"Error loading video: {str(e)}")
            return False
            
    def test_playback(self):
        try:
            # Create a window
            display = pyglet.canvas.get_display()
            screen = display.get_screens()[0]  # Use primary screen
            self.window = pyglet.window.Window(width=800, height=600, screen=screen)
            
            @self.window.event
            def on_draw():
                self.window.clear()
                if self.player and self.player.source and self.player.get_texture():
                    self.player.get_texture().blit(0, 0)
                    self.playback_success = True
            
            # Start playback
            self.player.play()
            
            # Run for 5 seconds
            def close_after_timeout():
                time.sleep(5)
                pyglet.app.exit()
            
            timeout_thread = threading.Thread(target=close_after_timeout)
            timeout_thread.daemon = True
            timeout_thread.start()
            
            try:
                pyglet.app.run()
            except Exception as e:
                self.error_message = str(e)
                debug_print(f"Error during playback: {str(e)}")
            
            # Cleanup
            self.player.pause()
            self.window.close()
            
            return self.playback_success
            
        except Exception as e:
            self.error_message = str(e)
            debug_print(f"Error during playback: {str(e)}")
            if self.window:
                self.window.close()
            return False

def test_video_files(csv_path):
    try:
        # Read CSV file
        df = pd.read_csv(csv_path)
        
        # Get unique video paths from both columns
        video_paths = pd.concat([df['VideoPath1'], df['VideoPath2']]).unique()
        
        results = []
        
        for video_path in video_paths:
            debug_print(f"\n{'='*50}")
            debug_print(f"Testing video: {video_path}")
            
            # Analyze video
            video_details = analyze_video_file(video_path)
            
            # Test playback
            tester = VideoTester(video_path)
            can_prepare = tester.prepare()
            can_play = tester.test_playback() if can_prepare else False
            
            result = {
                'path': video_path,
                'details': video_details,
                'can_prepare': can_prepare,
                'can_play': can_play,
                'error': tester.error_message
            }
            
            results.append(result)
            
            # Print summary
            debug_print(f"\nResults for {os.path.basename(video_path)}:")
            debug_print(f"Can prepare: {can_prepare}")
            debug_print(f"Can play: {can_play}")
            if not can_prepare or not can_play:
                debug_print(f"Error: {tester.error_message}")
            
        return results
            
    except Exception as e:
        debug_print(f"Error processing CSV: {str(e)}")
        return None

if __name__ == "__main__":
    csv_path = r"C:\Users\canoz\OneDrive\Masaüstü\ScratchExp\video_pairs.csv"  # Update this path
    results = test_video_files(csv_path)
    
    if results:
        # Print final summary
        debug_print("\nFinal Summary:")
        debug_print(f"Total videos tested: {len(results)}")
        playable = sum(1 for r in results if r['can_play'])
        debug_print(f"Successfully playable: {playable}")
        debug_print(f"Failed: {len(results) - playable}")
        
        # Print details of failed videos
        if len(results) - playable > 0:
            debug_print("\nFailed Videos:")
            for result in results:
                if not result['can_play']:
                    debug_print(f"\nFile: {os.path.basename(result['path'])}")
                    if result['details']:
                        debug_print("Video details:")
                        for key, value in result['details'].items():
                            debug_print(f"  {key}: {value}")
                    debug_print(f"Error: {result['error']}")