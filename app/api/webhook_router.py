from typing import List

from fastapi import APIRouter, Depends

from ..schemas.webhook import Webhook, WebhookCreate
from ..core.database import get_db

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.get("/", response_model=List[Webhook])
async def list_webhooks(db=Depends(get_db)):
    """List all registered webhooks."""
    # TODO: Retrieve webhooks from the database
    return []


@router.post("/", response_model=Webhook)
async def create_webhook(webhook: WebhookCreate, db=Depends(get_db)):
    """Register a new webhook."""
    # TODO: Save webhook to the database
    return Webhook(id=1, **webhook.dict())
