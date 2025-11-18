import threading
import time
import os
import tempfile
import sounddevice as sd
import soundfile as sf
import ffmpeg
import pyglet
import pandas as pd
from pyglet.window import key
from screeninfo import get_monitors
import numpy as np
from pylsl import StreamInfo, StreamOutlet
from config.ffmpeg_config import get_ffmpeg_cmd

# LSL Initiation
info = StreamInfo(name='ExpEvent_Markers', type='Markers', channel_count=1,
                  channel_format='int32', source_id='uniqueid12345')
# Initialize the stream.
outlet = StreamOutlet(info)

audio_device_1_index = 7
audio_device_2_index = 19

# Global variables
exit_event = threading.Event()
pyglet_running = threading.Event()
rating_complete = threading.Event()

current_pair_index = 0
window1 = None
window2 = None
cross1 = None
cross2 = None
ratings_data = []
audio_offset_ms = 500  # Positive value means audio starts earlier by this many milliseconds

# Global input listener and key mappings
input_window = pyglet.window.Window(visible=False)
participant_1_keys = {key._1: 1, key._2: 2, key._3: 3, key._4: 4, key._5: 5, key._6: 6, key._7: 7}
participant_2_keys = {key.Q: 1, key.W: 2, key.E: 3, key.R: 4, key.T: 5, key.Y: 6, key.U: 7}

# Create a hidden window to act as the global input listener
input_window = pyglet.window.Window(visible=False)

@input_window.event
def on_key_press(symbol, modifiers):
    global p1_responded, p2_responded, ratings_data

    # Key mappings for both participants
    participant_1_keys = {key._1: 1, key._2: 2, key._3: 3, key._4: 4, key._5: 5, key._6: 6, key._7: 7}
    participant_2_keys = {key.Q: 1, key.W: 2, key.E: 3, key.R: 4, key.T: 5, key.Y: 6, key.U: 7}

    # Handle Participant 1 input
    if symbol in participant_1_keys and not p1_responded:
        rating = participant_1_keys[symbol]
        outlet.push_sample(x=[3000 + rating])  # Send LSL marker for Participant 1
        ratings_data.append(('P1', rating))
        response1.text = f"Response recorded: {rating}"
        p1_responded = True
        debug_print(f"Participant 1 responded: {rating}")

    # Handle Participant 2 input
    elif symbol in participant_2_keys and not p2_responded:
        rating = participant_2_keys[symbol]
        outlet.push_sample(x=[5000 + rating])  # Send LSL marker for Participant 2
        ratings_data.append(('P2', rating))
        response2.text = f"Response recorded: {rating}"
        p2_responded = True
        debug_print(f"Participant 2 responded: {rating}")

    # Check if both participants have responded
    if p1_responded and p2_responded:
        rating_complete.set()

def debug_print(message):
    print(f"DEBUG: {message}")

def load_video_pairs_from_csv(csv_path):
    """Load video pairs from a CSV file with VideoPath1 and VideoPath2 columns"""
    try:      
        # Read the CSV file
        df = pd.read_csv(csv_path)
        
        # Verify required columns exist
        if 'VideoPath1' not in df.columns or 'VideoPath2' not in df.columns:
            debug_print("Error: CSV must contain 'VideoPath1' and 'VideoPath2' columns")
            return None
            
        # Convert DataFrame rows to list of tuples
        video_pairs = list(zip(df['VideoPath1'], df['VideoPath2']))
        
        debug_print(f"Loaded {len(video_pairs)} video pairs from CSV")
        return video_pairs
        
    except Exception as e:
        debug_print(f"Error loading video pairs from CSV: {str(e)}")
        return None
    
# Video Stimuli Path List
csv_path = r"C:\Users\canoz\OneDrive\Masaüstü\ScratchExp\video_pairs_extended.csv"
video_pairs = load_video_pairs_from_csv(csv_path)

