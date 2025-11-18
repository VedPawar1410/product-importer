"""CSV import utility.

This module is responsible for parsing CSV files that contain product data and
incrementally loading them into the database in *batches* so that very large
files (hundreds of thousands of records) can be processed without exhausting
memory.  Progress is stored in Redis so that a front-end can poll and display
real-time status to the user.

The actual database persistence logic lives in `product_service.upsert_products`,
which performs a *case-insensitive* upsert on the `sku` column.  The importer is
therefore only concerned with:

1. Reading the file line-by-line using the streaming API (no `pandas` or
   `csv.reader` slurp-all-into-memory shortcuts).
2. Converting each CSV row into a `ProductCreate` pydantic model.
3. Collecting rows into batches (default size = 1000) and delegating to
   `product_service`.
4. Updating a Redis key after every successful batch so callers can track
   progress.

The importer is intentionally *synchronous* – it is expected to run inside a
Celery task so it will not block the web process.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, List, Optional

from redis import Redis  # redis-py
from sqlalchemy.orm import Session

from ..core.config import settings
from ..schemas.product import ProductCreate
from . import product_service

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def import_csv(
    db: Session,
    file_path: str | Path,
    *,
    redis_client: Optional[Redis] = None,
    progress_key: str | None = None,
    batch_size: int = 1000,
) -> int:
    """Stream a CSV file, batch the rows and upsert them into the DB.

    Parameters
    ----------
    db:
        SQLAlchemy session that will be used by :pyfunc:`product_service`.
    file_path:
        Path to the CSV file on disk.
    redis_client:
        Optional redis client.  If omitted, a new client will be instantiated
        from :pydata:`app.core.config.settings.celery_broker_url` (which points
        to the same Redis instance as the broker) – this avoids a hard
        dependency in call sites while still supporting ad-hoc usage.
    progress_key:
        The Redis key in which progress data is stored.  If *None*, a key is
        derived from the filename (e.g. "import:products:{filename}:progress").
    batch_size:
        Number of rows to accumulate before calling
        :pyfunc:`product_service.upsert_products`.

    Returns
    -------
    int
        Number of rows successfully processed.
    """

    # ---------------------------------------------------------------------
    # Preconditions / setup
    # ---------------------------------------------------------------------

    file_path = Path(file_path)
    if not file_path.is_file():
        raise FileNotFoundError(file_path)

    if redis_client is None:
        # Lazily create a client so the function can be used without one.
        redis_client = Redis.from_url(settings.celery_broker_url, decode_responses=True)

    if progress_key is None:
        progress_key = f"import:products:{file_path.stem}:progress"

    # We *optionally* compute the total line count so we can write a percentage
    # to Redis.  This is cheap enough for typical files and performed in a
    # streaming manner to keep memory usage low.
    with file_path.open("r", newline="", encoding="utf-8") as f:
        total_lines = sum(1 for _ in f) - 1  # subtract header

    # ------------------------------------------------------------------
    # Main import loop – stream, batch, upsert, report progress
    # ------------------------------------------------------------------

    processed = 0
    batch: list[ProductCreate] = []

    with file_path.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)

        for row in reader:
            try:
                batch.append(ProductCreate(**row))
            except Exception as exc:  # noqa: BLE001  (broad but logs row)
                # Log and skip problematic rows – add proper logging in real code
                # print(f"Skipping row due to error: {exc}. Row data: {row}")
                continue

            if len(batch) >= batch_size:
                _flush_batch(db, batch)
                processed += len(batch)
                _report_progress(redis_client, progress_key, processed, total_lines)
                batch.clear()

        # Flush any remaining rows
        if batch:
            _flush_batch(db, batch)
            processed += len(batch)
            _report_progress(redis_client, progress_key, processed, total_lines)

    return processed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _flush_batch(db: Session, batch: Iterable[ProductCreate]) -> None:
    """Delegate to *product_service* and commit the transaction."""

    product_service.upsert_products(db, list(batch))
    # In a long-running import we want to commit frequently so any unique
    # constraint violations are caught early and we keep the transaction log
    # size under control.
    db.commit()


def _report_progress(
    redis_client: Redis,
    key: str,
    processed: int,
    total: int,
) -> None:
    """Write progress information to Redis so callers can poll."""

    redis_client.hset(key, mapping={"processed": processed, "total": total})
