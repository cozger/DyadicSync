import os
from moviepy.editor import VideoFileClip

def convert_video_to_wav(input_dir, output_dir):
    # Check if input and output directories exist
    if not os.path.exists(input_dir):
        print(f"Error: The input directory {input_dir} does not exist.")
        return
    if not os.path.exists(output_dir):
        print(f"Error: The output directory {output_dir} does not exist.")
        return
    
    # Supported video file extensions
    supported_extensions = (".mp4", ".mpeg")

    # Loop through all supported video files in the input directory
    for filename in os.listdir(input_dir):
        if filename.endswith(supported_extensions):  # Check for supported file types
            input_file = os.path.join(input_dir, filename)
            output_file = os.path.join(output_dir, f"{os.path.splitext(filename)[0]}.wav")

            # Skip processing if the output WAV file already exists
            if os.path.exists(output_file):
                print(f"Skipping {filename} - WAV file already exists.")
                continue

            try:
                # Load the video file
                video = VideoFileClip(input_file)

                # Extract the audio
                audio = video.audio

                # Write the audio to a WAV file
                audio.write_audiofile(output_file)
                print(f"Successfully converted {filename} to WAV.")

            except Exception as e:
                print(f"Error processing {filename}: {e}")

# Set the input and output directories
input_directory = r"C:\Users\canoz\OneDrive\Masaüstü\EmotionVideos"  # Replace with the actual input directory
output_directory = r"C:\Users\canoz\OneDrive\Masaüstü\EmotionVideos"  # Replace with the actual output directory

# Convert all video files in the input directory to WAV and save to the output directory
convert_video_to_wav(input_directory, output_directory)
