
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
import httpx
from datetime import datetime, timezone, timedelta
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

    requested_items = (
        [(item.product_id, item.quantity) for item in body.items]
        if body.items
        else [(body.product_id, 1)]
    )

    products_and_quantities = []
    total_inr = 0.0

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

    first_product = products_and_quantities[0][0]

    # Look up a previous attempt using the client-supplied key.
    order = db.scalar(
        select(Order).where(
            Order.idempotency_key == body.idempotency_key
        )
    )

    if order is not None:
        # Never allow a key to be reused for another user's order,
        # session, or cart.
        existing_items = {
            item.product_id: item.quantity for item in order.items
        }
        requested_map = dict(requested_items)

        if (
            order.demo_owner_id != owner
            or order.session_id != body.session_id
            or existing_items != requested_map
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "idempotency_key_conflict",
                    "message": (
                        "This idempotency key belongs to a different "
                        "checkout request. Start a new checkout."
                    ),
                },
            )

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == order.id,
                PaymentAttempt.kind == "create",
            )
        )

        if attempt is None:
            raise HTTPException(
                status_code=409,
                detail="The previous checkout attempt requires investigation.",
            )

        # A completed creation can safely return the original approval URL.
        if order.status == "checkout_unavailable":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "checkout_unavailable",
                    "message": (
                        "This PayPal checkout is no longer available. "
                        "Start a new checkout with a new idempotency key."
                    ),
                },
            )
        if order.status == "checkout_unavailable":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "checkout_unavailable",
                    "message": (
                        "This PayPal checkout is no longer available. "
                        "Start a new checkout with a new idempotency key."
                    ),
                },
            )
        if (
            attempt.status == "succeeded"
            and order.paypal_order_id
            and order.approval_url
        ):
            return {
                "order": _order_out(order),
                "approval_url": order.approval_url,
                "sandbox": True,
                "duplicate": True,
                "pricing_note": "Reused existing PayPal checkout.",
            }

        if attempt.status == "failed":
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "previous_checkout_failed",
                    "message": (
                        "The previous checkout failed. Start a new "
                        "checkout with a new idempotency key."
                    ),
                },
            )

        # PayPal Orders v2 idempotency retention is six hours by default.
        created_at = attempt.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) - created_at > timedelta(hours=6):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "checkout_reconciliation_required",
                    "message": (
                        "The previous PayPal creation attempt is too old "
                        "to retry safely. Verify its outcome before "
                        "starting another checkout."
                    ),
                },
            )

    else:
        # Create and persist the local order BEFORE contacting PayPal.
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
            idempotency_key=body.idempotency_key,
        )
        db.add(order)
        db.flush()

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
            idempotency_key=body.idempotency_key,
        )
        db.add(attempt)

        try:
            db.commit()
            db.refresh(order)
        except IntegrityError:
            db.rollback()

            # Another concurrent request may have created this key first.
            order = db.scalar(
                select(Order).where(
                    Order.idempotency_key == body.idempotency_key
                )
            )
            if order is None:
                raise

            raise HTTPException(
                status_code=409,
                detail={
                    "code": "checkout_already_started",
                    "message": (
                        "This checkout is already being processed. "
                        "Retry using the same idempotency key."
                    ),
                },
            )

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
            amount=order.paypal_amount,
            currency=order.paypal_currency,
            description=f"AgentCart cart ({len(requested_items)} lines)",
            custom_id=order.id,
            return_url=return_url,
            cancel_url=cancel_url,
            request_id=order.idempotency_key,
        )

    except (httpx.TimeoutException, httpx.NetworkError) as exc:
        # PayPal may have created the order despite the network failure.
        # Keep the attempt started and retry only with the same request ID.
        attempt.status = "started"
        attempt.error_message = (
            "PayPal creation outcome unknown due to a network error."
        )
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_create_outcome_unknown",
                "message": (
                    "PayPal's order creation outcome could not be confirmed. "
                    "Retry this checkout using the same idempotency key."
                ),
            },
        ) from exc

    except HTTPException as exc:
        attempt.status = "failed"
        attempt.error_message = str(exc.detail)
        order.status = "capture_failed"
        db.commit()
        raise


    except PayPalError as exc:
        attempt.http_status = exc.status_code
        attempt.error_message = exc.message

        # Retryable or ambiguous errors must preserve the started attempt.
        if exc.status_code in (408, 429) or exc.status_code >= 500:
            attempt.status = "started"
            order.status = "pending"
            db.commit()

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_create_outcome_unknown",
                    "message": (
                        "PayPal returned a retryable or ambiguous error. "
                        "Retry using the same idempotency key."
                    ),
                    "paypal_http_status": exc.status_code,
                },
            ) from exc

        # Definite client-side rejection.
        attempt.status = "failed"
        order.status = "capture_failed"
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_error",
                "message": exc.message,
                "paypal_http_status": exc.status_code,
                "paypal": exc.payload,
            },
        ) from exc
    # Save any returned PayPal ID even if the response is incomplete.
    order.paypal_order_id = paypal_order.get("id")
    order.paypal_status = paypal_order.get("status")
    order.approval_url = approval_url_from(paypal_order)

    if not order.paypal_order_id or not order.approval_url:
        # Do not mark this failed: PayPal may already have created an order.
        attempt.status = "started"
        attempt.error_message = (
            "PayPal returned an incomplete creation response."
        )
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_create_response_incomplete",
                "message": (
                    "PayPal returned an incomplete response. "
                    "Retry with the same idempotency key."
                ),
            },
        )

    attempt.status = "succeeded"
    attempt.paypal_order_id = order.paypal_order_id
    attempt.error_message = None

    db.commit()
    db.refresh(order)

    return {
        "order": _order_out(order),
        "approval_url": order.approval_url,
        "sandbox": True,
        "duplicate": False,
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
        attempt.http_status = exc.status_code
        attempt.error_message = exc.message

        details = (exc.payload or {}).get("details", {})
        issue = ""

        if isinstance(details, list) and details:
            if isinstance(details[0], dict):
                issue = str(details[0].get("issue") or "")
        elif isinstance(details, dict):
            issue = str(details.get("issue") or details.get("name") or "")

        # PayPal says the order may already have been captured.
        # Verify its actual status before marking the order paid.
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

            except Exception as reconcile_exc:
                attempt.error_message = (
                    "PayPal reported ORDER_ALREADY_CAPTURED, "
                    f"but reconciliation failed: {str(reconcile_exc)}"
                )

            # Never mark the attempt failed when payment status is uncertain.
            attempt.status = "started"
            order.paypal_status = "RECONCILIATION_REQUIRED"
            db.commit()

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_capture_reconciliation_required",
                    "message": (
                        "PayPal indicates this order may already be captured, "
                        "but its final payment status could not be verified. "
                        "Do not start another capture."
                    ),
                },
            ) from exc

        # Ambiguous errors: preserve the started attempt.
        if exc.status_code in (408, 429) or exc.status_code >= 500:
            attempt.status = "started"
            db.commit()

            raise HTTPException(
                status_code=502,
                detail={
                    "code": "paypal_capture_outcome_unknown",
                    "message": (
                        "PayPal returned an ambiguous capture error. "
                        "The payment may have completed. "
                        "Reconcile the payment before retrying."
                    ),
                    "paypal_http_status": exc.status_code,
                },
            ) from exc

        # Definite client-side rejection.
        attempt.status = "failed"
        order.status = "capture_failed"
        order.paypal_status = str(issue or "CAPTURE_FAILED")
        db.commit()

        raise HTTPException(
            status_code=502,
            detail={
                "code": "paypal_capture_failed",
                "message": exc.message,
                "paypal_http_status": exc.status_code,
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
