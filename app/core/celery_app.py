from pathlib import Path

from celery import Celery
from redis import Redis

from .config import settings

celery_app = Celery(
    "product_importer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Imported after celery_app exists: webhook_service registers its own task on it.
from .database import SessionLocal  # noqa: E402
from ..services import csv_importer, webhook_service  # noqa: E402

# Status/progress records only matter while someone is watching the import.
# Expiring them keeps the small free-tier Redis (noeviction policy) from filling up.
STATUS_TTL_SECONDS = 24 * 60 * 60


# ---------------------------------------------------------------------------
# Product import task
# ---------------------------------------------------------------------------


@celery_app.task(name="import_products", bind=True)
def import_products_task(self, task_id: str, file_path: str) -> int:
    """Import the CSV saved at *file_path* and report progress in Redis.

    Redis structure::

        upload:{task_id} -> {
            status: "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED",
            processed: <int>,          # rows imported (on success)
            error: <str>,              # error message (on failure)
        }

        upload:{task_id}:progress -> {
            processed_rows, total_rows, successful_rows, failed_rows
        }

    The upload is deleted afterwards, whether the import succeeded or not.
    """

    redis_client: Redis = Redis.from_url(settings.celery_broker_url, decode_responses=True)

    status_key = f"upload:{task_id}"
    progress_key = f"{status_key}:progress"

    redis_client.hset(status_key, mapping={"status": "PROCESSING"})

    try:
        # A dedicated session inside the task, fully isolated from the web process.
        with SessionLocal() as db:
            processed_rows = csv_importer.import_csv(
                db,
                file_path,
                redis_client=redis_client,
                progress_key=progress_key,
            )

        redis_client.hset(
            status_key,
            mapping={
                "status": "COMPLETED",
                "processed": processed_rows,
            },
        )

        # Notify every webhook subscribed to "import.completed" (sent by a
        # separate Celery task, so a slow receiver can't hold up the import).
        try:
            webhook_service.dispatch_event(
                "import.completed",
                {"task_id": task_id, "processed_rows": processed_rows},
            )
        except Exception as exc:  # noqa: BLE001 – a webhook problem must not fail the import
            print(f"Could not enqueue import.completed webhooks: {exc}")

        return processed_rows

    except Exception as exc:
        # Make the failure visible to the polling UI before re-raising, so
        # Celery still records the traceback.
        redis_client.hset(status_key, mapping={"status": "FAILED", "error": str(exc)})
        raise

    finally:
        Path(file_path).unlink(missing_ok=True)
        redis_client.expire(status_key, STATUS_TTL_SECONDS)
        redis_client.expire(progress_key, STATUS_TTL_SECONDS)
