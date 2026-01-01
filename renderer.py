import subprocess
import random
import os
import json

# --- Configuration ---
OUTPUT_VIDEO = "final_video.mp4"

def get_duration(file_path):
    """
    Uses ffprobe to get the duration of a media file in seconds.
    """
    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "json", 
        file_path
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        return float(data['format']['duration'])
    except Exception as e:
        print(f"Error probing {file_path}: {e}")
        return 0.0

def render_video(resolution, background_video, audio, subtitles, output_file=OUTPUT_VIDEO):
    """
    Combines background video, audio, and subtitles into a Reel/TikTok ready file.
    """
    if not os.path.exists(background_video):
        print(f"Error: Background video '{background_video}' not found.")
        return

    # 1. Probe durations
    print("Probing asset durations...")
    audio_duration = get_duration(audio)
    bg_duration = get_duration(background_video)
    
    print(f"Audio Duration: {audio_duration:.2f}s")
    print(f"Background Duration: {bg_duration:.2f}s")

    # 2. Select Random Start Point
    if bg_duration > audio_duration:
        max_start = bg_duration - audio_duration
        start_time = random.uniform(0, max_start)
        print(f"Selected random start time: {start_time:.2f}s")
    else:
        print("Warning: Background video is shorter than audio. Looping might be required (defaulting to start 0).")
        start_time = 0

        # 3. Build FFmpeg Command
    if resolution=="1280x720":
        #1280*720
        vf = (
        f"[0:v]"
        f"scale=720:1280,"
        f"ass={subtitles}"
        f"[outv]"
    )

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", background_video,
            "-i", audio,
            "-filter_complex", vf,
            "-map", "[outv]",
            "-map", "1:a",
            "-shortest",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            output_file
        ]
    else: #1080p
        vf = (
        f"[0:v]"
        f"scale=1080:1920,"
        f"ass={subtitles}"
        f"[outv]"
    )

        cmd = [
            "ffmpeg",
            "-y",
            "-ss", str(start_time),
            "-i", background_video,
            "-i", audio,
            "-filter_complex", vf,
            "-map", "[outv]",
            "-map", "1:a",
            "-shortest",
            "-c:v", "libx264",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            output_file
        ]



    print("Rendering video... (This involves video encoding and may take time)")
    try:
        # We print the command for debugging if it fails again
        # print("Running command:", " ".join(cmd))
        subprocess.run(cmd, check=True)
        print(f"\nSuccess! Video rendered to: {output_file}")
    except subprocess.CalledProcessError as e:
        print(f"FFmpeg Error: {e}")

# if __name__ == "__main__":
#     # Test Run
#     bg = "background.mp4" 
#     aud = "Script_audio.mp3"
#     subs = "Script_captions.ass"
    
#     if os.path.exists(bg) and os.path.exists(aud) and os.path.exists(subs):
#         render_video(bg, aud, subs)
#     else:
#         print(f"Test skipped. Please ensure {bg}, {aud}, and {subs} exist.")