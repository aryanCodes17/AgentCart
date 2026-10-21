from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product
from app.services.ranking import normalize_category


def product_to_dict(product: Product) -> dict[str, Any]:
    return {
        "id": product.id,
        "slug": product.slug,
        "name": product.name,
        "brand": product.brand,
        "category": product.category,
        "price_inr": float(product.price_inr),
        "currency": product.currency,
        "image_url": product.image_url,
        "short_description": product.short_description,
        "description": product.description,
        "specs": product.specs or {},
        "available": product.available,
        "data_source": product.data_source,
        "data_label": product.data_label,
        "detail_url": product.detail_url,
    }


def list_products(
    db: Session,
    *,
    category: str | None = None,
    q: str | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
    brand: str | None = None,
    available: bool | None = None,
    offset: int = 0,
    limit: int = 24,
) -> tuple[list[Product], int]:
    stmt = select(Product)
    count_base = select(Product)
    if category:
        normalized = normalize_category(category)
        stmt = stmt.where(Product.category == normalized)
        count_base = count_base.where(Product.category == normalized)
    if brand:
        stmt = stmt.where(Product.brand.ilike(brand))
        count_base = count_base.where(Product.brand.ilike(brand))
    if available is not None:
        stmt = stmt.where(Product.available.is_(available))
        count_base = count_base.where(Product.available.is_(available))
    if min_price is not None:
        stmt = stmt.where(Product.price_inr >= min_price)
        count_base = count_base.where(Product.price_inr >= min_price)
    if max_price is not None:
        stmt = stmt.where(Product.price_inr <= max_price)
        count_base = count_base.where(Product.price_inr <= max_price)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(Product.name.ilike(like) | Product.brand.ilike(like) | Product.short_description.ilike(like))
        count_base = count_base.where(
            Product.name.ilike(like) | Product.brand.ilike(like) | Product.short_description.ilike(like)
        )
    total = len(list(db.scalars(count_base)))
    rows = list(db.scalars(stmt.order_by(Product.price_inr.asc()).offset(offset).limit(limit)))
    return rows, total


def get_product(db: Session, product_id: str) -> Product | None:
    return db.get(Product, product_id)


def all_product_dicts(db: Session, category: str | None = None) -> list[dict[str, Any]]:
    stmt = select(Product)
    if category:
        stmt = stmt.where(Product.category == normalize_category(category))
    return [product_to_dict(row) for row in db.scalars(stmt)]
