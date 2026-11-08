from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ProductBase(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    sku: str | None = None
    name: str | None = None
    description: str | None = None
    price: float | None = None
    active: bool | None = True


class ProductCreate(ProductBase):
    sku: str = Field(min_length=1)
    name: str = Field(min_length=1)
    active: bool | None = True


class ProductUpdate(ProductBase):
    pass


class Product(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedProducts(BaseModel):
    total: int
    items: list[Product]
