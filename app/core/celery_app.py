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
def import_products_task(self, task_id: str, file_path: str) -> int:  # noqa: D401 (simple docstring)
    """Import a CSV file containing product data.

    The task streams the CSV file in batches, inserts/updates products in the
    database and writes *live* progress information to Redis so that a client
    (e.g. a React front-end) can poll and display a progress bar.

    Redis structure::

        upload:{task_id} -> {
            status: "PROCESSING" | "COMPLETED" | "FAILED",
            processed: <int>,          # rows processed (present on success)
            error: <str | null>,       # error message   (present on failure)
        }

        upload:{task_id}:progress -> {
            processed: <int>,
            total: <int>,
        }

    Parameters
    ----------
    task_id
        UUID (or any unique identifier) supplied by the caller so progress can
        be correlated with a specific file upload.
    file_path
        Absolute path to the *temporary* CSV file on disk.
    """

    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)

    status_key = f"upload:{task_id}"
    progress_key = f"{status_key}:progress"

    # The task might be submitted by the API which already set *QUEUED* – we now
    # mark it as *PROCESSING*.
    redis_client.hset(status_key, mapping={"status": "PROCESSING"})

    processed_rows: int = 0
    try:
        # Always open a dedicated SQLAlchemy session inside the task so it is
        # fully isolated from the web worker.
        with SessionLocal() as db:
            processed_rows = csv_importer.import_csv(
                db,
                Path(file_path),
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

        # Re-raise so Celery marks the task as *FAILURE* in the result backend
        # (useful for Flower / monitoring).
        raise
