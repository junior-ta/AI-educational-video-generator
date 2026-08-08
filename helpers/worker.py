import os
import traceback

import audio
import subtitles
import renderer
from supabase_jobs import get_client, update_job, claim_next_pending_job
from r2_helper import upload_file, download_to_file, new_object_key

TEMP_DIR = "worker_temp"
UPLOADS_BUCKET = "uploads"
ASSETS_BUCKET = "assets"
OUTPUTS_BUCKET = "outputs"
MAX_JOBS_PER_RUN = 5


def cleanup(*paths):
    for p in paths:
        if p and os.path.exists(p):
            os.remove(p)


def process_full_job(client, job):
    job_id = job["id"]
    bg_local = os.path.join(TEMP_DIR, "background.mp4")
    output_local = os.path.join(TEMP_DIR, "final_output.mp4")

    download_to_file(UPLOADS_BUCKET, job["bg_video_key"], bg_local)
    audio.create_podcast_audio(job["script_json"], job["voice_skeptic"], job["voice_expert"])
    subtitles.generate_subtitles(job["resolution"], "Script_audio.mp3")
    renderer.render_video(job["resolution"], bg_local, "Script_audio.mp3", "Script_captions.ass", output_file=output_local)

    audio_key = new_object_key("audio", "Script_audio.mp3")
    captions_key = new_object_key("captions", "Script_captions.ass")
    output_key = new_object_key("rendered", "final_video.mp4")

    upload_file(ASSETS_BUCKET, "Script_audio.mp3", audio_key)
    upload_file(ASSETS_BUCKET, "Script_captions.ass", captions_key)
    upload_file(OUTPUTS_BUCKET, output_local, output_key)

    update_job(client, job_id, status="done", audio_key=audio_key, captions_key=captions_key, output_video_key=output_key)
    cleanup(bg_local, output_local, "Script_audio.mp3", "Script_captions.ass")


def process_rerender_job(client, job):
    job_id = job["id"]
    bg_local = os.path.join(TEMP_DIR, "background.mp4")
    audio_local = os.path.join(TEMP_DIR, "Script_audio.mp3")
    captions_local = os.path.join(TEMP_DIR, "Script_captions.ass")
    output_local = os.path.join(TEMP_DIR, "final_output.mp4")

    download_to_file(UPLOADS_BUCKET, job["bg_video_key"], bg_local)
    download_to_file(ASSETS_BUCKET, job["audio_key"], audio_local)
    download_to_file(ASSETS_BUCKET, job["captions_key"], captions_local)

    renderer.render_video(job["resolution"], bg_local, audio_local, captions_local, output_file=output_local)

    output_key = new_object_key("rendered", "final_video.mp4")
    upload_file(OUTPUTS_BUCKET, output_local, output_key)
    update_job(client, job_id, status="done", output_video_key=output_key)
    cleanup(bg_local, audio_local, captions_local, output_local)


def process_job(client, job):
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
    os.makedirs(TEMP_DIR, exist_ok=True)
    client = get_client(use_service_key=True)

    processed = 0
    while processed < MAX_JOBS_PER_RUN:
        job = claim_next_pending_job(client)
        if not job:
            break
        print(f"Claimed {job['job_type']} job {job['id']}")
        process_job(client, job)
        processed += 1

    print(f"Run complete. Processed {processed} job(s).")


if __name__ == "__main__":
    main()