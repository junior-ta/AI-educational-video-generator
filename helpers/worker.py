import os
import time
import traceback

import audio
import subtitles
import renderer
from supabase_helper import (
    get_client,
    download_to_file,
    upload_file,
    update_job,
    claim_next_pending_job,
    new_storage_path,
)

POLL_INTERVAL_SECONDS = 10 #time delay between job look-ups
TEMP_DIR = "worker_temp"
UPLOADS_BUCKET = "uploads"
ASSETS_BUCKET = "assets"
OUTPUTS_BUCKET = "outputs"


def cleanup(*paths):
    for p in paths:
        if p and os.path.exists(p):
            os.remove(p)


def process_full_job(client, job):
    job_id = job["id"]
    bg_local = os.path.join(TEMP_DIR, "background.mp4")
    output_local = os.path.join(TEMP_DIR, "final_output.mp4")

    print(f"[{job_id}] Downloading background video...")
    download_to_file(client, UPLOADS_BUCKET, job["bg_video_path"], bg_local)

    print(f"[{job_id}] Generating audio...")
    audio.create_podcast_audio(job["script_json"], job["voice_skeptic"], job["voice_expert"])

    print(f"[{job_id}] Generating subtitles...")
    subtitles.generate_subtitles(job["resolution"], "Script_audio.mp3")

    print(f"[{job_id}] Rendering video...")
    renderer.render_video(
        job["resolution"], bg_local, "Script_audio.mp3", "Script_captions.ass", output_file=output_local
    )

    print(f"[{job_id}] Uploading audio, captions, and video...")
    audio_dest = new_storage_path("audio", "Script_audio.mp3")
    captions_dest = new_storage_path("captions", "Script_captions.ass")
    output_dest = new_storage_path("rendered", "final_video.mp4")

    upload_file(client, ASSETS_BUCKET, "Script_audio.mp3", audio_dest)
    upload_file(client, ASSETS_BUCKET, "Script_captions.ass", captions_dest)
    upload_file(client, OUTPUTS_BUCKET, output_local, output_dest)

    update_job(
        client, job_id,
        status="done",
        audio_path=audio_dest,
        captions_path=captions_dest,
        output_video_path=output_dest,
    )

    cleanup(bg_local, output_local, "Script_audio.mp3", "Script_captions.ass")


def process_rerender_job(client, job):
    #Re-render only: reuses existing audio, uses the (edited) captions passed in.
    
    job_id = job["id"]
    bg_local = os.path.join(TEMP_DIR, "background.mp4")
    audio_local = os.path.join(TEMP_DIR, "Script_audio.mp3")
    captions_local = os.path.join(TEMP_DIR, "Script_captions.ass")
    output_local = os.path.join(TEMP_DIR, "final_output.mp4")

    print(f"[{job_id}] Downloading background video, audio, and edited captions...")
    download_to_file(client, UPLOADS_BUCKET, job["bg_video_path"], bg_local)
    download_to_file(client, ASSETS_BUCKET, job["audio_path"], audio_local)
    download_to_file(client, ASSETS_BUCKET, job["captions_path"], captions_local)

    print(f"[{job_id}] Re-rendering with updated subtitles...")
    renderer.render_video(job["resolution"], bg_local, audio_local, captions_local, output_file=output_local)

    output_dest = new_storage_path("rendered", "final_video.mp4")
    upload_file(client, OUTPUTS_BUCKET, output_local, output_dest)

    update_job(client, job_id, status="done", output_video_path=output_dest)

    cleanup(bg_local, audio_local, captions_local, output_local)


def process_job(client, job):
    os.makedirs(TEMP_DIR, exist_ok=True)
    try:
        if job.get("job_type") == "rerender":
            process_rerender_job(client, job)
        else:
            process_full_job(client, job)
        print(f"[{job['id']}] Done.")
    except Exception as e:
        print(f"[{job['id']}] FAILED: {e}")
        update_job(client, job["id"], status="error", error_message=str(e))
        traceback.print_exc()


def main():
    client = get_client(use_service_key=True)
    print("Worker s running. Polling for jobs...")
    while True:
        job = claim_next_pending_job(client)
        if job:
            print(f"Claimed {job['job_type']} job {job['id']}")
            process_job(client, job)
        else:
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()