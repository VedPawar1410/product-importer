from typing import List

from fastapi import APIRouter, Depends

from ..schemas.product import Product, ProductCreate
from ..core.database import get_db

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=List[Product])
async def list_products(db=Depends(get_db)):
    """List all products."""
    # TODO: Retrieve products from the database
    return []


@router.post("/", response_model=Product)
async def create_product(product: ProductCreate, db=Depends(get_db)):
    """Create a new product."""
    # TODO: Insert product into the database
    return Product(id=1, **product.dict())
