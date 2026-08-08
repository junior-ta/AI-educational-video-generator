"""Used to save background uploads and to save output after compute"""

import os
import uuid
import boto3

R2_ENDPOINT = f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"


def get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=R2_ENDPOINT,
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def upload_file(bucket: str, local_path: str, key: str) -> str:
    get_r2_client().upload_file(local_path, bucket, key)
    return key


def download_to_file(bucket: str, key: str, local_path: str):
    get_r2_client().download_file(bucket, key, local_path)


def get_presigned_url(bucket: str, key: str, expires_in: int = 3600) -> str:
    return get_r2_client().generate_presigned_url(
        "get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=expires_in
    )


def new_object_key(prefix: str, filename: str) -> str:
    return f"{prefix}/{uuid.uuid4()}_{filename}"