from pydantic import BaseModel


class WebhookBase(BaseModel):
    event: str
    url: str


class WebhookCreate(WebhookBase):
    pass


class Webhook(WebhookBase):
    id: int

    model_config = {"from_attributes": True}
