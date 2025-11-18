from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from ..models.product import Product
from ..schemas.product import ProductCreate


def upsert_products(db: Session, products: list[ProductCreate]) -> None:
    """
    Insert or update products in a single batch.
    Matching is case-insensitive on SKU.

    - New SKUs → INSERT
    - Existing SKUs → UPDATE name + description + price + active
    """

    if not products:
        return

    # Extract all SKUs in lowercase for case-insensitive match.
    incoming_skus_lower = [p.sku.lower() for p in products]

    # Fetch existing products that match these SKUs
    stmt = select(Product).where(
        func.lower(Product.sku).in_(incoming_skus_lower)
    )
    existing = {p.sku.lower(): p for p in db.execute(stmt).scalars().all()}

    for item in products:
        key = item.sku.lower()

        if key in existing:
            # Update existing
            db_product = existing[key]
            db_product.name = item.name
            db_product.description = item.description
            if hasattr(item, 'price') and item.price is not None:
                db_product.price = item.price
            if hasattr(item, 'active') and item.active is not None:
                db_product.active = item.active

        else:
            # Insert new
            db_product = Product(
                name=item.name,
                sku=item.sku,
                description=item.description,
                price=getattr(item, 'price', None),
                active=getattr(item, 'active', True),
            )
            db.add(db_product)

    # Commit happens upstream in csv_importer._flush_batch()
