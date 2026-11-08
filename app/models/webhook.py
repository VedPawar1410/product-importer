from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, func

from ..core.database import Base


class Webhook(Base):
    """Outgoing *HTTP* webhook registration.

    Each row represents a consumer-provided URL that should receive a POST
    request whenever the :pyattr:`event` occurs in the system.
    """

    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)

    # Domain-specific event identifier (e.g. "import.completed").  Keeping it a
    # free-form string keeps the implementation simple for now.
    event = Column(String(128), nullable=False, index=True)

    # Target URL that will receive a JSON payload via HTTP POST.
    url = Column(String(512), nullable=False)

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:  # pragma: no cover – utility only
        return f"<Webhook id={self.id} event={self.event} url={self.url}>"


class WebhookDelivery(Base):
    """One attempt to deliver an event to a webhook: the delivery log.

    Retries create new rows (attempt 2, 3), so the history shows every try.
    Rows are removed with their webhook (ON DELETE CASCADE).
    """

    __tablename__ = "webhook_deliveries"

    id = Column(Integer, primary_key=True)
    webhook_id = Column(Integer, ForeignKey("webhooks.id", ondelete="CASCADE"), nullable=False)
    event = Column(String(128), nullable=False)
    success = Column(Boolean, nullable=False)
    status_code = Column(Integer, nullable=True)  # None when no response (timeout, refused...)
    response_ms = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    attempt = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Serves both "latest delivery per webhook" and "history for one webhook".
    __table_args__ = (Index("ix_webhook_deliveries_webhook_created", webhook_id, created_at.desc()),)
