from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_owner
from app.models import Order
from app.schemas import OrderOut, ProductOut
from app.services.catalog import product_to_dict
import httpx

from app.config import Settings, get_settings
from app.models import Order, PaymentAttempt
from app.services.paypal import PayPalClient, PayPalError, capture_id_from

router = APIRouter(prefix="/api/orders", tags=["orders"])



def serialize(order: Order) -> OrderOut:
    return OrderOut(
        id=order.id,
        product=ProductOut.model_validate(product_to_dict(order.product)),
        items=[
            {
                "product": ProductOut.model_validate(
                    product_to_dict(item.product)
                ),
                "quantity": item.quantity,
                "unit_price_inr": float(item.unit_price_inr),
            }
            for item in order.items
        ],
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

@router.post("/{order_id}/reconcile")
async def reconcile_order(
    order_id: str,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> dict:
    order = db.get(Order, order_id)

    if order is None or order.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Order not found.")

    # Already confirmed paid: no PayPal request is necessary.
    if order.status == "paid" and order.paypal_capture_id:
        return {
            "order": serialize(order),
            "reconciliation": "already_paid",
            "sandbox": True,
        }

        # Also verify a pending checkout whose PayPal creation succeeded.
    if order.status == "pending_approval":
        create_attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == order.id,
                PaymentAttempt.kind == "create",
                PaymentAttempt.status == "succeeded",
            )
        )

        if create_attempt is None or not order.paypal_order_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "checkout_creation_not_confirmed",
                    "message": "The original PayPal checkout cannot be verified.",
                },
            )

        client = PayPalClient(settings)

        try:
            details = await client.get_order(order.paypal_order_id)

        except PayPalError as exc:
            if exc.status_code == 404:
                order.status = "checkout_unavailable"
                order.paypal_status = "RESOURCE_NOT_FOUND"
                order.approval_url = None
                db.commit()
                db.refresh(order)

                return {
                    "order": serialize(order),
                    "reconciliation": "checkout_unavailable",
                    "paypal_status": "RESOURCE_NOT_FOUND",
                    "message": (
                        "PayPal no longer recognizes this checkout. "
                        "The original order has been preserved. "
                        "Start a new checkout to try again."
                    ),
                    "sandbox": True,
                }

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_reconciliation_failed",
                    "message": exc.message,
                    "paypal_http_status": exc.status_code,
                },
            ) from exc

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_reconciliation_unavailable",
                    "message": "PayPal could not be reached. Try again later.",
                },
            ) from exc

        paypal_status = details.get("status")
        capture_id = capture_id_from(details)

        if paypal_status == "COMPLETED" and capture_id:
            order.status = "paid"
            order.paypal_status = "COMPLETED"
            order.paypal_capture_id = capture_id
            db.commit()
            db.refresh(order)

            return {
                "order": serialize(order),
                "reconciliation": "paid",
                "sandbox": True,
            }

        if paypal_status == "APPROVED":
            order.status = "approved_not_captured"

        order.paypal_status = str(paypal_status or "UNKNOWN")
        db.commit()
        db.refresh(order)

        return {
            "order": serialize(order),
            "reconciliation": "unresolved",
            "paypal_status": paypal_status,
            "message": (
                "PayPal has not confirmed a completed payment. "
                "No capture was initiated."
            ),
            "sandbox": True,
        }

    # Verify a pending checkout whose PayPal creation succeeded.
    if order.status == "pending_approval":
        create_attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == order.id,
                PaymentAttempt.kind == "create",
                PaymentAttempt.status == "succeeded",
            )
        )

        if create_attempt is None or not order.paypal_order_id:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "checkout_creation_not_confirmed",
                    "message": "The original PayPal checkout cannot be verified.",
                },
            )

        client = PayPalClient(settings)

        try:
            details = await client.get_order(order.paypal_order_id)

        except PayPalError as exc:
            if exc.status_code == 404:
                order.status = "checkout_unavailable"
                order.paypal_status = "RESOURCE_NOT_FOUND"
                order.approval_url = None
                db.commit()
                db.refresh(order)

                return {
                    "order": serialize(order),
                    "reconciliation": "checkout_unavailable",
                    "paypal_status": "RESOURCE_NOT_FOUND",
                    "message": (
                        "PayPal no longer recognizes this checkout. "
                        "The original order has been preserved. "
                        "Start a new checkout to try again."
                    ),
                    "sandbox": True,
                }

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_reconciliation_failed",
                    "message": exc.message,
                    "paypal_http_status": exc.status_code,
                },
            ) from exc

        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_reconciliation_unavailable",
                    "message": "PayPal could not be reached. Try again later.",
                },
            ) from exc

        paypal_status = details.get("status")
        capture_id = capture_id_from(details)

        if paypal_status == "COMPLETED" and capture_id:
            order.status = "paid"
            order.paypal_status = "COMPLETED"
            order.paypal_capture_id = capture_id
            db.commit()
            db.refresh(order)

            return {
                "order": serialize(order),
                "reconciliation": "paid",
                "sandbox": True,
            }

        order.paypal_status = str(paypal_status or "UNKNOWN")
        db.commit()
        db.refresh(order)

        return {
            "order": serialize(order),
            "reconciliation": "unresolved",
            "paypal_status": paypal_status,
            "message": (
                "PayPal has not confirmed a completed payment. "
                "No capture was initiated."
            ),
            "sandbox": True,
        }

    # Only reconcile an unresolved capture attempt.
    attempt = db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.kind == "capture",
            PaymentAttempt.status == "started",
        )
    )

    if attempt is None:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "no_unresolved_capture",
                "message": "This order has no unresolved capture attempt.",
            },
        )

    if not order.paypal_order_id:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "paypal_order_id_missing",
                "message": "Cannot reconcile without a PayPal order ID.",
            },
        )

    client = PayPalClient(settings)

    try:
        details = await client.get_order(order.paypal_order_id)

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_reconciliation_unavailable",
                "message": "PayPal could not be reached. The capture remains unresolved.",
            },
        ) from exc

    except PayPalError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_reconciliation_failed",
                "message": exc.message,
                "paypal_http_status": exc.status_code,
            },
        ) from exc

    paypal_status = details.get("status")
    capture_id = capture_id_from(details)

    # Only a confirmed completed capture can mark an order paid.
    if paypal_status == "COMPLETED" and capture_id:
        order.status = "paid"
        order.paypal_status = "COMPLETED"
        order.paypal_capture_id = capture_id
        attempt.status = "succeeded"
        attempt.error_message = None

        db.commit()
        db.refresh(order)

        return {
            "order": serialize(order),
            "reconciliation": "paid",
            "sandbox": True,
        }

    # Never start another capture from this endpoint.
    # Keep the attempt unresolved until its outcome is confirmed.
    order.paypal_status = str(paypal_status or "UNKNOWN")
    attempt.error_message = (
        f"Reconciliation checked PayPal. "
        f"Current PayPal status: {paypal_status or 'UNKNOWN'}. "
        "Capture remains unresolved."
    )

    db.commit()
    db.refresh(order)

    return {
        "order": serialize(order),
        "reconciliation": "unresolved",
        "paypal_status": paypal_status,
        "message": (
            "PayPal has not confirmed a completed capture. "
            "No new capture was initiated."
        ),
        "sandbox": True,
    }