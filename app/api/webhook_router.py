"""FastAPI router exposing *webhook* CRUD + test endpoint."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from ..core.database import get_db
from ..schemas.webhook import Webhook as WebhookSchema, WebhookCreate
from ..services import webhook_service


router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[WebhookSchema])
async def list_webhooks(db=Depends(get_db)):
    """Return all registered webhooks."""

    return webhook_service.list_webhooks(db)


@router.post(
    "/",
    response_model=WebhookSchema,
    status_code=status.HTTP_201_CREATED,
)
async def create_webhook(webhook_in: WebhookCreate, db=Depends(get_db)):
    """Create a new webhook registration."""

    return webhook_service.create_webhook(db, webhook_in)


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(webhook_id: int, db=Depends(get_db)):
    """Delete a webhook (idempotent)."""

    webhook_service.delete_webhook(db, webhook_id)


# ---------------------------------------------------------------------------
# POST /webhooks/test – trigger event manually
# ---------------------------------------------------------------------------


@router.post("/test/{event}", status_code=status.HTTP_202_ACCEPTED)
async def test_event(event: str):
    """Enqueue a test dispatch for *event* with a dummy payload."""

    webhook_service.dispatch_event(event, payload={"hello": "world"})
    return {"accepted": True}
