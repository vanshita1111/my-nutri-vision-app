"""
AWS S3 image upload/download service.
Falls back to local filesystem storage when AWS credentials are absent (dev mode).
"""

import asyncio
import io
from pathlib import Path
from app.config import settings

_LOCAL_STORAGE_DIR = Path("local_image_storage")


def _is_local_mode() -> bool:
    return not settings.AWS_ACCESS_KEY_ID or settings.APP_ENV == "development"


def _get_s3_client():
    import boto3
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )


async def upload_image_bytes(image_data: bytes, job_id: str, content_type: str) -> str:
    """Upload raw image bytes; returns S3 key (or local path in dev mode)."""
    ext = "jpg" if "jpeg" in content_type else content_type.split("/")[-1]
    key = f"{settings.S3_PREFIX}/{job_id}/original.{ext}"

    if _is_local_mode():
        local_path = _LOCAL_STORAGE_DIR / key
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(image_data)
        return key

    s3 = _get_s3_client()
    await asyncio.to_thread(
        s3.upload_fileobj,
        io.BytesIO(image_data),
        settings.S3_BUCKET_NAME,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return key


async def download_image_to_temp(s3_key: str, local_path: str) -> None:
    """Download from S3 (or local dev storage) to a temp file path."""
    if _is_local_mode():
        src = _LOCAL_STORAGE_DIR / s3_key
        with open(local_path, "wb") as f:
            f.write(src.read_bytes())
        return

    s3 = _get_s3_client()
    await asyncio.to_thread(s3.download_file, settings.S3_BUCKET_NAME, s3_key, local_path)


def get_presigned_url(s3_key: str, expires_in: int = 3600) -> str:
    """Generate a presigned URL for frontend image display."""
    if _is_local_mode():
        return f"/dev/images/{s3_key}"
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key},
        ExpiresIn=expires_in,
    )
