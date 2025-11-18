"""Database + Celery helpers related to outgoing webhooks."""

from __future__ import annotations

import logging
from typing import Sequence, Any

import requests
from sqlalchemy.orm import Session

from ..core.database import SessionLocal
from ..core.celery_app import celery_app
from ..models.webhook import Webhook as WebhookModel
from ..schemas.webhook import WebhookCreate

logger = logging.getLogger(__name__)


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
    """Return all webhooks ordered by *created_at*."""

    return db.query(WebhookModel).order_by(WebhookModel.created_at).all()


def delete_webhook(db: Session, webhook_id: int) -> None:  # noqa: D401 (simple docstring)
    """Delete a webhook – silently ignored if it does not exist."""

    db.query(WebhookModel).filter_by(id=webhook_id).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Event dispatching
# ---------------------------------------------------------------------------


def dispatch_event(event: str, payload: dict[str, Any] | None = None) -> None:  # noqa: D401
    """Enqueue a Celery task that triggers all URLs subscribed to *event*."""

    payload = payload or {}
    _send_webhook_task.delay(event, payload)


# ---------------------------------------------------------------------------
# Celery task – fan-out HTTP POSTs
# ---------------------------------------------------------------------------


@celery_app.task(name="webhook.send")
def _send_webhook_task(event: str, payload: dict[str, Any]):
    """Send *payload* via POST to every webhook registered for *event*."""

    with SessionLocal() as db:
        targets: Sequence[WebhookModel] = db.query(WebhookModel).filter_by(event=event).all()

    logger.info("Dispatching webhook event '%s' to %s targets", event, len(targets))

    for target in targets:
        try:
            resp = requests.post(target.url, json={"event": event, "data": payload}, timeout=10)
            resp.raise_for_status()
        except Exception as exc:  # pragma: no cover – best-effort
            logger.warning("Webhook POST to %s failed: %s", target.url, exc)
