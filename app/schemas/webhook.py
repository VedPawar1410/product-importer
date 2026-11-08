from datetime import datetime

from pydantic import BaseModel


class WebhookBase(BaseModel):
    event: str
    url: str


class WebhookCreate(WebhookBase):
    pass


class WebhookDelivery(BaseModel):
    """One recorded delivery attempt."""

    id: int
    webhook_id: int
    event: str
    success: bool
    status_code: int | None = None
    response_ms: float | None = None
    error: str | None = None
    attempt: int
    created_at: datetime

    model_config = {"from_attributes": True}


class Webhook(WebhookBase):
    id: int
    created_at: datetime | None = None
    last_delivery: WebhookDelivery | None = None

    model_config = {"from_attributes": True}
