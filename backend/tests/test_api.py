import pytest
from fastapi.testclient import TestClient
import uuid
from app.config import get_settings
from app.main import app
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Order, PaymentAttempt

@pytest.fixture()
def client():
    with TestClient(app) as test_client:
        yield test_client


HEADERS = {"X-Demo-Session": "demo-owner-test-1"}


def test_health(client: TestClient):
    response = client.get("/api/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["demo"] is True
    if not get_settings().ai_configured:
        assert body["ai"]["mode"] == "rule_based"


def test_public_settings(client: TestClient):
    response = client.get("/api/settings/public")
    assert response.status_code == 200
    body = response.json()
    assert body["demo"] is True
    assert body["catalog_currency"] == "INR"
    assert body["paypal_currency"] == "USD"
    assert body["paypal_inr_per_usd"] == 95.0
    assert "paypal_client_secret" not in body
    assert "gemini_api_key" not in body


def test_products_list_and_detail(client: TestClient):
    listing = client.get("/api/products", headers=HEADERS)
    assert listing.status_code == 200
    items = listing.json()["items"]
    assert listing.json()["total"] >= 30
    detail = client.get(f"/api/products/{items[0]['id']}")
    assert detail.status_code == 200
    missing = client.get("/api/products/does-not-exist")
    assert missing.status_code == 404


def test_agent_search_enforces_constraints(client: TestClient):
    response = client.post(
        "/api/agent/search",
        headers=HEADERS,
        json={"message": "Find a laptop for coding under ₹70,000 with at least 16 GB RAM"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] in ("ai", "rule_based")
    assert body["session_id"]
    assert body["evaluated_count"] >= 1
    for item in body["eligible"]:
        assert item["product"]["price_inr"] <= 70000
        assert item["product"]["specs"]["ram_gb"] >= 16
        assert item["product"]["category"] == "laptop"
        assert item["product"]["available"] is True
    assert any(not row["eligible"] for row in body["excluded"])


def test_checkout_rejects_missing_paypal_config(client: TestClient):
    search = client.post(
        "/api/agent/search",
        headers=HEADERS,
        json={"message": "laptop under 70000 with 16 GB RAM"},
    )
    assert search.status_code == 200
    session_id = search.json()["session_id"]
    product_id = search.json()["eligible"][0]["product"]["id"]
    response = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json={
            "product_id": product_id,
            "session_id": session_id,
            "idempotency_key": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "paypal_not_configured"


def test_session_isolation(client: TestClient):
    created = client.post("/api/sessions", headers=HEADERS)
    assert created.status_code == 200
    session_id = created.json()["id"]
    other = client.get(f"/api/sessions/{session_id}", headers={"X-Demo-Session": "someone-else-999"})
    assert other.status_code == 404


def test_checkout_capture_requires_matching_owner_and_session(client: TestClient):
    response = client.post(
        "/api/checkout/capture-order",
        headers=HEADERS,
        json={"paypal_order_id": "nonexistent-pp-id", "session_id": "dummy-session"},
    )
    assert response.status_code == 404


def test_checkout_cancel_requires_matching_owner_and_session(client: TestClient):
    response = client.post(
        "/api/checkout/cancel",
        headers=HEADERS,
        json={"paypal_order_id": "nonexistent-pp-id", "session_id": "dummy-session"},
    )
    assert response.status_code == 404

def test_checkout_cancel_rejected_while_capture_is_in_progress(client: TestClient):
    # Create a valid session and product using the existing API.
    test_suffix = uuid.uuid4().hex
    paypal_order_id = f"TEST-CAPTURE-{test_suffix}"
    create_key = f"test-create-{test_suffix}"
    capture_key = f"test-capture-{test_suffix}"
    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    # Insert a representative order and an active capture attempt.
    with SessionLocal() as db:
        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending_approval",
            amount_inr=1000,
            currency="INR",
            paypal_amount=10.53,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            paypal_order_id=paypal_order_id,
            idempotency_key=create_key,
        )
        db.add(order)
        db.flush()

        db.add(
            PaymentAttempt(
                order_id=order.id,
                kind="capture",
                status="started",
                paypal_order_id=order.paypal_order_id,
                idempotency_key=capture_key,
            )
        )
        db.commit()

    # Cancellation must not win against an active capture.
    response = client.post(
        "/api/checkout/cancel",
        headers=HEADERS,
        json={
            "paypal_order_id": paypal_order_id,
            "session_id": session_id,
        },
    )

    assert response.status_code == 409

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(
                Order.paypal_order_id == paypal_order_id
            )
        )
        assert saved_order is not None
        assert saved_order.status != "cancelled"



def test_checkout_capture_timeout_keeps_attempt_for_reconciliation(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.routers import checkout as checkout_router
    import httpx

    test_suffix = uuid.uuid4().hex
    paypal_order_id = f"TEST-TIMEOUT-{test_suffix}"
    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    with SessionLocal() as db:
        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending_approval",
            amount_inr=1000,
            currency="INR",
            paypal_amount=10.53,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            paypal_order_id=paypal_order_id,
            idempotency_key=f"test-create-{test_suffix}",
        )
        db.add(order)
        db.commit()

    class TimeoutPayPalClient:
        def __init__(self, settings):
            pass

        async def capture_order(self, paypal_order_id, request_id):
            raise httpx.ReadTimeout("Simulated PayPal timeout")

    monkeypatch.setattr(checkout_router, "PayPalClient", TimeoutPayPalClient)

    response = client.post(
        "/api/checkout/capture-order",
        headers=HEADERS,
        json={"paypal_order_id": paypal_order_id, "session_id": session_id},
    )

    assert response.status_code == 502

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(Order.paypal_order_id == paypal_order_id)
        )
        assert saved_order is not None
        assert saved_order.status != "paid"

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "capture",
            )
        )
        assert attempt is not None
        assert attempt.status == "started"



