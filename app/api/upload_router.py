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
    Accept CSV → store in Redis → enqueue Celery task
    
    For Render deployment: stores file content in Redis since disks cannot
    be shared between web and worker services. Files expire after 1 hour.
    """

    # Create a task_id used for Redis keys
    task_id: str = uuid.uuid4().hex

    # Read entire file content into memory
    file_content = await file.read()
    
    # Store file content in Redis (expires after 1 hour)
    redis_client_binary: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=False)
    file_key = f"upload:file:{task_id}"
    redis_client_binary.setex(file_key, 3600, file_content)  # 1 hour TTL

    # Create initial QUEUED status
    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
    status_key = f"upload:{task_id}"
    redis_client.hset(status_key, mapping={"status": "QUEUED"})

    # Enqueue Celery job with task_id (worker will fetch from Redis)
    celery_result = import_products_task.delay(task_id)

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
