from celery import Celery

from .config import settings

celery_app = Celery(
    "product_importer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)


@celery_app.task
def example_task() -> str:
    """A placeholder Celery task."""
    # TODO: Replace with real task implementation
    return "example"

# ---------------------------------------------------------------------------
# Product import task
# ---------------------------------------------------------------------------

from contextlib import suppress
from pathlib import Path

from redis import Redis

from .database import SessionLocal
from ..services import csv_importer, webhook_service
from ..schemas.webhook import WebhookCreate


@celery_app.task(name="import_products", bind=True)
def import_products_task(self, task_id: str) -> int:  # noqa: D401 (simple docstring)
    """Import a CSV file containing product data.

    The task retrieves CSV content from Redis, processes it in batches,
    inserts/updates products in the database and writes *live* progress
    information to Redis so that a client can poll and display a progress bar.

    Redis structure::

        upload:file:{task_id} -> <binary CSV content>
        upload:{task_id} -> {
            status: "PROCESSING" | "COMPLETED" | "FAILED",
            processed: <int>,          # rows processed (present on success)
            error: <str | null>,       # error message   (present on failure)
        }

        upload:{task_id}:progress -> {
            processed_rows: <int>,
            total_rows: <int>,
            successful_rows: <int>,
            failed_rows: <int>,
        }

    Parameters
    ----------
    task_id
        UUID (or any unique identifier) supplied by the caller so progress can
        be correlated with a specific file upload.
    """

    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)
    redis_client_binary: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=False)

    status_key = f"upload:{task_id}"
    progress_key = f"{status_key}:progress"
    file_key = f"upload:file:{task_id}"

    # The task might be submitted by the API which already set *QUEUED* – we now
    # mark it as *PROCESSING*.
    redis_client.hset(status_key, mapping={"status": "PROCESSING"})

    processed_rows: int = 0
    try:
        # Retrieve file content from Redis
        file_content = redis_client_binary.get(file_key)
        if not file_content:
            raise ValueError(f"File content not found in Redis for task {task_id}")

        # Always open a dedicated SQLAlchemy session inside the task so it is
        # fully isolated from the web worker.
        with SessionLocal() as db:
            processed_rows = csv_importer.import_csv_from_content(
                db,
                file_content,
                redis_client=redis_client,
                progress_key=progress_key,
            )

            # Persist a *webhook event* so downstream services can react.  In a
            # real-world app this could enqueue another Celery task that
            # dispatches the HTTP request; for now we simply record it.
            with suppress(Exception):
                webhook_service.create_webhook(
                    db,
                    WebhookCreate(url="import.completed"),
                )

        redis_client.hset(
            status_key,
            mapping={
                "status": "COMPLETED",
                "processed": processed_rows,
            },
        )

        # Clean up file content from Redis after successful processing
        redis_client_binary.delete(file_key)

        return processed_rows

    except Exception as exc:
        # Ensure failure is visible to the caller *before* re-raising so Celery
        # can still record the traceback.
        redis_client.hset(
            status_key,
            mapping={
                "status": "FAILED",
                "error": str(exc),
            },
        )

        # Clean up file content from Redis even on failure
        try:
            redis_client_binary.delete(file_key)
        except:
            pass

        # Re-raise so Celery marks the task as *FAILURE* in the result backend
        # (useful for Flower / monitoring).
        raise
