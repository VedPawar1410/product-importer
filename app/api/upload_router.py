"""
File upload API for product CSV imports.

This router exposes two endpoints that coordinate the asynchronous product
import flow executed by Celery:

1. POST /upload/start
2. GET /upload/status/{task_id}
"""

from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from redis import Redis

from ..core.config import settings
from ..core.celery_app import import_products_task


router = APIRouter(prefix="/upload", tags=["upload"])


# ---------------------------------------------------------------------------
# POST /upload/start – enqueue import job
# ---------------------------------------------------------------------------

@router.post(
    "/start",
    summary="Start a new product import",
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_upload(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Accept CSV → save to shared Docker volume → enqueue Celery task
    """

    # Create a task_id used for filenames + Redis keys
    task_id: str = uuid.uuid4().hex

    # Persistent folder accessible by both web + worker containers
    # Uses /data for Render, compatible with /shared for local Docker
    upload_dir = Path("/data/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded file into persistent volume
    tmp_path = upload_dir / f"{task_id}.csv"

    with tmp_path.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1 MB chunks
            buffer.write(chunk)

    # Create initial QUEUED status
    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
    status_key = f"upload:{task_id}"
    redis_client.hset(status_key, mapping={"status": "QUEUED"})

    # Enqueue Celery job
    celery_result = import_products_task.delay(task_id, str(tmp_path))

    return {
        "task_id": task_id,
        "celery_task_id": celery_result.id,
    }


# ---------------------------------------------------------------------------
# GET /upload/status/{task_id}
# ---------------------------------------------------------------------------

@router.get(
    "/status/{task_id}",
    summary="Fetch import status & progress",
)
def get_status(task_id: str) -> dict[str, object]:
    """
    Poll Redis for task status and progress
    """

    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)

    status_key = f"upload:{task_id}"
    progress_key = f"{status_key}:progress"

    status_data = redis_client.hgetall(status_key)
    if not status_data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown task_id")

    progress_data = redis_client.hgetall(progress_key) or None

    return {
        "task_id": task_id,
        "status": status_data,
        "progress": progress_data,
    }
