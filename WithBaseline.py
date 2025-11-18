import threading
import time
import os
import tempfile
import sounddevice as sd
import soundfile as sf
import ffmpeg
import pyglet
import keyboard # type: ignore
import pandas as pd
from pyglet.window import key
import numpy as np
from pylsl import StreamInfo, StreamOutlet
from config.ffmpeg_config import get_ffmpeg_cmd

# LSL Initiation
info = StreamInfo(name='ExpEvent_Markers', type='Markers', channel_count=1,
                  channel_format='int32', source_id='uniqueid12345')
# Initialize the stream.
outlet = StreamOutlet(info)

audio_device_1_index = 9
audio_device_2_index = 7

baseline_length = 240 #Baseline recording length in seconds

# Global variables
exit_event = threading.Event()
pyglet_running = threading.Event()
rating_complete = threading.Event()
phase = None    #keeps track of what phase the exp is at
current_pair_index = 0
completed_videos = 0  # Track completed videos for each pair
window1 = None
window2 = None
cross1 = None
cross2 = None
ratings_data = []
audio_offset_ms = 350  # Positive value means audio starts earlier by this many milliseconds

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
        outlet.push_sample(x=[300000 + current_pair_index*100 + rating])  # Send LSL marker for Participant 1
        debug_print(f"Participant 1 Resp marker sent: {300000 + current_pair_index*100 + rating}")
        ratings_data.append(('P1', rating))
        response1.text = f"Response recorded: {rating}"
        p1_responded = True
        debug_print(f"Participant 1 responded: {rating}")

    # Handle Participant 2 input
    elif symbol in participant_2_keys and not p2_responded:
        rating = participant_2_keys[symbol]
        outlet.push_sample(x=[500000 + current_pair_index*100 + rating])  # Send LSL marker for Participant 2
        debug_print(f"Participant 2 Resp marker sent: {500000 + current_pair_index*100 + rating}")
        ratings_data.append(('P2', rating))
        response2.text = f"Response recorded: {rating}"
        p2_responded = True
        debug_print(f"Participant 2 responded: {rating}")

    # Check if both participants have responded
    if p1_responded and p2_responded:
        debug_print("Both responses received. Setting rating_complete.")
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
csv_path = r"D:\Projects\DyadicSync\video_pairs_extended.csv"
video_pairs = load_video_pairs_from_csv(csv_path)


def show_welcome_screen():
    """Run welcome screen on both video monitors"""
    global HeadsetP1, HeadsetP2, window1, window2, phase
    phase = "welcome"  # Set the current phase to 'welcome'
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


        # Track the current phase of the experiment
        @window1.event
        def on_draw():
            global phase
            window1.clear()

            if phase == "welcome":
                debug_print("Drawing welcome screen on window 1.")
                welcome_batch1.draw()
            elif phase == "baseline" and cross1.active:
                debug_print("Drawing cross on window 1.")
                cross1.draw()
            elif phase == "videos":
                debug_print("Rendering video on window 1.")
                if player1 and player1.player.source and player1.player.texture:
                    player1.player.texture.blit(0, 0, width=window1.width, height=window1.height)

        @window2.event
        def on_draw():
            global phase
            window2.clear()

            if phase == "welcome":
                debug_print("Drawing welcome screen on window 2.")
                welcome_batch2.draw()
            elif phase == "baseline" and cross2.active:
                debug_print("Drawing cross on window 2.")
                cross2.draw()
            elif phase == "videos":
                debug_print("Rendering video on window 2.")
                if player2 and player2.player.source and player2.player.texture:
                    player2.player.texture.blit(0, 0, width=window2.width, height=window2.height)

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
                self.player.delete()  # Properly releases resources.
                self.player = None
            self.audio_data = None
            self.samplerate = None
            debug_print(f"Stopped player for video: {self.video_path}")
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

