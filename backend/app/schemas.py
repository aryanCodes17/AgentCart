from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator,model_validator


class Budget(BaseModel):
    amount: float | None = Field(default=None, ge=0)
    currency: str = "INR"


class HardConstraints(BaseModel):
    minimum_ram_gb: int | None = Field(default=None, ge=0)
    minimum_storage_gb: int | None = Field(default=None, ge=0)
    minimum_refresh_hz: int | None = Field(default=None, ge=0)
    minimum_battery_hours: float | None = Field(default=None, ge=0)
    minimum_screen_inches: float | None = Field(default=None, ge=0)
    maximum_weight_kg: float | None = Field(default=None, ge=0)
    wired: bool | None = None
    wireless: bool | None = None
    in_stock_only: bool = True


class PreferenceWeights(BaseModel):
    price: float = 0.25
    performance: float = 0.25
    battery: float = 0.20
    display: float = 0.15
    portability: float = 0.15

    @field_validator("price", "performance", "battery", "display", "portability")
    @classmethod
    def non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("weights must be >= 0")
        return value

    def normalized(self) -> dict[str, float]:
        raw = {
            "price": self.price,
            "performance": self.performance,
            "battery": self.battery,
            "display": self.display,
            "portability": self.portability,
        }
        total = sum(raw.values()) or 1.0
        return {key: value / total for key, value in raw.items()}


class ShoppingRequirementSchema(BaseModel):
    category: str | None = None
    budget: Budget = Field(default_factory=Budget)
    hard_constraints: HardConstraints = Field(default_factory=HardConstraints)
    preferences: dict[str, str] = Field(default_factory=dict)
    use_cases: list[str] = Field(default_factory=list)
    excluded_brands: list[str] = Field(default_factory=list)
    preferred_brands: list[str] = Field(default_factory=list)
    query_text: str = ""
    weights: PreferenceWeights = Field(default_factory=PreferenceWeights)
    needs_clarification: bool = False
    clarifying_question: str | None = None


class ProductOut(BaseModel):
    id: str
    slug: str
    name: str
    brand: str
    category: str
    price_inr: float
    currency: str
    image_url: str
    short_description: str
    description: str
    specs: dict[str, Any]
    available: bool
    data_source: str
    data_label: str
    detail_url: str | None = None

    model_config = {"from_attributes": True}


class ComponentScore(BaseModel):
    name: str
    score: float | None
    reason: str
    unknown: bool = False


class RankedProduct(BaseModel):
    product: ProductOut
    rank: int | None = None
    eligible: bool
    exclusion_reason: str | None = None
    overall_score: float | None = None
    component_scores: list[ComponentScore]
    advantages: list[str]
    disadvantages: list[str]
    missing_information: list[str]
    match_labels: list[str]
    explanation: str


class RankingResponse(BaseModel):
    session_id: str | None = None
    mode: Literal["ai", "rule_based"]
    evaluated_count: int
    eligible_count: int
    excluded_count: int
    weights: dict[str, float]
    methodology: str
    requirement: ShoppingRequirementSchema
    eligible: list[RankedProduct]
    excluded: list[RankedProduct]
    tradeoff_summary: str
    stages: list[str]


class AgentSearchRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = None
    weights: PreferenceWeights | None = None


class AgentMessageRequest(BaseModel):
    session_id: str
    message: str = Field(min_length=1, max_length=4000)


class AgentCompareRequest(BaseModel):
    product_ids: list[str] = Field(min_length=2, max_length=4)
    session_id: str | None = None


class AgentRerankRequest(BaseModel):
    session_id: str
    weights: PreferenceWeights


class CartItemRequest(BaseModel):
    product_id: str
    quantity: int = Field(default=1, ge=1, le=10)


class CreateOrderRequest(BaseModel):
    session_id: str
    items: list[CartItemRequest] = Field(default_factory=list, max_length=50)
    product_id: str | None = None

    @model_validator(mode="after")
    def validate_items(self):
        if not self.items and not self.product_id:
            raise ValueError("Provide at least one cart item.")
        if self.items and self.product_id:
            raise ValueError("Provide items or product_id, not both.")
        if len({item.product_id for item in self.items}) != len(self.items):
            raise ValueError("Duplicate product IDs are not allowed.")
        return self



class CaptureOrderRequest(BaseModel):
    paypal_order_id: str
    session_id: str

class OrderItemOut(BaseModel):
    product: ProductOut
    quantity: int
    unit_price_inr: float


class OrderOut(BaseModel):
    id: str
    product: ProductOut
    items: list["OrderItemOut"] = []
    status: str
    amount_inr: float
    currency: str
    paypal_amount: float
    paypal_currency: str
    fx_rate_inr_per_usd: float
    paypal_order_id: str | None
    paypal_capture_id: str | None
    paypal_status: str | None
    approval_url: str | None
    sandbox: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class HealthOut(BaseModel):
    status: str
    ai: dict[str, Any]
    paypal: dict[str, Any]
    database: str
    demo: bool = True


class PublicSettingsOut(BaseModel):
    app_env: str
    ai_provider: str
    ai_configured: bool
    ai_mode: str
    paypal_configured: bool
    paypal_environment: str
    paypal_currency: str
    catalog_currency: str
    paypal_inr_per_usd: float
    public_frontend_url: str
    public_backend_url: str
    database: str
    demo: bool = True

