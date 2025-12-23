import os
import stable_whisper

# --- Configuration ---
INPUT_AUDIO = "Script_audio.mp3"
OUTPUT_FILENAME = "Script_captions.ass"
MODEL_SIZE = "tiny" # 'tiny', 'base', 'small', 'medium', 'large'

def generate_subtitles(audio_path=INPUT_AUDIO):
    """
    Transcribes the audio and generates an ASS subtitle file with Karaoke effects.
    """
    if not os.path.exists(audio_path):
        print(f"Error: {audio_path} not found. Run the audio generation step first.")
        return

    #print(f"Loading Whisper model ('{MODEL_SIZE}')...")
    # Load the model
    model = stable_whisper.load_model(MODEL_SIZE)

    print(f"Transcribing {audio_path} (please be patient)...")
    result = model.transcribe(audio_path, regroup=False) # regroup=False keeps word timing precise
    
    # Generate the .ass file The ('karaoke=True' flag enables the word-by-word highlighting)
    result.to_ass(
        OUTPUT_FILENAME,
        karaoke=True,
        font="Montserrat ExtraBold",
        font_size=20,
        # ASS color format is &HAABBGGRR& (Alpha, Blue, Green, Red)
        # &H00FFFF& -> 00 Alpha, FF Blue, FF Green, 00 Red -> Cyan/Yellowish mix
        highlight_color="7CFF00" #"&H00FFFF&" 
    )
    
    print(f"Success! Subtitles saved to {OUTPUT_FILENAME}")

if __name__ == "__main__":
    generate_subtitles()