from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_owner
from app.models import Order
from app.schemas import OrderOut, ProductOut
from app.services.catalog import product_to_dict

router = APIRouter(prefix="/api/orders", tags=["orders"])


def serialize(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        product=ProductOut.model_validate(product_to_dict(order.product)),
        status=order.status,
        amount_inr=float(order.amount_inr),
        currency=order.currency,
        paypal_amount=float(order.paypal_amount),
        paypal_currency=order.paypal_currency,
        fx_rate_inr_per_usd=order.fx_rate_inr_per_usd,
        paypal_order_id=order.paypal_order_id,
        paypal_capture_id=order.paypal_capture_id,
        paypal_status=order.paypal_status,
        approval_url=order.approval_url,
        sandbox=True,
        created_at=order.created_at,
    )


@router.get("")
def list_orders(db: Session = Depends(get_db), owner: str = Depends(current_owner)) -> dict:
    rows = list(
        db.scalars(select(Order).where(Order.demo_owner_id == owner).order_by(Order.created_at.desc()))
    )
    return {"items": [serialize(row) for row in rows], "sandbox": True}


@router.get("/{order_id}")
def get_order(order_id: str, db: Session = Depends(get_db), owner: str = Depends(current_owner)) -> dict:
    order = db.get(Order, order_id)
    if order is None or order.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {"order": serialize(order), "sandbox": True}
