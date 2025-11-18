from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func, delete, update as sqlalchemy_update
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.product import Product as ProductModel
from ..schemas.product import (
    PaginatedProducts,
    Product,
    ProductCreate,
    ProductUpdate,
)
from ..core.database import get_async_db

router = APIRouter(prefix="/products", tags=["products"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_filters(stmt, sku: str | None, name: str | None, active: bool | None):
    if sku is not None:
        stmt = stmt.where(func.lower(ProductModel.sku) == sku.lower())
    if name is not None:
        stmt = stmt.where(ProductModel.name.ilike(f"%{name}%"))
    if active is not None:
        stmt = stmt.where(ProductModel.active.is_(active))
    return stmt


# ---------------------------------------------------------------------------
# GET /products – list with pagination & filters
# ---------------------------------------------------------------------------


@router.get("/", response_model=PaginatedProducts)
async def list_products(
    *,
    db: AsyncSession = Depends(get_async_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    sku: str | None = Query(None),
    name: str | None = Query(None),
    active: bool | None = Query(None),
):
    stmt = select(ProductModel)
    stmt = _apply_filters(stmt, sku, name, active)
    stmt = stmt.offset(offset).limit(limit)

    result = await db.execute(stmt)
    items = result.scalars().all()

    # total count
    count_stmt = select(func.count()).select_from(ProductModel)
    count_stmt = _apply_filters(count_stmt, sku, name, active)
    total = (await db.execute(count_stmt)).scalar_one()

    return PaginatedProducts(total=total, items=items)


# ---------------------------------------------------------------------------
# POST /products – create
# ---------------------------------------------------------------------------


@router.post("/", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(*, db: AsyncSession = Depends(get_async_db), product: ProductCreate):
    new_product = ProductModel(**product.dict(exclude_unset=True))
    db.add(new_product)
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001 (re-raise)
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await db.refresh(new_product)
    return new_product


# ---------------------------------------------------------------------------
# PUT /products/{product_id} – update
# ---------------------------------------------------------------------------


@router.put("/{product_id}", response_model=Product)
async def update_product(
    *,
    product_id: int,
    db: AsyncSession = Depends(get_async_db),
    product: ProductUpdate,
):
    stmt = (
        sqlalchemy_update(ProductModel)
        .where(ProductModel.id == product_id)
        .values(**product.dict(exclude_unset=True))
        .execution_options(synchronize_session="fetch")
    )
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    await db.commit()
    updated = await db.get(ProductModel, product_id)
    return updated


# ---------------------------------------------------------------------------
# DELETE /products/{product_id} – delete single
# ---------------------------------------------------------------------------


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(*, product_id: int, db: AsyncSession = Depends(get_async_db)):
    stmt = delete(ProductModel).where(ProductModel.id == product_id)
    result = await db.execute(stmt)
    if result.rowcount == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    await db.commit()
    return None


# ---------------------------------------------------------------------------
# DELETE /products/all – bulk delete (filtered)
# ---------------------------------------------------------------------------


@router.delete("/all", status_code=status.HTTP_204_NO_CONTENT)
async def bulk_delete_products(
    *,
    db: AsyncSession = Depends(get_async_db),
    sku: str | None = Query(None),
    name: str | None = Query(None),
    active: bool | None = Query(None),
):
    stmt = delete(ProductModel)
    stmt = _apply_filters(stmt, sku, name, active)
    await db.execute(stmt)
    await db.commit()
    return None
