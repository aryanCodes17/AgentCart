from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import ProductOut
from app.services.catalog import get_product, list_products, product_to_dict

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("")
def search_products(
    db: Session = Depends(get_db),
    category: str | None = None,
    q: str | None = None,
    min_price: float | None = Query(default=None, ge=0),
    max_price: float | None = Query(default=None, ge=0),
    brand: str | None = None,
    available: bool | None = None,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=24, ge=1, le=100),
) -> dict:
    rows, total = list_products(
        db,
        category=category,
        q=q,
        min_price=min_price,
        max_price=max_price,
        brand=brand,
        available=available,
        offset=offset,
        limit=limit,
    )
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [ProductOut.model_validate(product_to_dict(row)) for row in rows],
        "data_label": "Demo inventory",
    }


@router.get("/{product_id}", response_model=ProductOut)
def product_detail(product_id: str, db: Session = Depends(get_db)) -> ProductOut:
    product = get_product(db, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found.")
    return ProductOut.model_validate(product_to_dict(product))
