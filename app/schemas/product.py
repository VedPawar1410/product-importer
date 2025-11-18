from datetime import datetime
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    sku: str
    description: str | None = None


class ProductBase(BaseModel):
    sku: str | None = None
    name: str | None = None
    description: str | None = None
    price: float | None = None
    active: bool | None = True


class ProductCreate(ProductBase):
    sku: str
    name: str
    active: bool | None = True


class ProductUpdate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PaginatedProducts(BaseModel):
    total: int
    items: list[Product]
