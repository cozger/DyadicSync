import ffmpeg
from config.ffmpeg_config import get_ffmpeg_cmd

def convert_video(input_file, output_file):
    # Set the desired output format and codec
    output_format = 'mp4'
    output_codec = 'libx264'  # H.264 codec

    # Convert the video using ffmpeg
    stream = ffmpeg.input(input_file)
    stream = ffmpeg.output(stream, output_file, format=output_format, vcodec=output_codec, preset='medium', crf=23)
    ffmpeg.run(stream, cmd=get_ffmpeg_cmd())

# Example usage
input_file = r"C:\Users\canoz\OneDrive\Masaüstü\EmotionVideos\33.mp4"
output_file = r"C:\Users\canoz\OneDrive\Masaüstü\EmotionVideos\33_h264.mp4"
convert_video(input_file, output_file)