def show_welcome_screen():
    """Run welcome screen on both video monitors"""
    global HeadsetP1, HeadsetP2, window1, window2

    headset_selected = threading.Event()
    welcome_complete = threading.Event()

    try:
        # Use the same screen setup as videos
        display = pyglet.display.get_display()
        screens = display.get_screens()

        if len(screens) < 3:
            debug_print("Error: Not enough screens detected")
            return False

        # Create windows on the same screens as videos
        window1 = pyglet.window.Window(fullscreen=True, screen=screens[1])
        window2 = pyglet.window.Window(fullscreen=True, screen=screens[2])
        window1.set_exclusive_keyboard(False)
        window2.set_exclusive_keyboard(False)


        debug_print("Welcome windows created")

        # Create text for both windows
        welcome_batch1 = pyglet.graphics.Batch()
        welcome_batch2 = pyglet.graphics.Batch()

        # Create labels for window 1
        welcome_text1 = pyglet.text.Label(
            'Welcome to the Experiment',
            font_name='Arial',
            font_size=36,
            x=window1.width // 2,
            y=window1.height // 2 + 150,
            anchor_x='center',
            anchor_y='center',
            batch=welcome_batch1
        )

        instruction_text1 = pyglet.text.Label(
            'Select headset configuration:\n\n'
            'Press G: B16 (P1) and TheOtherOne (P2)\n'
            'Press K: TheOtherOne (P1) and B16 (P2)\n\n'
            'During videos:\n'
            'A or ← : Left response\n'
            'D or → : Right response\n'
            'ESC : Exit',
            font_name='Arial',
            font_size=24,
            x=window1.width // 2,
            y=window1.height // 2,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=600,
            batch=welcome_batch1
        )

        confirmation_text1 = pyglet.text.Label(
            '',  # Will be updated when selection is made
            font_name='Arial',
            font_size=24,
            x=window1.width // 2,
            y=window1.height // 2 - 150,
            anchor_x='center',
            anchor_y='center',
            color=(0, 255, 0, 255),
            batch=welcome_batch1
        )

        # Create identical labels for window 2
        welcome_text2 = pyglet.text.Label(
            'Welcome to the Experiment',
            font_name='Arial',
            font_size=36,
            x=window2.width // 2,
            y=window2.height // 2 + 150,
            anchor_x='center',
            anchor_y='center',
            batch=welcome_batch2
        )

        instruction_text2 = pyglet.text.Label(
            instruction_text1.text,  # Use same text as window 1
            font_name='Arial',
            font_size=24,
            x=window2.width // 2,
            y=window2.height // 2,
            anchor_x='center',
            anchor_y='center',
            multiline=True,
            width=600,
            batch=welcome_batch2
        )

        confirmation_text2 = pyglet.text.Label(
            '',  # Will be updated when selection is made
            font_name='Arial',
            font_size=24,
            x=window2.width // 2,
            y=window2.height // 2 - 150,
            anchor_x='center',
            anchor_y='center',
            color=(0, 255, 0, 255),
            batch=welcome_batch2
        )

        def update_confirmation(text):
            confirmation_text1.text = text
            confirmation_text2.text = text

        @window1.event
        def on_draw():
            window1.clear()
            welcome_batch1.draw()

        @window2.event
        def on_draw():
            window2.clear()
            welcome_batch2.draw()

        @window1.event
        def on_key_press(symbol, modifiers):
            handle_key_press(symbol, update_confirmation, headset_selected, welcome_complete)

        @window2.event
        def on_key_press(symbol, modifiers):
            handle_key_press(symbol, update_confirmation, headset_selected, welcome_complete)

        def handle_key_press(symbol, update_confirmation, headset_selected, welcome_complete):
            global HeadsetP1, HeadsetP2
            if symbol == key.G and not headset_selected.is_set():
                HeadsetP1 = 'B16'
                HeadsetP2 = 'TheOtherOne'
                outlet.push_sample(x=[9161])
                headset_selected.set()
                update_confirmation("Selected: B16 (P1) and TheOtherOne (P2)\nPress ENTER to continue")
                debug_print("G pressed - Headset 1 selected")
            elif symbol == key.K and not headset_selected.is_set():
                HeadsetP1 = 'TheOtherOne'
                HeadsetP2 = 'B16'
                outlet.push_sample(x=[9162])
                headset_selected.set()
                update_confirmation("Selected: TheOtherOne (P1) and B16 (P2)\nPress ENTER to continue")
                debug_print("K pressed - Headset 2 selected")
            elif symbol == key.SPACE and headset_selected.is_set():
                debug_print("Space pressed - Welcome screen complete")
                welcome_complete.set()
                pyglet.app.exit()
            elif symbol == key.ESCAPE:
                debug_print("Escape pressed - Exiting")
                exit_program()

        debug_print("Starting welcome screen")
        pyglet.app.run()

        # Clean up
        window1.close()
        window2.close()

        debug_print("Welcome screen completed successfully")
        return welcome_complete.is_set()

    except Exception as e:
        debug_print(f"Error in welcome screen: {str(e)}")
        return False


