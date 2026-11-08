"""CSV import utility.

Streams a CSV file from disk, validates each row, upserts products in batches
and writes live progress to Redis so the frontend can show a progress bar.

Memory stays flat whatever the file size: rows are read one at a time and only
`batch_size` rows are held before they're written. The database work lives in
`product_service.upsert_products` (case-insensitive upsert on SKU).

Runs synchronously inside the Celery worker, never in the web process.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from redis import Redis
from sqlalchemy.orm import Session

from ..schemas.product import ProductCreate
from . import product_service

# "utf-8-sig" also accepts files saved by Excel, which start with a byte-order mark.
ENCODING = "utf-8-sig"


def import_csv(
    db: Session,
    file_path: str | Path,
    *,
    redis_client: Redis,
    progress_key: str,
    batch_size: int = 1000,
) -> int:
    """Import every valid row of the CSV at *file_path*; return the number imported.

    Invalid rows (missing sku/name, unparseable price...) are skipped and counted
    as ``failed_rows`` in the progress record.
    """

    file_path = Path(file_path)

    # First pass: count data rows so progress can show a percentage. Counting CSV
    # records (not newlines) stays correct for quoted multi-line fields and files
    # without a trailing newline.
    with file_path.open("r", newline="", encoding=ENCODING) as f:
        total = max(sum(1 for _ in csv.reader(f)) - 1, 0)  # minus the header

    processed = 0
    failed = 0
    batch: list[ProductCreate] = []

    with file_path.open("r", newline="", encoding=ENCODING) as f:
        for row in csv.DictReader(f):
            product = _parse_row(row)
            if product is None:
                failed += 1  # counted and reported, never silently dropped
                continue
            batch.append(product)

            if len(batch) >= batch_size:
                _flush_batch(db, batch)
                processed += len(batch)
                _report_progress(redis_client, progress_key, processed, total, failed)
                batch.clear()

    # Flush the remainder (and always report, so failures-only files show up)
    if batch:
        _flush_batch(db, batch)
        processed += len(batch)
    _report_progress(redis_client, progress_key, processed, total, failed)

    return processed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_row(row: dict) -> ProductCreate | None:
    """Validate one CSV row. Empty cells mean "no value"; returns None for invalid rows."""

    cleaned = {k: (v if v not in ("", None) else None) for k, v in row.items() if k}
    try:
        return ProductCreate(**cleaned)
    except Exception:  # noqa: BLE001 – any validation error makes the row invalid
        return None


def _flush_batch(db: Session, batch: Iterable[ProductCreate]) -> None:
    """Upsert one batch and commit, so progress is durable and transactions stay small."""

    product_service.upsert_products(db, list(batch))
    db.commit()


def _report_progress(
    redis_client: Redis,
    key: str,
    processed: int,
    total: int,
    failed: int = 0,
) -> None:
    """Write progress information to Redis so callers can poll."""

    redis_client.hset(
        key,
        mapping={
            "processed_rows": processed + failed,
            "total_rows": total,
            "successful_rows": processed,
            "failed_rows": failed,
        }
    )
