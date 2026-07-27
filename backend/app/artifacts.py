from pathlib import Path

import boto3

from .config import Settings


def upload_artifact(path: Path, settings: Settings) -> str | None:
    if not settings.s3_endpoint_url:
        return None
    client = boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
    )
    try:
        client.head_bucket(Bucket=settings.s3_bucket)
    except client.exceptions.ClientError:
        client.create_bucket(Bucket=settings.s3_bucket)
    key = f"models/{path.name}"
    client.upload_file(str(path), settings.s3_bucket, key)
    return f"s3://{settings.s3_bucket}/{key}"
