from sqlalchemy.orm import Session

from ..schemas.product import ProductCreate


def create_product(db: Session, product: ProductCreate):
    """Create a product record in the database."""
    # TODO: Implement product creation logic
    pass
