from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, Index, func
from ..core.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    sku = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # SKUs are unique ignoring case ("ABC-1" and "abc-1" are the same product).
    # A functional index on lower(sku) makes Postgres enforce that, and it is also
    # the conflict target for the CSV upsert and the index used by the SKU filter.
    __table_args__ = (Index("ix_products_sku_lower", func.lower(sku), unique=True),)
