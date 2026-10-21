import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


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
        json={"product_id": product_id, "session_id": session_id, "amount": 1},
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

