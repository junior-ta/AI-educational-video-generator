import os
import re
import stable_whisper

# --- Configuration ---
INPUT_AUDIO = "Script_audio.mp3"
OUTPUT_FILENAME = "Script_captions.ass"
MODEL_SIZE = "tiny"  # 'tiny', 'base', 'small', 'medium', 'large'

# Video resolution (your reel)
PLAY_RES_X = 1080
PLAY_RES_Y = 1920

# PLAY_RES_X = 720
# PLAY_RES_Y = 1280

def patch_ass_style(ass_path: str):
    """
    Patch the generated .ass file to use a bold neon-green style with thick black outline
    and correct PlayResX/PlayResY for 720x1280.
    """
    with open(ass_path, "r", encoding="utf-8") as f:
        ass = f.read()

    # Ensure Script Info contains PlayResX/PlayResY (important for sizing/positioning)
    if "PlayResX:" not in ass:
        ass = ass.replace("[Script Info]\n", f"[Script Info]\nPlayResX: {PLAY_RES_X}\nPlayResY: {PLAY_RES_Y}\n")
    else:
        ass = re.sub(r"PlayResX:\s*\d+", f"PlayResX: {PLAY_RES_X}", ass)
        ass = re.sub(r"PlayResY:\s*\d+", f"PlayResY: {PLAY_RES_Y}", ass)

    # Our target style for 720x1280:
    # - Fontsize ~90 (similar visual scale to reels caption)
    # - Neon green fill (ASS color format is &HAABBGGRR)
    #   #7CFF00 (RGB) -> RR=7C, GG=FF, BB=00 -> &H00 00 FF 7C = &H0000FF7C
    # - black outline thickness: Outline=1
    # - Shadow=0
    # - Alignment=2 bottom-center
    # - MarginV=350 pushes it upward (like your example). Tweak if needed.
    style_block= f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,Montserrat ExtraBold,68,&H0033C9FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,5,2,38,38,345,1
"""
    
    #720x1280
    style_block = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,Montserrat ExtraBold,45,&H0033C9FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,1,3,2,25,25,230,1
"""

    # Replace existing style section (from [V4+ Styles] up to before [Events])
    if "[V4+ Styles]" in ass:
        ass = re.sub(r"\[V4\+ Styles\][\s\S]*?(?=\[Events\])", style_block + "\n", ass, count=1)
    else:
        ass = ass.replace("[Events]", style_block + "\n[Events]")

    # Force all Dialogue lines to use Style "Reel"
    # Dialogue format: Dialogue: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
    ass = re.sub(r"(Dialogue:\s*\d+,\s*[^,]*,\s*[^,]*,)([^,]*)(,)", r"\1Reel\3", ass)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)

def generate_subtitles(audio_path=INPUT_AUDIO):
    """
    Transcribes the audio and generates an ASS subtitle file with Karaoke effects,
    then patches the ASS styling to match the reel look (neon green + thick outline).
    """
    if not os.path.exists(audio_path):
        print(f"Error: {audio_path} not found. Run the audio generation step first.")
        return

    model = stable_whisper.load_model(MODEL_SIZE)

    print(f"Transcribing {audio_path} (please be patient)...")
    result = model.transcribe(audio_path, regroup=False)  # regroup=False keeps word timing precise
    result.split_by_length(max_words=5)

    # Generate the .ass file (karaoke=True enables word-by-word highlighting)
    # We'll keep font parameters here, but final visual style is enforced by patch_ass_style().
    result.to_ass(
        OUTPUT_FILENAME,
        karaoke=True,
        font="Montserrat ExtraBold",
        font_size=27,               # scaled for 720x1280
        highlight_color="7CFF00",    # karaoke highlight (kept)
    )

    # Patch to add thick black outline + correct PlayRes + consistent style
    patch_ass_style(OUTPUT_FILENAME)

    print(f"Success! Subtitles saved to {OUTPUT_FILENAME}")

if __name__ == "__main__":
    generate_subtitles()
