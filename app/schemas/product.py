from pydantic import BaseModel
from datetime import datetime


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

    class Config:
        orm_mode = True


class PaginatedProducts(BaseModel):
    total: int
    items: list[Product]