class SynchronizedPlayer:
    def __init__(self, video_path, audio_device_index, window):
        self.video_path = video_path
        self.audio_device_index = audio_device_index
        self.window = window
        self.player = None
        self.audio_data = None
        self.samplerate = None
        self.ready = threading.Event()
        
    def prepare(self):
        try:
            debug_print(f"Preparing video: {self.video_path}")
            # Extract audio first
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_file:
                temp_audio_path = temp_file.name
                try:
                    ffmpeg.input(self.video_path).output(
                        temp_audio_path,
                        format='wav',
                        acodec='pcm_s16le',
                        y=None
                    ).run(cmd=get_ffmpeg_cmd(), quiet=True, capture_stdout=True, capture_stderr=True)
                except Exception as e:
                    debug_print(f"FFmpeg error for {self.video_path}: {str(e)}")
                    raise
                    
                try:
                    self.audio_data, self.samplerate = sf.read(temp_audio_path, dtype='float32')
                except Exception as e:
                    debug_print(f"Soundfile read error for {self.video_path}: {str(e)}")
                    raise
                    
            os.remove(temp_audio_path)
            
            # Prepare video
            try:
                source = pyglet.media.load(self.video_path)
                if not source:
                    debug_print(f"Failed to load video source: {self.video_path}")
                    raise RuntimeError("Video source load failed")
                    
                self.player = pyglet.media.Player()
                self.player.queue(source)
                self.player.volume = 0
                
                # Test if we can get duration and texture
                test_duration = source.duration
                debug_print(f"Video duration: {test_duration}")
                
                self.ready.set()
                debug_print(f"Successfully prepared video: {self.video_path}")
                
            except Exception as e:
                debug_print(f"Pyglet video load error for {self.video_path}: {str(e)}")
                raise
                
        except Exception as e:
            debug_print(f"Error in prepare for {self.video_path}: {str(e)}")
            self.ready.set()  # Set ready even on failure so we don't hang
            raise  # Re-raise to handle in calling code
    
    def play_audio(self):
        try:
            # Make sure we have audio data
            if self.audio_data is None or self.samplerate is None:
                debug_print(f"No audio data available for device {self.audio_device_index}")
                return
                
            debug_print(f"Starting audio on device {self.audio_device_index}")
            # Play and wait to prevent the audio stream from being terminated
            sd.play(self.audio_data, self.samplerate, device=self.audio_device_index)
            sd.wait()  # This ensures the audio plays completely
            debug_print(f"Audio finished on device {self.audio_device_index}")
        except Exception as e:
            debug_print(f"Error playing audio on device {self.audio_device_index}: {str(e)}")
    
    def start(self):
        if not self.ready.is_set():
            raise RuntimeError("Player not prepared")
            
        try:
            debug_print(f"Player ready for device {self.audio_device_index}")
        except Exception as e:
            debug_print(f"Error in start: {str(e)}")
            
    def stop(self):
        try:
            if self.player:
                self.player.pause()
                self.player.delete()  # Add this line
                self.player = None    # Add this line
            sd.stop()
            # Clear audio data
            self.audio_data = None
            self.samplerate = None
        except Exception as e:
            debug_print(f"Error in stop: {str(e)}")

