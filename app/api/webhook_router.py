"""FastAPI router: webhook CRUD, test sends and the delivery log."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status

from ..core.database import get_db
from ..schemas.webhook import Webhook as WebhookSchema
from ..schemas.webhook import WebhookCreate
from ..schemas.webhook import WebhookDelivery as WebhookDeliverySchema
from ..services import webhook_service


router = APIRouter(prefix="/webhooks", tags=["webhooks"])

TEST_PAYLOAD = {"test": True, "message": "Test delivery from Product Importer"}


def _get_or_404(db, webhook_id: int):
    webhook = webhook_service.get_webhook(db, webhook_id)
    if webhook is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    return webhook


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


# Collection routes use "" (path /webhooks, no trailing slash) to match the
# frontend. With "/" the path is /webhooks/, and a request for /webhooks is
# swallowed by the static-files mount at "/" (a 404) before FastAPI's
# trailing-slash redirect can run.
@router.get("", response_model=List[WebhookSchema])
def list_webhooks(db=Depends(get_db)):
    """Return all registered webhooks, each with its most recent delivery."""

    return webhook_service.list_webhooks(db)


@router.post(
    "",
    response_model=WebhookSchema,
    status_code=status.HTTP_201_CREATED,
)
def create_webhook(webhook_in: WebhookCreate, db=Depends(get_db)):
    """Create a new webhook registration."""

    return webhook_service.create_webhook(db, webhook_in)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(webhook_id: int, db=Depends(get_db)):
    """Delete a webhook and its delivery log (idempotent)."""

    webhook_service.delete_webhook(db, webhook_id)


# ---------------------------------------------------------------------------
# Test sends + delivery log
# ---------------------------------------------------------------------------


@router.post("/test/{event}", status_code=status.HTTP_202_ACCEPTED)
def test_event(event: str):
    """Queue a test event for every webhook subscribed to *event* (delivered in the background)."""

    webhook_service.dispatch_event(event, payload={"hello": "world"})
    return {"accepted": True}


@router.post("/{webhook_id}/test", response_model=WebhookDeliverySchema)
def test_webhook(webhook_id: int, db=Depends(get_db)):
    """Send one test event to this webhook now and return the recorded result.

    Synchronous on purpose: the person clicking "Test" wants the real status
    code and response time, not "queued". (No retries here.)
    """

    webhook = _get_or_404(db, webhook_id)
    return webhook_service.send_once(db, webhook, webhook.event, TEST_PAYLOAD)


@router.get("/{webhook_id}/deliveries", response_model=List[WebhookDeliverySchema])
def list_deliveries(webhook_id: int, limit: int = Query(20, ge=1, le=100), db=Depends(get_db)):
    """Most recent delivery attempts for one webhook, newest first."""

    _get_or_404(db, webhook_id)
    return webhook_service.list_deliveries(db, webhook_id, limit)
