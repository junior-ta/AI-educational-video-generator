import os
import uuid
from supabase import create_client, Client

SUPABASE_URL = os.environ["SUPABASE_URL"]


def get_client(use_service_key: bool = False) -> Client:
    """use_service_key=True is for the worker only — never in Streamlit."""
    key = os.environ["SUPABASE_SERVICE_KEY"] if use_service_key else os.environ["SUPABASE_ANON_KEY"]
    return create_client(SUPABASE_URL, key)


# --- Storage ---

def upload_file(client: Client, bucket: str, local_path: str, dest_path: str) -> str:
    with open(local_path, "rb") as f:
        client.storage.from_(bucket).upload(
            dest_path, f, {"content-type": "application/octet-stream", "upsert": "true"}
        )
    return dest_path


def download_to_file(client: Client, bucket: str, storage_path: str, local_path: str):
    data = client.storage.from_(bucket).download(storage_path)
    with open(local_path, "wb") as f:
        f.write(data)


def get_signed_url(client: Client, bucket: str, storage_path: str, expires_in: int = 3600) -> str:
    res = client.storage.from_(bucket).create_signed_url(storage_path, expires_in)
    return res["signedURL"]


def new_storage_path(prefix: str, filename: str) -> str:
    return f"{prefix}/{uuid.uuid4()}_{filename}"


#_____________________Jobs table___________________________

def create_full_job(client: Client, script_json, voice_skeptic, voice_expert, resolution, bg_video_path) -> str:
    row = {
        "job_type": "full",
        "script_json": script_json,
        "voice_skeptic": voice_skeptic,
        "voice_expert": voice_expert,
        "resolution": resolution,
        "bg_video_path": bg_video_path,
        "status": "pending",
    }
    res = client.table("jobs").insert(row).execute()
    return res.data[0]["id"]


def create_rerender_job(client: Client, parent_job: dict, new_captions_path: str) -> str:

    #This is used for renders taht have already been made but user decided to chnage the captions. Only the captions file changes.

    row = {
        "job_type": "rerender",
        "parent_job_id": parent_job["id"],
        "resolution": parent_job["resolution"],
        "bg_video_path": parent_job["bg_video_path"],
        "audio_path": parent_job["audio_path"],
        "captions_path": new_captions_path,
        "status": "pending",
    }
    res = client.table("jobs").insert(row).execute()
    return res.data[0]["id"]


def get_job(client: Client, job_id: str) -> dict:
    res = client.table("jobs").select("*").eq("id", job_id).single().execute()
    return res.data


def update_job(client: Client, job_id: str, **fields):
    client.table("jobs").update(fields).eq("id", job_id).execute()


def claim_next_pending_job(client: Client) -> dict | None:

    #...Because I am using one Railway worker.
  
    res = (
        client.table("jobs")
        .select("*")
        .eq("status", "pending")
        .order("created_at")
        .limit(1)
        .execute()
    )
    if not res.data:
        return None

    job = res.data[0]
    client.table("jobs").update({"status": "processing"}).eq("id", job["id"]).execute()
    return job