class CrossDisplay:
    def __init__(self, window):
        self.window = window
        self.active = False
        self.batch = pyglet.graphics.Batch()
        
        self.cross_length = min(window.width, window.height) * 0.2
        self.cross_thickness = self.cross_length * 0.1
        
        center_x = window.width // 2
        center_y = window.height // 2
        
        self.vertical = pyglet.shapes.Rectangle(
            x=center_x - self.cross_thickness/2,
            y=center_y - self.cross_length/2,
            width=self.cross_thickness,
            height=self.cross_length,
            color=(255, 255, 255),
            batch=self.batch
        )
        
        self.horizontal = pyglet.shapes.Rectangle(
            x=center_x - self.cross_length/2,
            y=center_y - self.cross_thickness/2,
            width=self.cross_length,
            height=self.cross_thickness,
            color=(255, 255, 255),
            batch=self.batch
        )
    
    def draw(self):
        if self.active:
            self.batch.draw()

def run_video_audio_sync(video1_path, video2_path, audio_device_1_index, audio_device_2_index, on_finish_callback):
    global window1, window2, cross1, cross2
    
    if exit_event.is_set():
        return
    
    try:    
        player1 = SynchronizedPlayer(video1_path, audio_device_1_index, window1)
        player2 = SynchronizedPlayer(video2_path, audio_device_2_index, window2)
        
        # Show crosses during preparation
        cross1.active = True
        cross2.active = True
        
        # Prepare both players
        prep_success = True
        try:
            prep_thread1 = threading.Thread(target=player1.prepare)
            prep_thread2 = threading.Thread(target=player2.prepare)
            
            prep_thread1.start()
            prep_thread2.start()
            prep_thread1.join()
            prep_thread2.join()
            
            # Verify both players are ready and have valid sources
            if not (player1.player and player1.player.source and 
                    player2.player and player2.player.source):
                raise RuntimeError("One or both players failed to prepare properly")
                
            video1_duration = player1.player.source.duration
            video2_duration = player2.player.source.duration
            # Use the longer duration to ensure both videos complete
            video_duration = max(video1_duration, video2_duration)
            debug_print(f"Video pair {current_pair_index} prepared successfully. Durations: {video1_duration:.2f}, {video2_duration:.2f}")
            
        except Exception as e:
            debug_print(f"Error preparing video pair {current_pair_index}: {str(e)}")
            prep_success = False
            
        if not prep_success:
            debug_print(f"Skipping video pair {current_pair_index} due to preparation failure")
            pyglet.clock.schedule_once(on_finish_callback, 1)
            return
    
        @window1.event
        def on_draw():
            window1.clear()
            if cross1.active:
                cross1.draw()
            elif player1.player.source and player1.player.texture:
                player1.player.texture.blit(0, 0, width=window1.width, height=window1.height)
                
        @window2.event
        def on_draw():
            window2.clear()
            if cross2.active:
                cross2.draw()
            elif player2.player.source and player2.player.texture:
                player2.player.texture.blit(0, 0, width=window2.width, height=window2.height)
        
        def handle_playback_end(dt):
            try:
                if exit_event.is_set():
                    return
                    
                debug_print("Entering handle_playback_end")
                
                # Stop playback
                player1.stop()
                player2.stop()
                
                # Clear any remaining audio
                sd.stop()
                
                # Force garbage collection to free up resources
                import gc
                gc.collect()
                
                cross1.active = True
                cross2.active = True
                
                if not exit_event.is_set():
                    debug_print("Starting rating screen")
                    # Show rating screen after videos complete
                    rating_complete.clear()
                    create_rating_screen()
                    
                    def check_rating_complete(dt):
                        if rating_complete.is_set():
                            pyglet.clock.unschedule(check_rating_complete)
                            debug_print("Ratings complete, proceeding to next pair")
                            on_finish_callback(0)  # This will trigger play_next_pair
                    
                    # Schedule check for rating completion
                    pyglet.clock.schedule_interval(check_rating_complete, 0.1)
                    
            except Exception as e:
                debug_print(f"Error in playback end handler: {str(e)}")
                on_finish_callback(0)
                
        def start_playback(dt):
            try:
                if exit_event.is_set():
                    return
                    
                debug_print("Starting playback function")
                cross1.active = False
                cross2.active = False
                
                # Create audio threads first but don't start them
                audio_thread1 = threading.Thread(target=player1.play_audio)
                audio_thread2 = threading.Thread(target=player2.play_audio)
                
                # Calculate delay for video start based on audio offset
                video_delay = audio_offset_ms / 1000.0  # Convert to seconds
                
                debug_print(f"Starting playback for pair {current_pair_index}")
                
                # Start audio threads first if offset is positive
                if audio_offset_ms > 0:
                    audio_thread1.start()
                    audio_thread2.start()
                    time.sleep(video_delay)
                    outlet.push_sample(x=[1000+current_pair_index])
                    player1.player.play()
                    player2.player.play()
                else:
                    # Start videos first if offset is negative
                    player1.player.play()
                    player2.player.play()
                    time.sleep(-video_delay)
                    outlet.push_sample(x=[100+current_pair_index])
                    audio_thread1.start()
                    audio_thread2.start()
                
                # Schedule cleanup using exact duration
                debug_print(f"Scheduling cleanup in {video_duration} seconds")
                pyglet.clock.schedule_once(handle_playback_end, video_duration + 0.1)  # Add small buffer
                
            except Exception as e:
                debug_print(f"Error in start_playback: {str(e)}")
                handle_playback_end(0)
                
        # Start playback after a delay
        pyglet.clock.schedule_once(start_playback, 3)
        
    except Exception as e:
        debug_print(f"Fatal error in video sync: {str(e)}")
        pyglet.clock.schedule_once(on_finish_callback, 1)


