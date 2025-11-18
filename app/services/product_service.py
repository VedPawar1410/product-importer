from __future__ import annotations

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from ..models.product import Product
from ..schemas.product import ProductCreate


def upsert_products(db: Session, products: list[ProductCreate]) -> None:
    """
    Insert or update products in a single batch using PostgreSQL's native UPSERT.
    Matching is case-insensitive on SKU.

    - New SKUs → INSERT
    - Existing SKUs → UPDATE name + description + price + active
    
    Uses PostgreSQL's INSERT ... ON CONFLICT DO UPDATE for efficiency.
    Handles duplicates within the batch by taking the last occurrence.
    """

    if not products:
        return

    # Deduplicate products within the batch (keep last occurrence of each SKU)
    products_dict = {}
    for item in products:
        products_dict[item.sku.lower()] = item
    
    # Prepare bulk insert data
    values_to_insert = []
    for item in products_dict.values():
        values_to_insert.append({
            'sku': item.sku,
            'name': item.name,
            'description': item.description,
            'price': getattr(item, 'price', None),
            'active': getattr(item, 'active', True),
        })
    
    if not values_to_insert:
        return
    
    # Use PostgreSQL's INSERT ... ON CONFLICT DO UPDATE (UPSERT)
    stmt = insert(Product).values(values_to_insert)
    
    # On conflict (duplicate SKU), update the existing row
    stmt = stmt.on_conflict_do_update(
        index_elements=['sku'],  # The unique constraint column
        set_={
            'name': stmt.excluded.name,
            'description': stmt.excluded.description,
            'price': stmt.excluded.price,
            'active': stmt.excluded.active,
            'updated_at': func.now(),  # Update timestamp
        }
    )
    
    db.execute(stmt)
    
    # Commit happens upstream in csv_importer._flush_batch()