def test_checkout_recovers_when_paypal_says_order_already_captured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    from app.routers import checkout as checkout_router
    from app.services.paypal import PayPalError

    test_suffix = uuid.uuid4().hex
    paypal_order_id = f"TEST-ALREADY-CAPTURED-{test_suffix}"

    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    with SessionLocal() as db:
        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending_approval",
            amount_inr=1000,
            currency="INR",
            paypal_amount=10.53,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            paypal_order_id=paypal_order_id,
            idempotency_key=f"test-create-{test_suffix}",
        )
        db.add(order)
        db.commit()

    class AlreadyCapturedPayPalClient:
        def __init__(self, settings):
            pass

        async def capture_order(self, paypal_order_id, request_id):
            raise PayPalError(
                "PayPal reports this order was already captured.",
                payload={
                    "details": [
                        {"issue": "ORDER_ALREADY_CAPTURED"}
                    ]
                },
            )

        async def get_order(self, paypal_order_id):
            assert paypal_order_id == f"TEST-ALREADY-CAPTURED-{test_suffix}"
            return {
                "id": paypal_order_id,
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [
                                {"id": f"CAPTURE-{test_suffix}", "status": "COMPLETED"}
                            ]
                        }
                    }
                ],
            }

    monkeypatch.setattr(
        checkout_router, "PayPalClient", AlreadyCapturedPayPalClient
    )

    response = client.post(
        "/api/checkout/capture-order",
        headers=HEADERS,
        json={
            "paypal_order_id": paypal_order_id,
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is True
    assert body["order"]["status"] == "paid"
    assert body["order"]["paypal_capture_id"] == f"CAPTURE-{test_suffix}"
    assert body["paypal_status"] == "COMPLETED"

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(Order.paypal_order_id == paypal_order_id)
        )
        assert saved_order is not None
        assert saved_order.status == "paid"
        assert saved_order.paypal_capture_id == f"CAPTURE-{test_suffix}"

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "capture",
            )
        )
        assert attempt is not None
        assert attempt.status == "succeeded"


def test_checkout_reconciles_existing_capture_attempt(client, monkeypatch):
    from app.routers import checkout as checkout_router

    test_suffix = uuid.uuid4().hex
    paypal_order_id = f"TEST-RECONCILE-{test_suffix}"
    capture_id = f"CAPTURE-{test_suffix}"

    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    with SessionLocal() as db:
        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending_approval",
            amount_inr=1000,
            currency="INR",
            paypal_amount=10.53,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            paypal_order_id=paypal_order_id,
            idempotency_key=f"test-create-{test_suffix}",
        )
        db.add(order)
        db.flush()

        attempt = PaymentAttempt(
            order_id=order.id,
            kind="capture",
            status="started",
            paypal_order_id=paypal_order_id,
            idempotency_key=f"test-capture-{test_suffix}",
            error_message="Simulated timeout",
        )
        db.add(attempt)
        db.commit()

    class ReconciliationPayPalClient:
        def __init__(self, settings):
            pass

        async def get_order(self, requested_order_id):
            assert requested_order_id == paypal_order_id
            return {
                "id": paypal_order_id,
                "status": "COMPLETED",
                "purchase_units": [
                    {
                        "payments": {
                            "captures": [
                                {
                                    "id": capture_id,
                                    "status": "COMPLETED",
                                }
                            ]
                        }
                    }
                ],
            }

        async def capture_order(self, paypal_order_id, request_id):
            raise AssertionError(
                "A new capture must not be initiated during reconciliation."
            )

    monkeypatch.setattr(
        checkout_router,
        "PayPalClient",
        ReconciliationPayPalClient,
    )

    response = client.post(
        "/api/checkout/capture-order",
        headers=HEADERS,
        json={
            "paypal_order_id": paypal_order_id,
            "session_id": session_id,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["duplicate"] is True
    assert body["order"]["status"] == "paid"
    assert body["order"]["paypal_capture_id"] == capture_id
    assert body["paypal_status"] == "COMPLETED"

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(
                Order.paypal_order_id == paypal_order_id
            )
        )
        assert saved_order is not None
        assert saved_order.status == "paid"
        assert saved_order.paypal_capture_id == capture_id

        saved_attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "capture",
            )
        )
        assert saved_attempt is not None
        assert saved_attempt.status == "succeeded"