def exit_program():
    debug_print("Initiating program exit")
    sd.stop()
    exit_event.set()
    if pyglet_running.is_set():
        pyglet.app.exit()
    os._exit(1)


def create_rating_screen():
    input_window.activate()

    """Create and show rating screen after videos"""
    global response1, response2, p1_responded, p2_responded

    # Reset participant responses
    p1_responded = False
    p2_responded = False

    # Activate the input window for global input handling
    input_window.activate()

    # Create instruction batches for both windows
    instruction_batch1 = pyglet.graphics.Batch()
    instruction_batch2 = pyglet.graphics.Batch()

    # Instructions and labels for Participant 1
    instruction1 = pyglet.text.Label(
        'How did the video make you feel?\n\n'
        'Participant 1: Use number keys 1-7\n'
        '1 = Awful, 4 = Neutral, 7 = Amazing',
        font_name='Arial',
        font_size=24,
        x=window1.width // 2,
        y=window1.height // 2 + 100,
        anchor_x='center',
        anchor_y='center',
        multiline=True,
        width=600,
        batch=instruction_batch1
    )

    response1 = pyglet.text.Label(
        'Waiting for response...',
        font_name='Arial',
        font_size=24,
        x=window1.width // 2,
        y=window1.height // 2 - 100,
        anchor_x='center',
        anchor_y='center',
        batch=instruction_batch1
    )

    # Instructions and labels for Participant 2
    instruction2 = pyglet.text.Label(
        'How did the video make you feel?\n\n'
        'Participant 2: Use keys Q-U\n'
        'Q = Awful, R = Neutral, U = Amazing',
        font_name='Arial',
        font_size=24,
        x=window2.width // 2,
        y=window2.height // 2 + 100,
        anchor_x='center',
        anchor_y='center',
        multiline=True,
        width=600,
        batch=instruction_batch2
    )

    response2 = pyglet.text.Label(
        'Waiting for response...',
        font_name='Arial',
        font_size=24,
        x=window2.width // 2,
        y=window2.height // 2 - 100,
        anchor_x='center',
        anchor_y='center',
        batch=instruction_batch2
    )

    # Define drawing for Participant 1 window
    @window1.event
    def on_draw():
        window1.clear()
        instruction_batch1.draw()

    # Define drawing for Participant 2 window
    @window2.event
    def on_draw():
        window2.clear()
        instruction_batch2.draw()

    # Function to ensure input window remains active
    def ensure_input_window_active(dt):
        input_window.activate()
        #debug_print("Input window re-activated to preserve focus.")

    # Schedule periodic activation of input window
    pyglet.clock.schedule_interval(ensure_input_window_active, 1.0)

    debug_print("Rating screen setup complete")

