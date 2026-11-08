"""Database + Celery helpers for outgoing webhooks, including the delivery log.

Every delivery attempt is recorded in `webhook_deliveries` (status code,
response time, error), so you can see whether a receiver actually got an
event. Transient failures are retried by Celery with a growing delay.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Sequence
from urllib.parse import urlsplit

import requests
from sqlalchemy.orm import Session

from ..core.celery_app import celery_app
from ..core.database import SessionLocal
from ..models.webhook import Webhook as WebhookModel
from ..models.webhook import WebhookDelivery
from ..schemas.webhook import WebhookCreate

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (10, 60)  # wait before attempt 2 and attempt 3


# ---------------------------------------------------------------------------
# CRUD helpers (sync – used by FastAPI routes)
# ---------------------------------------------------------------------------


def create_webhook(db: Session, webhook_in: WebhookCreate) -> WebhookModel:
    """Persist a new :class:`~app.models.webhook.Webhook`."""

    webhook = WebhookModel(**webhook_in.model_dump())
    db.add(webhook)
    db.commit()
    db.refresh(webhook)
    return webhook


def list_webhooks(db: Session) -> Sequence[WebhookModel]:
    """Return all webhooks ordered by *created_at*, each with its latest delivery.

    The latest delivery per webhook comes from a single DISTINCT ON query
    rather than one query per webhook (avoids the N+1 pattern).
    """

    hooks = db.query(WebhookModel).order_by(WebhookModel.created_at).all()
    latest = (
        db.query(WebhookDelivery)
        .distinct(WebhookDelivery.webhook_id)
        .order_by(WebhookDelivery.webhook_id, WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
        .all()
    )
    by_webhook = {d.webhook_id: d for d in latest}
    for hook in hooks:
        hook.last_delivery = by_webhook.get(hook.id)  # read by the response schema
    return hooks


def get_webhook(db: Session, webhook_id: int) -> WebhookModel | None:
    return db.get(WebhookModel, webhook_id)


def delete_webhook(db: Session, webhook_id: int) -> None:  # noqa: D401 (simple docstring)
    """Delete a webhook (and, via ON DELETE CASCADE, its delivery log). Idempotent."""

    db.query(WebhookModel).filter_by(id=webhook_id).delete()
    db.commit()


def list_deliveries(db: Session, webhook_id: int, limit: int = 20) -> Sequence[WebhookDelivery]:
    """Most recent delivery attempts for one webhook, newest first."""

    return (
        db.query(WebhookDelivery)
        .filter_by(webhook_id=webhook_id)
        .order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id.desc())
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def send_once(
    db: Session, webhook: WebhookModel, event: str, payload: dict[str, Any], attempt: int = 1
) -> WebhookDelivery:
    """POST one event to one webhook, record the attempt and return it.

    Used by the Celery delivery task and, synchronously, by the Test endpoint.
    A delivery succeeds on any 2xx/3xx response; the error text explains everything else.
    """

    status_code: int | None = None
    error: str | None = None
    started = time.perf_counter()
    try:
        response = requests.post(webhook.url, json={"event": event, "data": payload}, timeout=TIMEOUT_SECONDS)
        status_code = response.status_code
        if not response.ok:
            error = f"HTTP {response.status_code} {response.reason or ''}".strip()
    except requests.Timeout:
        error = f"Timed out after {TIMEOUT_SECONDS}s"
    except requests.RequestException as exc:
        error = describe_error(exc, webhook.url)
    elapsed_ms = (time.perf_counter() - started) * 1000

    delivery = WebhookDelivery(
        webhook_id=webhook.id,
        event=event,
        success=error is None,
        status_code=status_code,
        response_ms=round(elapsed_ms, 1),
        error=error,
        attempt=attempt,
    )
    db.add(delivery)
    db.commit()
    db.refresh(delivery)
    return delivery


def describe_error(exc: requests.RequestException, url: str) -> str:
    """A short, human-readable reason instead of urllib3's long repr.

    (urllib3's text says "Max retries exceeded", which is about its own
    connection pool, not our retries, so it would also mislead.)
    """

    host = urlsplit(url).hostname or url
    text = str(exc)
    if isinstance(exc, requests.exceptions.SSLError):
        return f"TLS/SSL error with {host}"
    if isinstance(exc, requests.ConnectionError):
        if any(s in text for s in ("NameResolutionError", "Name or service not known", "nodename nor servname")):
            return f"Could not resolve host {host}"
        if "Connection refused" in text or "Errno 111" in text or "Errno 61" in text:
            return f"Connection refused by {host}"
        return f"Could not connect to {host}"
    return f"{type(exc).__name__}: {text}"[:300]


def is_retryable(delivery: WebhookDelivery) -> bool:
    """Network errors, timeouts, 429 and 5xx may succeed later; other 4xx won't."""

    code = delivery.status_code
    return code is None or code == 429 or code >= 500


# ---------------------------------------------------------------------------
# Event dispatching
# ---------------------------------------------------------------------------


def dispatch_event(event: str, payload: dict[str, Any] | None = None) -> None:  # noqa: D401
    """Enqueue one delivery task per webhook subscribed to *event*.

    One task per receiver means a slow or failing receiver is retried on its
    own, without delaying or re-sending to the others.
    """

    payload = payload or {}
    with SessionLocal() as db:
        webhook_ids = [row.id for row in db.query(WebhookModel.id).filter_by(event=event)]
    logger.info("Dispatching webhook event '%s' to %s targets", event, len(webhook_ids))
    for webhook_id in webhook_ids:
        deliver_webhook.delay(webhook_id, event, payload)


@celery_app.task(name="webhook.deliver", bind=True, max_retries=MAX_ATTEMPTS - 1)
def deliver_webhook(self, webhook_id: int, event: str, payload: dict[str, Any]) -> None:
    """Deliver one event to one webhook, retrying transient failures."""

    attempt = self.request.retries + 1
    with SessionLocal() as db:
        webhook = db.get(WebhookModel, webhook_id)
        if webhook is None:
            return  # deleted since the event was dispatched
        delivery = send_once(db, webhook, event, payload, attempt)
        should_retry = not delivery.success and is_retryable(delivery) and attempt < MAX_ATTEMPTS

    if should_retry:
        logger.warning("Webhook %s attempt %s failed; retrying", webhook_id, attempt)
        raise self.retry(countdown=RETRY_DELAYS_SECONDS[attempt - 1])
