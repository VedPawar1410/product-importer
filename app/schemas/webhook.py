from pydantic import BaseModel


class WebhookBase(BaseModel):
    url: str


class WebhookCreate(WebhookBase):
    pass


class Webhook(WebhookBase):
    id: int

    class Config:
        orm_mode = True