def test_checkout_reconciliation_keeps_non_completed_capture_blocked(
    client, monkeypatch
):
    from app.routers import checkout as checkout_router

    suffix = uuid.uuid4().hex
    paypal_order_id = f"TEST-RECONCILE-APPROVED-{suffix}"

    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    with SessionLocal() as db:
        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending_approval",
            amount_inr=1000,
            currency="INR",
            paypal_amount=10.53,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            paypal_order_id=paypal_order_id,
            idempotency_key=f"test-create-{suffix}",
        )
        db.add(order)
        db.flush()
        db.add(
            PaymentAttempt(
                order_id=order.id,
                kind="capture",
                status="started",
                paypal_order_id=paypal_order_id,
                idempotency_key=f"test-capture-{suffix}",
            )
        )
        db.commit()

    class ApprovedPayPalClient:
        def __init__(self, settings):
            pass

        async def get_order(self, requested_order_id):
            return {"id": requested_order_id, "status": "APPROVED"}

        async def capture_order(self, paypal_order_id, request_id):
            raise AssertionError("Must not initiate a second capture.")

    monkeypatch.setattr(
        checkout_router, "PayPalClient", ApprovedPayPalClient
    )

    response = client.post(
        "/api/checkout/capture-order",
        headers=HEADERS,
        json={
            "paypal_order_id": paypal_order_id,
            "session_id": session_id,
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]["code"]
        == "paypal_capture_reconciliation_required"
    )

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(Order.paypal_order_id == paypal_order_id)
        )
        assert saved_order is not None
        assert saved_order.status != "paid"

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "capture",
            )
        )
        assert attempt is not None
        assert attempt.status == "started"



def test_checkout_reconciliation_keeps_capture_blocked_when_paypal_unreachable(
    client, monkeypatch
):
    import httpx
    from app.routers import checkout as checkout_router

    suffix = uuid.uuid4().hex
    paypal_order_id = f"TEST-RECONCILE-ERROR-{suffix}"

    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    with SessionLocal() as db:
        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending_approval",
            amount_inr=1000,
            currency="INR",
            paypal_amount=10.53,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            paypal_order_id=paypal_order_id,
            idempotency_key=f"test-create-{suffix}",
        )
        db.add(order)
        db.flush()
        db.add(
            PaymentAttempt(
                order_id=order.id,
                kind="capture",
                status="started",
                paypal_order_id=paypal_order_id,
                idempotency_key=f"test-capture-{suffix}",
            )
        )
        db.commit()

    class UnreachablePayPalClient:
        def __init__(self, settings):
            pass

        async def get_order(self, requested_order_id):
            raise httpx.ReadTimeout("Simulated PayPal lookup timeout")

        async def capture_order(self, paypal_order_id, request_id):
            raise AssertionError("Must not initiate a second capture.")

    monkeypatch.setattr(
        checkout_router, "PayPalClient", UnreachablePayPalClient
    )

    response = client.post(
        "/api/checkout/capture-order",
        headers=HEADERS,
        json={
            "paypal_order_id": paypal_order_id,
            "session_id": session_id,
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]["code"]
        == "paypal_capture_reconciliation_required"
    )

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(Order.paypal_order_id == paypal_order_id)
        )
        assert saved_order is not None
        assert saved_order.status != "paid"

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "capture",
            )
        )
        assert attempt is not None
        assert attempt.status == "started"


