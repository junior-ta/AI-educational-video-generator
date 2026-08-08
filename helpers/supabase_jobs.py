"""This is used for my job queue from supabase"""

import os
from supabase import create_client, Client


def get_client(use_service_key: bool = False) -> Client:
    key = os.environ["SUPABASE_SERVICE_KEY"] if use_service_key else os.environ["SUPABASE_ANON_KEY"]
    return create_client(os.environ["SUPABASE_URL"], key)


#_____________________Jobs table___________________________

def create_full_job(client: Client, script_json, voice_skeptic, voice_expert, resolution, bg_video_key) -> str:
    row = {
        "job_type": "full", "script_json": script_json, "voice_skeptic": voice_skeptic,
        "voice_expert": voice_expert, "resolution": resolution, "bg_video_key": bg_video_key,
        "status": "pending",
    }
    res = client.table("jobs").insert(row).execute()
    return res.data[0]["id"]


def create_rerender_job(client: Client, parent_job: dict, new_captions_key: str) -> str:
    row = {
        "job_type": "rerender", "parent_job_id": parent_job["id"], "resolution": parent_job["resolution"],
        "bg_video_key": parent_job["bg_video_key"], "audio_key": parent_job["audio_key"],
        "captions_key": new_captions_key, "status": "pending",
    }
    res = client.table("jobs").insert(row).execute()
    return res.data[0]["id"]


def get_job(client: Client, job_id: str) -> dict:
    res = client.table("jobs").select("*").eq("id", job_id).single().execute()
    return res.data


def update_job(client: Client, job_id: str, **fields):
    client.table("jobs").update(fields).eq("id", job_id).execute()


def claim_next_pending_job(client: Client) -> dict | None:
    res = client.table("jobs").select("*").eq("status", "pending").order("created_at").limit(1).execute()
    if not res.data:
        return None
    job = res.data[0]
    client.table("jobs").update({"status": "processing"}).eq("id", job["id"]).execute()
    return job