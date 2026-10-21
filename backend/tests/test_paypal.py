from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services.paypal import PayPalClient, PayPalError, inr_to_paypal_amount


def test_inr_conversion_is_documented_rounding():
    assert inr_to_paypal_amount(70000, 83) == Decimal("843.37")


def test_invalid_fx_rate():
    with pytest.raises(ValueError):
        inr_to_paypal_amount(100, 0)


@pytest.mark.asyncio
async def test_missing_credentials_raise_503():
    settings = Settings(paypal_client_id="", paypal_client_secret="")
    client = PayPalClient(settings)
    with pytest.raises(HTTPException) as exc:
        await client.get_access_token()
    assert exc.value.status_code == 503


@pytest.mark.asyncio
async def test_auth_error_becomes_paypal_error():
    settings = Settings(paypal_client_id="id", paypal_client_secret="secret")
    http = AsyncMock()
    response = MagicMock()
    response.status_code = 401
    response.json.return_value = {"error": "invalid_client"}
    http.post = AsyncMock(return_value=response)
    client = PayPalClient(settings, client=http)
    with pytest.raises(PayPalError) as exc:
        await client.get_access_token()
    assert "paypal_client_secret" not in str(exc.value.payload).lower()
    assert settings.paypal_client_secret not in str(exc.value.payload)


@pytest.mark.asyncio
async def test_create_order_uses_server_amount():
    settings = Settings(paypal_client_id="id", paypal_client_secret="secret")
    http = AsyncMock()
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"access_token": "tok"}
    order_response = MagicMock()
    order_response.status_code = 201
    order_response.json.return_value = {
        "id": "PP-1",
        "status": "CREATED",
        "links": [{"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=PP-1"}],
    }
    http.post = AsyncMock(side_effect=[token_response, order_response])
    client = PayPalClient(settings, client=http)
    data = await client.create_order(
        amount=Decimal("10.00"),
        currency="USD",
        description="test",
        custom_id="ord-1",
        return_url="http://localhost:3000/ok",
        cancel_url="http://localhost:3000/cancel",
        request_id="idem-1",
    )
    assert data["id"] == "PP-1"
    sent = http.post.call_args_list[1].kwargs["json"]
    assert sent["purchase_units"][0]["amount"]["value"] == "10.00"
    assert sent["purchase_units"][0]["amount"]["currency_code"] == "USD"


def test_capture_id_from_valid_payload():
    from app.services.paypal import capture_id_from

    payload = {
        "id": "ORD-123",
        "status": "COMPLETED",
        "purchase_units": [
            {
                "payments": {
                    "captures": [
                        {"id": "CAP-999", "status": "COMPLETED"}
                    ]
                }
            }
        ],
    }
    assert capture_id_from(payload) == "CAP-999"


def test_capture_id_from_empty_or_missing_payload():
    from app.services.paypal import capture_id_from

    assert capture_id_from({}) is None
    assert capture_id_from({"purchase_units": []}) is None
    assert capture_id_from({"purchase_units": [{"payments": {}}]}) is None


def test_approval_url_extraction():
    from app.services.paypal import approval_url_from

    order_approve = {
        "links": [
            {"rel": "self", "href": "https://api.sandbox.paypal.com/v2/checkout/orders/1"},
            {"rel": "approve", "href": "https://www.sandbox.paypal.com/checkoutnow?token=1"},
        ]
    }
    assert approval_url_from(order_approve) == "https://www.sandbox.paypal.com/checkoutnow?token=1"

    order_payer_action = {
        "links": [
            {"rel": "payer-action", "href": "https://www.sandbox.paypal.com/checkoutnow?token=2"},
        ]
    }
    assert approval_url_from(order_payer_action) == "https://www.sandbox.paypal.com/checkoutnow?token=2"

    assert approval_url_from({"links": []}) is None
    assert approval_url_from({}) is None


@pytest.mark.asyncio
async def test_capture_order_calls_correct_endpoint():
    settings = Settings(paypal_client_id="id", paypal_client_secret="secret")
    http = AsyncMock()
    token_response = MagicMock()
    token_response.status_code = 200
    token_response.json.return_value = {"access_token": "tok"}

    capture_response = MagicMock()
    capture_response.status_code = 201
    capture_response.json.return_value = {
        "id": "ORD-1",
        "status": "COMPLETED",
        "purchase_units": [{"payments": {"captures": [{"id": "CAP-1", "status": "COMPLETED"}]}}],
    }
    http.post = AsyncMock(side_effect=[token_response, capture_response])
    client = PayPalClient(settings, client=http)
    data = await client.capture_order("ORD-1", request_id="idem-cap-1")
    assert data["status"] == "COMPLETED"
    assert http.post.call_args_list[1].args[0].endswith("/v2/checkout/orders/ORD-1/capture")