def save_ratings():
    """Save ratings data to CSV file"""
    try:
        # Create DataFrame from ratings
        df = pd.DataFrame(ratings_data, columns=['Participant', 'Rating'])
        
        # Add video pair information
        df['VideoPair'] = current_pair_index
        df['Video1'] = video_pairs[current_pair_index-1][0]
        df['Video2'] = video_pairs[current_pair_index-1][1]
        
        # Add timestamp
        df['Timestamp'] = pd.Timestamp.now()
        
        # Create or append to CSV file
        file_path = 'experiment_data.csv'
        if os.path.exists(file_path):
            df.to_csv(file_path, mode='a', header=False, index=False)
        else:
            df.to_csv(file_path, index=False)
            
        debug_print(f"Ratings saved for video pair {current_pair_index}")
        
    except Exception as e:
        debug_print(f"Error saving ratings: {str(e)}")

import csv

def play_video_pairs_consecutively(video_pairs_input, audio_device_1_index, audio_device_2_index, log_file="video_compatibility_results.csv"):
    """Play pairs of videos consecutively, limiting playback to 3 seconds per pair, and log results to a CSV file."""
    global window1, window2, cross1, cross2, video_pairs, current_pair_index

    video_pairs = video_pairs_input.copy()
    current_pair_index = 0

    # Prepare the CSV log file
    with open(log_file, mode='w', newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        csvwriter.writerow(["Video 1", "Video 2", "Status", "Error Message"])  # Header row

        try:
            # Setup displays and windows
            display = pyglet.display.get_display()
            screens = display.get_screens()

            if len(screens) < 3:
                debug_print("Error: Not enough screens detected")
                return

            window1 = pyglet.window.Window(fullscreen=True, screen=screens[1])
            window2 = pyglet.window.Window(fullscreen=True, screen=screens[2])

            cross1 = CrossDisplay(window1)
            cross2 = CrossDisplay(window2)

            debug_print("Windows created successfully")
        except Exception as e:
            debug_print(f"Error setting up windows: {str(e)}")
            return

        def listen_for_exit():
            """Listen for 'esc' key to terminate the program."""
            while not exit_event.is_set():
                if keyboard.is_pressed('esc'):
                    exit_program()
                    break
                time.sleep(0.1)

        # Start thread to listen for exit key
        key_listener_thread = threading.Thread(target=listen_for_exit)
        key_listener_thread.daemon = True
        key_listener_thread.start()

        # Start playing video pairs
        if video_pairs:
            debug_print("Starting first video pair")
            pyglet_running.set()
            play_next_pair(0, csvwriter)
            try:
                pyglet.app.run()
            except Exception as e:
                debug_print(f"Error in pyglet app run: {str(e)}")
            finally:
                pyglet_running.clear()

def stop_and_play_next(player1, player2, csvwriter, video1_path, video2_path, status, error_message):
    """Stop current video players, log the result, and play the next pair."""
    global current_pair_index

    # Stop players if they exist
    if player1:
        player1.pause()
        player1.delete()
    if player2:
        player2.pause()
        player2.delete()

    # Log the result
    csvwriter.writerow([video1_path, video2_path, status, error_message])
    debug_print(f"Logged video pair: {video1_path}, {video2_path}, Status: {status}, Error: {error_message}")

    # Move to the next pair
    next_pair_index = current_pair_index + 1
    pyglet.clock.schedule_once(lambda dt: play_next_pair(next_pair_index, csvwriter), 0.1)

def play_next_pair(pair_index, csvwriter):
    """Play the next video pair, limiting playback to 3 seconds, and log results."""
    global video_pairs, current_pair_index, window1, window2

    if pair_index >= len(video_pairs):
        debug_print("All video pairs have been played")
        exit_program()
        return

    current_pair_index = pair_index
    video1_path, video2_path = video_pairs[pair_index]

    try:
        debug_print(f"Playing video pair {pair_index + 1}: {video1_path} and {video2_path}")

        # Load the videos
        player1 = pyglet.media.Player()
        player2 = pyglet.media.Player()
        source1 = pyglet.media.load(video1_path)
        source2 = pyglet.media.load(video2_path)
        player1.queue(source1)
        player2.queue(source2)

        # Play the videos
        player1.play()
        player2.play()

        # Wait for 3 seconds, then stop and play the next pair
        pyglet.clock.schedule_once(lambda dt: stop_and_play_next(player1, player2, csvwriter, video1_path, video2_path, "Success", ""), 3.0)

    except Exception as e:
        error_message = str(e)
        debug_print(f"Error playing video pair {pair_index + 1}: {error_message}")

        # Log failure and move to next pair
        stop_and_play_next(None, None, csvwriter, video1_path, video2_path, "Failure", error_message)


def play_next_pair(pair_index, csvwriter):
    """Play the next video pair, limiting playback to 3 seconds, and log results."""
    global video_pairs, current_pair_index, window1, window2

    if pair_index >= len(video_pairs):
        debug_print("All video pairs have been played")
        # Exit cleanly when all pairs are done
        pyglet.app.exit()
        return

    current_pair_index = pair_index
    video1_path, video2_path = video_pairs[pair_index]

    try:
        debug_print(f"Playing video pair {pair_index + 1}: {video1_path} and {video2_path}")

        # Load the videos
        player1 = pyglet.media.Player()
        player2 = pyglet.media.Player()
        source1 = pyglet.media.load(video1_path)
        source2 = pyglet.media.load(video2_path)
        player1.queue(source1)
        player2.queue(source2)

        # Define drawing for Participant 1 window
        @window1.event
        def on_draw():
            window1.clear()
            if player1.source and player1.texture:
                player1.texture.blit(0, 0, width=window1.width, height=window1.height)

        # Define drawing for Participant 2 window
        @window2.event
        def on_draw():
            window2.clear()
            if player2.source and player2.texture:
                player2.texture.blit(0, 0, width=window2.width, height=window2.height)

        # Play the videos
        player1.play()
        player2.play()

        # Wait for 3 seconds, then stop and move to the next pair
        pyglet.clock.schedule_once(lambda dt: stop_and_play_next(player1, player2, csvwriter, video1_path, video2_path, "Success", ""), 3.0)

    except Exception as e:
        error_message = str(e)
        debug_print(f"Error playing video pair {pair_index + 1}: {error_message}")

        # Log failure and move to next pair
        stop_and_play_next(None, None, csvwriter, video1_path, video2_path, "Failure", error_message)


if __name__ == "__main__":

    log_file = r"C:\Users\canoz\OneDrive\Masaüstü\ScratchExp\compability.csv"

    try:
        debug_print("Testing video compatibility with 3-second playback")
        play_video_pairs_consecutively(video_pairs, audio_device_1_index, audio_device_2_index, log_file)
        debug_print(f"Results saved to {log_file}")
    except Exception as e:
        debug_print(f"Critical error during compatibility testing: {str(e)}")
