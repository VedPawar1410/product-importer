"""
File upload API for product CSV imports.

This router exposes two endpoints that coordinate the asynchronous product
import flow executed by Celery:

1. POST /upload/start
2. GET /upload/status/{task_id}
"""

from __future__ import annotations

import shutil
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
def start_upload(file: UploadFile = File(...)) -> dict[str, str]:
    """
    Save the CSV to the shared upload directory → enqueue the Celery import.

    The file is copied in 1 MB chunks, so memory use stays flat whatever the
    file size. Only the task id travels through Redis, never the file itself.
    (A plain `def` route: FastAPI runs it in a thread, so the blocking file copy
    doesn't stall other requests.)
    """

    task_id: str = uuid.uuid4().hex
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / f"{task_id}.csv"

    try:
        with file_path.open("wb") as out:
            shutil.copyfileobj(file.file, out, length=1024 * 1024)

        redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
        redis_client.hset(f"upload:{task_id}", mapping={"status": "QUEUED"})

        celery_result = import_products_task.delay(task_id, str(file_path))
    except Exception as e:
        file_path.unlink(missing_ok=True)
        print(f"Upload failed: {e!r}")  # appears in Render logs
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload failed: {e}. Check that Redis and the database are reachable.",
        )

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