@pytest.mark.parametrize(
    ("paypal_status", "expected_attempt_status", "expected_order_status", "expected_code"),
    [
        (400, "failed", "capture_failed", "paypal_error"),
        (429, "started", "pending", "paypal_create_outcome_unknown"),
        (500, "started", "pending", "paypal_create_outcome_unknown"),
        (503, "started", "pending", "paypal_create_outcome_unknown"),
    ],
)
def test_checkout_create_paypal_error_states(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    paypal_status: int,
    expected_attempt_status: str,
    expected_order_status: str,
    expected_code: str,
):
    from app.routers import checkout as checkout_router
    from app.services.paypal import PayPalError

    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    product_id = products_response.json()["items"][0]["id"]

    idempotency_key = str(uuid.uuid4())

    class FailingPayPalClient:
        def __init__(self, settings):
            pass

        async def create_order(self, **kwargs):
            raise PayPalError(
                "Simulated PayPal failure",
                status_code=paypal_status,
                payload={"status": paypal_status},
            )

    monkeypatch.setattr(
        checkout_router, "PayPalClient", FailingPayPalClient
    )

    response = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json={
            "product_id": product_id,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        },
    )

    assert response.status_code == 502
    assert response.json()["detail"]["code"] == expected_code

    with SessionLocal() as db:
        order = db.scalar(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        assert order is not None
        assert order.status == expected_order_status

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == order.id,
                PaymentAttempt.kind == "create",
            )
        )
        assert attempt is not None
        assert attempt.status == expected_attempt_status
        assert attempt.http_status == paypal_status


def test_checkout_create_order_same_key_returns_existing_order(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import checkout as checkout_router

    session_response = client.post("/api/sessions", headers=HEADERS)
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    product_id = products_response.json()["items"][0]["id"]

    idempotency_key = str(uuid.uuid4())
    paypal_calls = []

    class SuccessfulPayPalClient:
        def __init__(self, settings):
            pass

        async def create_order(self, **kwargs):
            paypal_calls.append(kwargs["request_id"])
            return {
                "id": "TEST-PAYPAL-" + idempotency_key[:12],
                "status": "CREATED",
                "links": [
                    {
                        "rel": "approve",
                        "href": "https://example.com/approve",
                    }
                ],
            }

    monkeypatch.setattr(
        checkout_router, "PayPalClient", SuccessfulPayPalClient
    )

    payload = {
        "product_id": product_id,
        "session_id": session_id,
        "idempotency_key": idempotency_key,
    }

    first = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json=payload,
    )

    second = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json=payload,
    )

    assert first.status_code == 200
    assert second.status_code == 200

    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True

    assert first.json()["order"]["id"] == second.json()["order"]["id"]
    assert len(paypal_calls) == 1
    assert paypal_calls[0] == idempotency_key

    with SessionLocal() as db:
        orders = db.scalars(
            select(Order).where(Order.idempotency_key == idempotency_key)
        ).all()

        assert len(orders) == 1


def test_checkout_create_order_rejects_same_key_with_different_product(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from app.routers import checkout as checkout_router

    session_response = client.post("/api/sessions", headers=HEADERS)
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    products = products_response.json()["items"]

    assert len(products) >= 2

    first_product_id = products[0]["id"]
    second_product_id = products[1]["id"]

    idempotency_key = str(uuid.uuid4())

    class SuccessfulPayPalClient:
        def __init__(self, settings):
            pass

        async def create_order(self, **kwargs):
            return {
                "id": "TEST-PAYPAL-" + idempotency_key[:12],
                "status": "CREATED",
                "links": [
                    {
                        "rel": "approve",
                        "href": "https://example.com/approve",
                    }
                ],
            }

    monkeypatch.setattr(
        checkout_router, "PayPalClient", SuccessfulPayPalClient
    )

    first = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json={
            "product_id": first_product_id,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        },
    )

    assert first.status_code == 200

    second = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json={
            "product_id": second_product_id,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        },
    )

    assert second.status_code == 409
    assert second.json()["detail"]["code"] == "idempotency_key_conflict"


