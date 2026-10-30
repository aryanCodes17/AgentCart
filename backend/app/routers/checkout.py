
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx

from app.config import Settings, get_settings
from app.db import get_db
from app.deps import current_owner
from app.models import (
    Order,
    OrderItem,
    PaymentAttempt,
    Product,
    ShoppingSession,
    new_id,
)
from app.schemas import (
    CaptureOrderRequest,
    CreateOrderRequest,
    OrderOut,
    ProductOut,
)
from app.services.catalog import product_to_dict
from app.services.paypal import (
    PayPalClient,
    PayPalError,
    approval_url_from,
    capture_id_from,
    inr_to_paypal_amount,
)

router = APIRouter(prefix="/api/checkout", tags=["checkout"])


def _order_out(order: Order) -> OrderOut:
    order_items = [
        {
            "product": ProductOut.model_validate(product_to_dict(item.product)),
            "quantity": item.quantity,
            "unit_price_inr": float(item.unit_price_inr),
        }
        for item in order.items
    ]

    return OrderOut(
        id=order.id,
        product=ProductOut.model_validate(product_to_dict(order.product)),
        items=order_items,
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


@router.post("/create-order")
async def create_order(
    body: CreateOrderRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> dict:
    session = db.get(ShoppingSession, body.session_id)
    if session is None or session.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Support multi-item carts and legacy single-product requests.
    requested_items = (
        [(item.product_id, item.quantity) for item in body.items]
        if body.items
        else [(body.product_id, 1)]
    )

    products_and_quantities = []
    total_inr = 0.0

    # Validate products and calculate the total on the server.
    for product_id, quantity in requested_items:
        product = db.get(Product, product_id)

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=f"Product not found: {product_id}",
            )

        if not product.available:
            raise HTTPException(
                status_code=400,
                detail=f"Product is unavailable: {product.name}",
            )

        products_and_quantities.append((product, quantity))
        total_inr += float(product.price_inr) * quantity

    total_inr = round(total_inr, 2)
    paypal_amount = inr_to_paypal_amount(
        total_inr,
        settings.paypal_inr_per_usd,
    )

    # Preserve product_id for compatibility with existing orders/API.
    first_product = products_and_quantities[0][0]

    order = Order(
        session_id=session.id,
        demo_owner_id=owner,
        product_id=first_product.id,
        status="pending_approval",
        amount_inr=total_inr,
        currency="INR",
        paypal_amount=float(paypal_amount),
        paypal_currency=settings.paypal_currency,
        fx_rate_inr_per_usd=settings.paypal_inr_per_usd,
        idempotency_key=f"create-{new_id()}",
    )
    db.add(order)
    db.flush()

    # Save each cart line against the parent order.
    for product, quantity in products_and_quantities:
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=quantity,
                unit_price_inr=product.price_inr,
            )
        )

    attempt = PaymentAttempt(
        order_id=order.id,
        kind="create",
        status="started",
        idempotency_key=order.idempotency_key,
    )
    db.add(attempt)

    client = PayPalClient(settings)
    return_url = (
        f"{settings.public_frontend_url}/checkout/success"
        f"?order_id={order.id}"
    )
    cancel_url = (
        f"{settings.public_frontend_url}/checkout/success"
        f"?order_id={order.id}&cancelled=1"
    )

    try:
        paypal_order = await client.create_order(
            amount=paypal_amount,
            currency=settings.paypal_currency,
            description=f"AgentCart cart ({len(products_and_quantities)} lines)",
            custom_id=order.id,
            return_url=return_url,
            cancel_url=cancel_url,
            request_id=order.idempotency_key,
        )
    except HTTPException as exc:
        attempt.status = "failed"
        attempt.error_message = str(exc.detail)
        order.status = "capture_failed"
        db.commit()
        raise
    except PayPalError as exc:
        attempt.status = "failed"
        attempt.http_status = exc.status_code
        attempt.error_message = exc.message
        order.status = "capture_failed"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_error",
                "message": exc.message,
                "paypal": exc.payload,
            },
        ) from exc

    order.paypal_order_id = paypal_order.get("id")
    order.paypal_status = paypal_order.get("status")
    order.approval_url = approval_url_from(paypal_order)

    if not order.approval_url:
        attempt.status = "failed"
        attempt.error_message = "PayPal response did not include an approval URL."
        order.status = "capture_failed"
        db.commit()
        raise HTTPException(
            status_code=502,
            detail="PayPal did not return an approval link.",
        )

    attempt.status = "succeeded"
    attempt.paypal_order_id = order.paypal_order_id
    db.commit()
    db.refresh(order)

    return {
        "order": _order_out(order),
        "approval_url": order.approval_url,
        "sandbox": True,
        "pricing_note": (
            f"Cart total ₹{total_inr:,.2f} INR. Sandbox charge "
            f"{settings.paypal_currency} {paypal_amount:.2f} using documented "
            f"demo rate {settings.paypal_inr_per_usd} INR/USD. "
            "This is not a live FX quote."
        ),
    }


