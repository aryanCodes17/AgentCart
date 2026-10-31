"""Official PayPal REST v2 helpers.

Endpoints used (documented at https://developer.paypal.com/api/rest/):
- POST {base}/v1/oauth2/token
- POST {base}/v2/checkout/orders
- POST {base}/v2/checkout/orders/{id}/capture
- GET  {base}/v2/checkout/orders/{id}
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import httpx
from fastapi import HTTPException

from app.config import Settings


class PayPalError(Exception):
    def __init__(self, message: str, status_code: int = 502, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.payload = payload or {}


def inr_to_paypal_amount(amount_inr: float, inr_per_usd: float) -> Decimal:
    if inr_per_usd <= 0:
        raise ValueError("INR per USD rate must be positive")
    usd = Decimal(str(amount_inr)) / Decimal(str(inr_per_usd))
    quantized = usd.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized < Decimal("0.01"):
        return Decimal("0.01")
    return quantized


class PayPalClient:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self._client = client
        self._token: str | None = None

    def _require_config(self) -> None:
        if not self.settings.paypal_configured:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "paypal_not_configured",
                    "message": "PayPal Sandbox credentials are not configured. Set PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET.",
                },
            )

    async def _http(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=20.0)
        return self._client

    async def get_access_token(self) -> str:
        self._require_config()
        if self._token:
            return self._token
        http = await self._http()
        response = await http.post(
            f"{self.settings.paypal_base_url}/v1/oauth2/token",
            data={"grant_type": "client_credentials"},
            auth=(self.settings.paypal_client_id, self.settings.paypal_client_secret),
            headers={"Accept": "application/json"},
        )
        if response.status_code >= 400:
            raise PayPalError(
                "PayPal authentication failed. Check Sandbox client ID and secret.",
                status_code=response.status_code,
                payload={"status": response.status_code},
            )
        data = response.json()
        token = data.get("access_token")
        if not token:
            raise PayPalError("PayPal token response did not include access_token.")
        self._token = token
        return token

    async def create_order(
        self,
        *,
        amount: Decimal,
        currency: str,
        description: str,
        custom_id: str,
        return_url: str,
        cancel_url: str,
        request_id: str,
    ) -> dict[str, Any]:
        token = await self.get_access_token()
        http = await self._http()
        payload = {
            "intent": "CAPTURE",
            "purchase_units": [
                {
                    "custom_id": custom_id,
                    "description": description[:127],
                    "amount": {"currency_code": currency, "value": f"{amount:.2f}"},
                }
            ],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "brand_name": "AgentCart",
                        "landing_page": "LOGIN",
                        "user_action": "PAY_NOW",
                        "shipping_preference": "NO_SHIPPING",
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                    }
                }
            },
        }
        response = await http.post(
            f"{self.settings.paypal_base_url}/v2/checkout/orders",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": request_id,
            },
        )
        data = _safe_json(response)
        if response.status_code >= 400:
            raise PayPalError(
                "PayPal create-order failed.",
                status_code=response.status_code,
                payload={"status": response.status_code, "details": _redacted(data)},
            )
        return data

    async def capture_order(self, paypal_order_id: str, request_id: str) -> dict[str, Any]:
        token = await self.get_access_token()
        http = await self._http()
        response = await http.post(
            f"{self.settings.paypal_base_url}/v2/checkout/orders/{paypal_order_id}/capture",
            json={},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "PayPal-Request-Id": request_id,
            },
        )
        data = _safe_json(response)
        if response.status_code >= 400:
            raise PayPalError(
                "PayPal capture failed.",
                status_code=response.status_code,
                payload={"status": response.status_code, "details": _redacted(data)},
            )
        return data

    async def get_order(self, paypal_order_id: str) -> dict[str, Any]:
        token = await self.get_access_token()
        http = await self._http()
        response = await http.get(
            f"{self.settings.paypal_base_url}/v2/checkout/orders/{paypal_order_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        data = _safe_json(response)
        if response.status_code >= 400:
            raise PayPalError(
                "PayPal get-order failed.",
                status_code=response.status_code,
                payload={
                    "status": response.status_code,
                    "details": _redacted(data),
                },
            )
        return data


def approval_url_from(order: dict[str, Any]) -> str | None:
    for link in order.get("links") or []:
        if link.get("rel") in {"approve", "payer-action"}:
            return link.get("href")
    return None


def capture_id_from(capture_payload: dict[str, Any]) -> str | None:
    units = capture_payload.get("purchase_units") or []
    for unit in units:
        captures = ((unit.get("payments") or {}).get("captures")) or []
        for item in captures:
            if item.get("id"):
                return item["id"]
    return None


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"raw": data}
    except Exception:
        return {"text": response.text[:500]}


def _redacted(data: dict[str, Any]) -> dict[str, Any]:
    blocked = {"access_token", "client_secret", "authorization"}
    return {key: value for key, value in data.items() if key.lower() not in blocked}
