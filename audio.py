import asyncio
import os
import json
import edge_tts
from pydub import AudioSegment

# --- Configuration ---
OUTPUT_FILE = "Script_audio.mp3"
TEMP_DIR = "temp_audio_segments"

# Voice Choices
VOICE_SKEPTIC = "en-US-GuyNeural" 
VOICE_EXPERT = "en-US-AriaNeural" 
#VOICE_EXPERT = "en-US-ChristopherNeural" 
#VOICE_EXPERT = "en-US-EricNeural" 

# Voices Adjustments
RATE_SKEPTIC = "+12%"   # Speed up for energy
PITCH_EXPERT = "-2Hz"   # Lower slightly for authority

async def generate_segment(text, speaker, index):
    """
    Generates a single audio clip for a line of dialogue.
    Returns the filename of the generated clip.
    """
    if not os.path.exists(TEMP_DIR):
        os.makedirs(TEMP_DIR)
        
    filename = f"{TEMP_DIR}/segment_{index}_{speaker}.mp3"
    
    # Determine Voice & Settings based on Speaker
    if speaker == "Skeptic":
        voice = VOICE_SKEPTIC
        rate = RATE_SKEPTIC
        pitch = "+0Hz" 
    else:
        voice = VOICE_EXPERT
        rate = "+0%"   
        pitch = PITCH_EXPERT

    # Generate Audio using 'communicate' to hit the Edge TTS API
    communicate = edge_tts.Communicate(text, voice, rate=rate, pitch=pitch)
    await communicate.save(filename)
    
    return filename

async def generate_audio(script_json):
    """
    Main function to process the entire script JSON and produce a final MP3.
    """
    print("Generating audio")
    
    temp_files = []
    combined_audio = AudioSegment.empty()
    
    # 300ms Silence to insert between speakers
    silence = AudioSegment.silent(duration=200) 

    # 1. Generate all clips
    l=0
    for i, line in enumerate(script_json):
        speaker = line.get("speaker")
        text = line.get("text")
        
        if l==0 or l%5==0:
            print("...")
        
        try:
            # Await for generation
            filename = await generate_segment(text, speaker, i)
            temp_files.append(filename)
            
            # Load the clip into pydub
            clip = AudioSegment.from_mp3(filename)
            
            # Add to main track with spacing
            combined_audio += clip + silence
            
        except Exception as e:
            print(f"Error generating line {i}: {e}")

    # 2. Export Final File
    print("Merging clips and exporting...")
    combined_audio.export(OUTPUT_FILE, format="mp3")
    print(f"Success! Saved to {OUTPUT_FILE}")

    # 3. Delete temp files
    print("Cleaning up trash...")
    for f in temp_files:
        if os.path.exists(f):
            os.remove(f)
    if os.path.exists(TEMP_DIR):
        os.rmdir(TEMP_DIR)

# --- Wrapper for Synchronous Execution ---
# Since edge-tts is async, we need this wrapper to call it from other scripts nicely.
def create_podcast_audio(script_json):
    asyncio.run(generate_audio(script_json))

# # --- Testing---
# if __name__ == "__main__":
#     with open("text.json", "r", encoding="utf-8") as f:
#         data = json.load(f)

#     test_script = data
#     # [
#     #     {"speaker": "Skeptic", "text": "Wait, so you're telling me this AI actually understands what I'm saying?"},
#     #     {"speaker": "Expert", "text": "Not exactly 'understands' in the human sense. It predicts the next most likely word based on patterns."},
#     #     {"speaker": "Skeptic", "text": "That sounds like a fancy autocomplete."},
#     #     {"speaker": "Expert", "text": "It is! But imagine an autocomplete that has read every book in the library."}
#     # ]
    
#     create_podcast_audio(test_script)