def test_checkout_create_timeout_then_retry_reuses_same_key(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    import httpx
    from app.routers import checkout as checkout_router

    session_response = client.post("/api/sessions", headers=HEADERS)
    assert session_response.status_code == 200
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    assert products_response.status_code == 200
    product_id = products_response.json()["items"][0]["id"]

    idempotency_key = str(uuid.uuid4())
    paypal_calls = []

    class TimeoutThenSuccessPayPalClient:
        def __init__(self, settings):
            pass

        async def create_order(self, **kwargs):
            paypal_calls.append(kwargs["request_id"])

            if len(paypal_calls) == 1:
                raise httpx.ReadTimeout("Simulated PayPal timeout")

            return {
                "id": "TEST-RETRY-" + idempotency_key[:12],
                "status": "CREATED",
                "links": [
                    {
                        "rel": "approve",
                        "href": "https://example.com/approve",
                    }
                ],
            }

    monkeypatch.setattr(
        checkout_router,
        "PayPalClient",
        TimeoutThenSuccessPayPalClient,
    )

    payload = {
        "product_id": product_id,
        "session_id": session_id,
        "idempotency_key": idempotency_key,
    }

    # First request: PayPal times out.
    first = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json=payload,
    )

    assert first.status_code == 502
    assert (
        first.json()["detail"]["code"]
        == "paypal_create_outcome_unknown"
    )

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(
                Order.idempotency_key == idempotency_key
            )
        )

        assert saved_order is not None
        original_order_id = saved_order.id
        assert saved_order.status != "capture_failed"

        attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "create",
            )
        )

        assert attempt is not None
        assert attempt.status == "started"

    # Second request: retry with exactly the same key and payload.
    second = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json=payload,
    )

    assert second.status_code == 200
    assert second.json()["order"]["id"] == original_order_id
    assert (
        second.json()["order"]["paypal_order_id"]
        == "TEST-RETRY-" + idempotency_key[:12]
    )
    assert second.json()["approval_url"] == "https://example.com/approve"

    # Both PayPal calls must use the same request ID.
    assert paypal_calls == [idempotency_key, idempotency_key]

    with SessionLocal() as db:
        orders = db.scalars(
            select(Order).where(
                Order.idempotency_key == idempotency_key
            )
        ).all()

        assert len(orders) == 1

        attempts = db.scalars(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == original_order_id,
                PaymentAttempt.kind == "create",
            )
        ).all()

        assert len(attempts) == 1
        assert attempts[0].status == "succeeded"


def test_checkout_stale_create_attempt_requires_reconciliation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
):
    from datetime import datetime, timezone, timedelta
    from app.routers import checkout as checkout_router

    session_response = client.post("/api/sessions", headers=HEADERS)
    session_id = session_response.json()["id"]

    products_response = client.get("/api/products", headers=HEADERS)
    product_id = products_response.json()["items"][0]["id"]

    idempotency_key = str(uuid.uuid4())

    # Create an existing order and a stale started attempt.
    with SessionLocal() as db:
        product = db.get(
            __import__("app.models", fromlist=["Product"]).Product,
            product_id,
        )

        order = Order(
            session_id=session_id,
            demo_owner_id=HEADERS["X-Demo-Session"],
            product_id=product_id,
            status="pending",
            amount_inr=product.price_inr,
            currency="INR",
            paypal_amount=10.0,
            paypal_currency="USD",
            fx_rate_inr_per_usd=95.0,
            idempotency_key=idempotency_key,
        )
        db.add(order)
        db.flush()

        from app.models import OrderItem

        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product_id,
                quantity=1,
                unit_price_inr=product.price_inr,
            )
        )
        db.flush()
        attempt = PaymentAttempt(
            order_id=order.id,
            kind="create",
            status="started",
            idempotency_key=idempotency_key,
        )
        db.add(attempt)
        db.commit()

        attempt.created_at = datetime.now(timezone.utc) - timedelta(hours=7)
        db.commit()

    paypal_calls = []

    class ShouldNotCallPayPalClient:
        def __init__(self, settings):
            pass

        async def create_order(self, **kwargs):
            paypal_calls.append(kwargs)
            raise AssertionError("PayPal must not be called for stale attempts")

    monkeypatch.setattr(
        checkout_router,
        "PayPalClient",
        ShouldNotCallPayPalClient,
    )

    response = client.post(
        "/api/checkout/create-order",
        headers=HEADERS,
        json={
            "product_id": product_id,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
        },
    )

    assert response.status_code == 409
    assert (
        response.json()["detail"]["code"]
        == "checkout_reconciliation_required"
    )
    assert paypal_calls == []

    with SessionLocal() as db:
        saved_order = db.scalar(
            select(Order).where(Order.idempotency_key == idempotency_key)
        )
        assert saved_order is not None

        saved_attempt = db.scalar(
            select(PaymentAttempt).where(
                PaymentAttempt.order_id == saved_order.id,
                PaymentAttempt.kind == "create",
            )
        )
        assert saved_attempt is not None
        assert saved_attempt.status == "started"
