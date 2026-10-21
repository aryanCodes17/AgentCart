from sqlalchemy import select
from sqlalchemy.orm import Session

from app.catalog_data import PRODUCTS
from app.models import Product


def seed_products(db: Session) -> int:
    existing = set(db.scalars(select(Product.id)))
    added = 0
    for item in PRODUCTS:
        if item["id"] in existing:
            continue
        db.add(Product(**item))
        added += 1
    db.commit()
    return added