def display_cross_for_duration(duration_seconds, on_complete):
    global window1, window2, cross1, cross2, phase

    display = pyglet.display.get_display()
    screens = display.get_screens()

    # Create windows for cross display
    window1 = pyglet.window.Window(fullscreen=True, screen=screens[1])
    window2 = pyglet.window.Window(fullscreen=True, screen=screens[2])

    if cross1 is None or cross2 is None:
        debug_print("Cross displays not initialized, creating new CrossDisplay instances.")
        cross1 = CrossDisplay(window1)
        cross2 = CrossDisplay(window2)

    debug_print(f"Displaying cross for {duration_seconds} seconds.")
    cross1.active = True
    cross2.active = True

    debug_print(f"Marker sent: {8888} for Baseline Start.")
    outlet.push_sample([8888])

    @window1.event
    def on_draw():
        window1.clear()
        if cross1.active:
            debug_print("Drawing Cross 1.")
            cross1.draw()

    @window2.event
    def on_draw():
        window2.clear()
        if cross2.active:
            debug_print("Drawing Cross 2.")
            cross2.draw()

    def stop_cross_display(dt):
        global window1, window2, cross1, cross2
        debug_print("Stopping cross display.")

        # Deactivate crosses
        cross1.active = False
        cross2.active = False

        debug_print(f"Marker sent: {9999} for Baseline End.")
        outlet.push_sample([9999])

        # Close the windows
        if window1:
            debug_print("Closing window 1.")
            window1.close()
            window1 = None

        if window2:
            debug_print("Closing window 2.")
            window2.close()
            window2 = None

        # Reset cross displays
        cross1 = None
        cross2 = None

        # Exit Pyglet event loop
        pyglet.app.exit()

        # Call the completion callback
        on_complete()

    # Schedule cross display stop after duration
    pyglet.clock.schedule_once(stop_cross_display, duration_seconds)
    debug_print("Starting Pyglet event loop for cross display.")
    pyglet.app.run()


def video_finished_callback(player_index, player):
    global completed_videos
    completed_videos += 1
    debug_print(f"Video {player_index} finished. Total completed: {completed_videos}")
    
    # Stop the specific player safely
    try:
        player.stop()
    except Exception as e:
        debug_print(f"Error stopping player {player_index}: {str(e)}")
    
    # Trigger cleanup only if both videos are done
    if completed_videos == 2:
        debug_print("Both videos completed. Proceeding with cleanup.")
        handle_playback_end(0)

def handle_playback_end(dt):
            global player1, completed_videos

            try:
                if completed_videos < 2:
                    debug_print("Waiting for both videos to complete before cleanup.")
                    return

                debug_print("Both videos finished. Cleaning up players and audio.")
                if player1:
                    player1.stop()
                if player2:
                    player2.stop()

                # Stop audio streams
                sd.stop()
                debug_print("Audio streams stopped.")

                # Reset global variables
                completed_videos = 0

                # Proceed to the next screen
                debug_print("Transitioning to rating screen.")
                create_rating_screen()

            except Exception as e:
                debug_print(f"Error during playback cleanup: {str(e)}")

def run_video_audio_sync(video1_path, video2_path, audio_device_1_index, audio_device_2_index, on_finish_callback):
    global window1, window2, cross1, cross2, player1, player2
    
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
                        
            # Validate both players after preparation
            if not (player1.player and player1.player.source):
                debug_print("Player 1 failed to prepare properly")
                prep_success = False
            if not (player2.player and player2.player.source):
                debug_print("Player 2 failed to prepare properly")
                prep_success = False

            if not prep_success:
                debug_print("Skipping video pair due to preparation failure")
                pyglet.clock.schedule_once(on_finish_callback, 1)
                return
                
            def player1_eos_handler():
                debug_print(f"Marker sent: {2100 + current_pair_index} for Participant 1 Video completion.")
                outlet.push_sample([2100 + current_pair_index])
                video_finished_callback(1, player1)

            def player2_eos_handler():
                debug_print(f"Marker sent: {2200 + current_pair_index} for Participant 2 Video completion.")
                outlet.push_sample([2200 + current_pair_index])
                video_finished_callback(2, player2)

            player1.player.on_eos = player1_eos_handler
            player2.player.on_eos = player2_eos_handler

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
            elif player1 and player1.player and player1.player.source and player1.player.texture:
                player1.player.texture.blit(0, 0, width=window1.width, height=window1.height)

        @window2.event
        def on_draw():
            window2.clear()
            if cross2.active:
                cross2.draw()
            elif player2 and player2.player and player2.player.source and player2.player.texture:
                player2.player.texture.blit(0, 0, width=window2.width, height=window2.height)

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
                    outlet.push_sample(x=[1000+current_pair_index])
                    audio_thread1.start()
                    audio_thread2.start()
                
                # Schedule cleanup using exact duration
                debug_print(f"Scheduling cleanup in {video_duration} seconds")
                pyglet.clock.schedule_once(handle_playback_end, video_duration + 0.1)  # Add small buffer
                
            except Exception as e:
                debug_print(f"Error in start_playback: {str(e)}")
                handle_playback_end(0)
                
        # Start playback after a delay
        pyglet.clock.schedule_once(start_playback, 3)       #The 3 seconds here is for the fixation cross. maybe it shouldn't be hard coded...
        
    except Exception as e:
        debug_print(f"Fatal error in video sync: {str(e)}")
        pyglet.clock.schedule_once(on_finish_callback, 1)

