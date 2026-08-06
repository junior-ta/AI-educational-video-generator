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

PLAY_RES_XX = 720
PLAY_RES_YY = 1280

def patch_ass_style720(ass_path: str):
    """
    Patch the generated .ass file to use a bold neon-green style with thick black outline
    and correct PlayResX/PlayResY for 720x1280.
    """
    with open(ass_path, "r", encoding="utf-8") as f:
        ass = f.read()

    # Ensure Script Info contains PlayResX/PlayResY (important for sizing/positioning)
    if "PlayResX:" not in ass:
        ass = ass.replace("[Script Info]\n", f"[Script Info]\nPlayResX: {PLAY_RES_XX}\nPlayResY: {PLAY_RES_YY}\n")
    else:
        ass = re.sub(r"PlayResX:\s*\d+", f"PlayResX: {PLAY_RES_XX}", ass)
        ass = re.sub(r"PlayResY:\s*\d+", f"PlayResY: {PLAY_RES_YY}", ass)

    # Our target style for 720x1280:
    # - Fontsize ~90 (similar visual scale to reels caption)
    # - Neon green fill (ASS color format is &HAABBGGRR)
    #   #7CFF00 (RGB) -> RR=7C, GG=FF, BB=00 -> &H00 00 FF 7C = &H0000FF7C
    # - black outline thickness: Outline=1
    # - Shadow=0
    # - Alignment=2 bottom-center
    # - MarginV=350 pushes it upward (like your example). Tweak if needed.
    style_block = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,Montserrat ExtraBold,45,&H0033C9FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,1,3,5,25,25,0,1
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

def patch_ass_style1080(ass_path: str):
    with open(ass_path, "r", encoding="utf-8") as f:
        ass = f.read()

    if "PlayResX:" not in ass:
        ass = ass.replace("[Script Info]\n", f"[Script Info]\nPlayResX: {PLAY_RES_X}\nPlayResY: {PLAY_RES_Y}\n")
    else:
        ass = re.sub(r"PlayResX:\s*\d+", f"PlayResX: {PLAY_RES_X}", ass)
        ass = re.sub(r"PlayResY:\s*\d+", f"PlayResY: {PLAY_RES_Y}", ass)


    style_block = f"""[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Reel,Montserrat ExtraBold,68,&H0033C9FF,&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,5,5,38,38,0,1
"""


    # Replace existing style section (from [V4+ Styles] up to before [Events])
    if "[V4+ Styles]" in ass:
        ass = re.sub(r"\[V4\+ Styles\][\s\S]*?(?=\[Events\])", style_block + "\n", ass, count=1)
    else:
        ass = ass.replace("[Events]", style_block + "\n[Events]")

    # Force all Dialogue lines to use Style "Reel"
    ass = re.sub(r"(Dialogue:\s*\d+,\s*[^,]*,\s*[^,]*,)([^,]*)(,)", r"\1Reel\3", ass)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(ass)



def generate_subtitles(resolution, audio_path=INPUT_AUDIO):
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
        font_size=27,
        highlight_color="7CFF00",    # karaoke highlight (kept)
    )

    # Patch to add thick black outline + correct PlayRes + consistent style
    if resolution=="1280x720":
        patch_ass_style720(OUTPUT_FILENAME)
    else:
        patch_ass_style1080(OUTPUT_FILENAME)

    print(f"Success! Subtitles saved to {OUTPUT_FILENAME}")


def extract_dialogue_text(ass_path: str):
    """
    Extracts only the spoken text from Dialogue lines.
    Returns a list of strings (one per subtitle line).
    """
    lines = []
    with open(ass_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Dialogue:"):
                text = line.split(",", 9)[-1].strip()
                lines.append(text)
    return lines


def rewrite_ass_text(ass_path: str, new_lines: list[str]):
    """
    Replaces subtitle text while keeping timing/style unchanged.
    """
    out = []
    i = 0
    with open(ass_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("Dialogue:") and i < len(new_lines):
                prefix = line.split(",", 9)[:9]
                line = ",".join(prefix) + "," + new_lines[i] + "\n"
                i += 1
            out.append(line)

    with open(ass_path, "w", encoding="utf-8") as f:
        f.writelines(out)
        
# if __name__ == "__main__":
#     generate_subtitles()
