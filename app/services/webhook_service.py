from sqlalchemy.orm import Session

from ..schemas.webhook import WebhookCreate


def create_webhook(db: Session, webhook: WebhookCreate):
    """Create a webhook record in the database."""
    # TODO: Implement webhook creation logic
    pass
