"""File upload API for product CSV imports.

This router exposes two endpoints that **coordinate** the asynchronous product
import flow executed by Celery:

1. ``POST /upload/start`` – Accepts a CSV file, writes it to ``/tmp`` and
   enqueues the :pyfunc:`app.core.celery_app.import_products_task`.  A *custom*
   ``task_id`` is generated so the caller can easily poll status **without**
   knowing the Celery task's UUID (which is still returned for debugging).

2. ``GET /upload/status/{task_id}`` – Returns *live* status and progress
   information that the Celery task stores in Redis while running.

The contract mirrors the Redis structures documented in
``app.core.celery_app.import_products_task``.
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
    """Save the uploaded *CSV* to ``/tmp`` and enqueue a Celery task.

    The endpoint is intentionally **fire-and-forget** – it returns *202
    Accepted* immediately after the task is submitted.  Callers are expected to
    poll ``GET /upload/status/{task_id}`` to track progress.
    """

    # Generate a *caller-friendly* identifier that can be embedded in Redis keys
    # and URLs without leaking the Celery UUID.
    task_id: str = uuid.uuid4().hex

    # Persist the file to a predictable location so the worker can access it.
    tmp_path: Path = Path("/tmp") / f"{task_id}.csv"

    # Stream-copy the upload to disk in chunks to keep memory usage low.
    with tmp_path.open("wb") as buffer:
        while chunk := await file.read(1024 * 1024):  # 1 MiB
            buffer.write(chunk)

    # Record initial *QUEUED* status so the first status poll has something to
    # return even if the worker has not picked up the task yet.
    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
    status_key = f"upload:{task_id}"
    redis_client.hset(status_key, mapping={"status": "QUEUED"})

    # Kick off the Celery task (non-blocking).
    celery_result = import_products_task.delay(task_id, str(tmp_path))

    return {
        "task_id": task_id,
        "celery_task_id": celery_result.id,
    }


# ---------------------------------------------------------------------------
# GET /upload/status/{task_id} – progress polling
# ---------------------------------------------------------------------------


@router.get(
    "/status/{task_id}",
    summary="Fetch import status & progress",
)
def get_status(task_id: str) -> dict[str, object]:  # noqa: D401 (simple docstring)
    """Return status/progress information stored in Redis.

    The response body contains two nested maps:

    * ``status``   – High-level task state (PROCESSING, COMPLETED, FAILED, …)
    * ``progress`` – Row counters that are updated during processing
    """

    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)

    status_key = f"upload:{task_id}"
    progress_key = f"{status_key}:progress"

    status_data = redis_client.hgetall(status_key)
    if not status_data:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Unknown task_id")

    progress_data = redis_client.hgetall(progress_key) or None  # may be empty early on

    return {
        "task_id": task_id,
        "status": status_data,
        "progress": progress_data,
    }