@router.post("/capture-order")
async def capture_order(
    body: CaptureOrderRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> dict:
    order = db.scalar(
        select(Order).where(Order.paypal_order_id == body.paypal_order_id)
    )

    if (
        order is None
        or order.demo_owner_id != owner
        or order.session_id != body.session_id
    ):
        raise HTTPException(
            status_code=404,
            detail="Order not found for this demo session.",
        )

    if order.status == "paid" and order.paypal_capture_id:
        return {
            "order": _order_out(order),
            "duplicate": True,
            "sandbox": True,
        }

    if order.status == "cancelled":
        raise HTTPException(status_code=409, detail="Order was cancelled.")

    # Reconcile an earlier capture whose outcome is still unknown.
    existing = db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.kind == "capture",
            PaymentAttempt.status == "started",
        )
    )

    if existing:
        client = PayPalClient(settings)

        try:
            order_details = await client.get_order(body.paypal_order_id)
            reconciled_capture_id = capture_id_from(order_details)

            if (
                order_details.get("status") == "COMPLETED"
                and reconciled_capture_id
            ):
                order.status = "paid"
                order.paypal_status = "COMPLETED"
                order.paypal_capture_id = reconciled_capture_id
                existing.status = "succeeded"
                existing.error_message = None
                db.commit()
                db.refresh(order)

                return {
                    "order": _order_out(order),
                    "duplicate": True,
                    "sandbox": True,
                    "paypal_status": "COMPLETED",
                }

            existing.error_message = (
                "Reconciliation did not confirm a completed capture. "
                "Another capture is blocked pending verification."
            )
            db.commit()

        except Exception:
            # Do not allow another capture when PayPal cannot be checked.
            db.rollback()

        raise HTTPException(
            status_code=409,
            detail={
                "code": "paypal_capture_reconciliation_required",
                "message": (
                    "The previous capture outcome is still unresolved. "
                    "No new capture was initiated. Verify the payment "
                    "status with PayPal before retrying."
                ),
            },
        )

    idempotency = f"capture-{new_id()}"
    capture_order_id = order.id

    attempt = PaymentAttempt(
        order_id=capture_order_id,
        kind="capture",
        status="started",
        paypal_order_id=order.paypal_order_id,
        idempotency_key=idempotency,
    )
    db.add(attempt)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()

        # Translate the error only if another unresolved capture exists.
        active_attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == capture_order_id,
                PaymentAttempt.kind == "capture",
                PaymentAttempt.status == "started",
            )
        )

        if active_attempt is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "paypal_capture_in_progress",
                    "message": (
                        "A capture attempt is already in progress or "
                        "awaiting reconciliation. No new capture was initiated."
                    ),
                },
            )

        # Preserve unrelated integrity errors.
        raise

    # This must remain outside the IntegrityError handler.
    client = PayPalClient(settings)

    try:
        payload = await client.capture_order(
            body.paypal_order_id,
            request_id=idempotency,
        )

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        # The capture may have reached PayPal despite the network failure.
        # Keep the attempt started so a retry must reconcile first.
        attempt.status = "started"
        attempt.error_message = (
            "Capture outcome unknown due to a network error. "
            "Reconcile with PayPal before retrying."
        )
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_capture_outcome_unknown",
                "message": (
                    "PayPal's capture outcome could not be confirmed. "
                    "Do not retry until the payment status has been reconciled."
                ),
            },
        ) from exc

    except HTTPException:
        attempt.status = "failed"
        order.status = "capture_failed"
        db.commit()
        raise

    except PayPalError as exc:
        details = exc.payload.get("details", {})
        issue = ""

        if isinstance(details, list) and details:
            issue = str(details[0].get("issue") or "")
        elif isinstance(details, dict):
            issue = str(details.get("issue") or details.get("name") or "")

        if issue == "ORDER_ALREADY_CAPTURED":
            try:
                order_details = await client.get_order(body.paypal_order_id)
                cap_id = capture_id_from(order_details)

                if order_details.get("status") == "COMPLETED" and cap_id:
                    order.status = "paid"
                    order.paypal_status = "COMPLETED"
                    order.paypal_capture_id = cap_id
                    attempt.status = "succeeded"
                    attempt.error_message = None
                    db.commit()
                    db.refresh(order)

                    return {
                        "order": _order_out(order),
                        "duplicate": True,
                        "sandbox": True,
                        "paypal_status": "COMPLETED",
                    }
            except Exception:
                # Fall through to the standard PayPal error response.
                pass

        attempt.status = "failed"
        attempt.error_message = exc.message
        order.status = "capture_failed"
        order.paypal_status = str(issue or "CAPTURE_FAILED")
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_capture_failed",
                "message": exc.message,
            },
        ) from exc

    status = payload.get("status")
    capture_id = capture_id_from(payload)
    order.paypal_status = status

    if status == "COMPLETED" and capture_id:
        order.status = "paid"
        order.paypal_capture_id = capture_id
        attempt.status = "succeeded"
        attempt.error_message = None
    elif status == "COMPLETED" and not capture_id:
        order.status = "capture_failed"
        attempt.status = "failed"
        attempt.error_message = (
            "Capture reported COMPLETED without a capture ID."
        )
    else:
        order.status = (
            "approved_not_captured"
            if status == "APPROVED"
            else "capture_failed"
        )
        attempt.status = "failed"
        attempt.error_message = f"Unexpected PayPal status: {status}"

    db.commit()
    db.refresh(order)

    return {
        "order": _order_out(order),
        "duplicate": False,
        "sandbox": True,
        "paypal_status": status,
    }


@router.post("/cancel")
def cancel_order(
    body: CaptureOrderRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> dict:
    order = db.scalar(
        select(Order).where(Order.paypal_order_id == body.paypal_order_id)
    )

    if (
        order is None
        or order.demo_owner_id != owner
        or order.session_id != body.session_id
    ):
        raise HTTPException(status_code=404, detail="Order not found.")

    if order.status == "paid":
        raise HTTPException(
            status_code=409,
            detail="Paid orders cannot be cancelled from this endpoint.",
        )

    capture_in_progress = db.scalar(
        select(PaymentAttempt.id)
        .where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.kind == "capture",
            PaymentAttempt.status == "started",
        )
        .limit(1)
    )

    if capture_in_progress:
        raise HTTPException(
            status_code=409,
            detail="Cannot cancel while payment capture is in progress.",
        )

    order.status = "cancelled"
    db.commit()
    db.refresh(order)

    return {"order": _order_out(order), "sandbox": True}
