from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Float, func

from ..core.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    sku = Column(String(64), nullable=False, unique=True, index=True)
    price = Column(Float, nullable=True)
    active = Column(Boolean, nullable=False, server_default="true", default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
