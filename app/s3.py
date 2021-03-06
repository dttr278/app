from io import BytesIO
import os

import boto3
import requests

from app.config import (
    AWS_REGION,
    BUCKET,
    AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY,
    LOCAL_FILE_UPLOAD,
    UPLOAD_DIR,
    URL,
)

if not LOCAL_FILE_UPLOAD:
    _session = boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION,
    )


def upload_from_bytesio(key: str, bs: BytesIO, content_type="string"):
    bs.seek(0)

    if LOCAL_FILE_UPLOAD:
        file_path = os.path.join(UPLOAD_DIR, key)
        file_dir = os.path.dirname(file_path)
        os.makedirs(file_dir, exist_ok=True)
        with open(file_path, "wb") as f:
            f.write(bs.read())

    else:
        _session.resource("s3").Bucket(BUCKET).put_object(
            Key=key, Body=bs, ContentType=content_type
        )


def upload_from_url(url: str, upload_path):
    r = requests.get(url)
    upload_from_bytesio(upload_path, BytesIO(r.content))


def get_url(key: str, expires_in=3600) -> str:
    if LOCAL_FILE_UPLOAD:
        return URL + "/static/upload/" + key
    else:
        s3_client = _session.client("s3")
        return s3_client.generate_presigned_url(
            ExpiresIn=expires_in,
            ClientMethod="get_object",
            Params={"Bucket": BUCKET, "Key": key},
        )
