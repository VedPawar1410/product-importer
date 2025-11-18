from sqlalchemy import Column, Integer, String

from ..core.database import Base


class Webhook(Base):
    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String(512), nullable=False, unique=True)
