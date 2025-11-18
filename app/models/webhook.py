from sqlalchemy import Column, Integer, String, func, DateTime

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