def play_next_pair(dt):
    global current_pair_index
    
    if exit_event.is_set():
        return
    
    debug_print(f"play_next_pair called with current_pair_index: {current_pair_index}")
    
    if current_pair_index < len(video_pairs):
        next_video1, next_video2 = video_pairs[current_pair_index]
        debug_print(f"Starting to play pair {current_pair_index + 1} of {len(video_pairs)}")
        debug_print(f"Video 1: {next_video1}")
        debug_print(f"Video 2: {next_video2}")
        current_pair_index += 1  # Increment before running video
        run_video_audio_sync(next_video1, next_video2, audio_device_1_index, audio_device_2_index, play_next_pair)
    else:
        debug_print("All videos completed")
        exit_program()

def exit_program():
    debug_print("Initiating program exit")
    sd.stop()
    exit_event.set()
    if pyglet_running.is_set():
        pyglet.app.exit()
    os._exit(1)

def create_rating_screen():
    debug_print("Creating rating screen.")
    global response1, response2, p1_responded, p2_responded, rating_complete
    
    # Reset participant responses
    p1_responded = False
    p2_responded = False
    rating_complete.clear()


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

    # Schedule periodic activation of input window
    pyglet.clock.schedule_interval(ensure_input_window_active, 1.0)

    def check_rating_complete(dt):
        """Periodically check if both participants have responded."""
        if rating_complete.is_set():
            debug_print("Both participants responded. Completing ratings.")
            save_ratings()
            pyglet.clock.unschedule(check_rating_complete)  # Stop periodic checks
            rating_complete.set()  # Signal completion
            debug_print("Exiting pyglet event loop.")
            #pyglet.app.exit()  # Close the app loop for this phase
            
            # Trigger the next video pair
            pyglet.clock.schedule_once(play_next_pair, 0.1)  # Slight delay for clean transition

    # Schedule periodic check for rating completion
    pyglet.clock.schedule_interval(check_rating_complete, 0.1)
    debug_print("Scheduled check_rating_complete to monitor responses.")

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
        file_path = 'experiment_data.csv'               #The naming scheme should be improved later(soft coded directory+timestamp)
        if os.path.exists(file_path):
            df.to_csv(file_path, mode='a', header=False, index=False)
        else:
            df.to_csv(file_path, index=False)
            
        debug_print(f"Ratings saved for video pair {current_pair_index}")
        
    except Exception as e:
        debug_print(f"Error saving ratings: {str(e)}")

def play_video_pairs_consecutively(video_pairs_input, audio_device_1_index, audio_device_2_index):
    global window1, window2, cross1, cross2, video_pairs, current_pair_index, phase
    phase = "videos"
    video_pairs = video_pairs_input.copy()
    current_pair_index = 0
    
    try:
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
        while not exit_event.is_set():
            if keyboard.is_pressed('esc'):
                exit_program()
                break
            time.sleep(0.1)

    key_listener_thread = threading.Thread(target=listen_for_exit)
    key_listener_thread.daemon = True
    key_listener_thread.start()

    if video_pairs:
        debug_print("Starting first video pair")
        pyglet_running.set()
        play_next_pair(0)
        try:
            pyglet.app.run()
        except Exception as e:
            debug_print(f"Error in pyglet app run: {str(e)}")
        finally:
            pyglet_running.clear()

if __name__ == "__main__":
    debug_print("Program starting")
    try:
        # Run the welcome screen and then proceed
        if show_welcome_screen():
            display_cross_for_duration(
                baseline_length,
                lambda: play_video_pairs_consecutively(video_pairs, audio_device_1_index, audio_device_2_index)
            )
            pyglet.app.run()
    except Exception as e:
        debug_print(f"Main program error: {str(e)}")
