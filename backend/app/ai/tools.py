"""Server-side tools the agent may request. Arguments are re-validated here."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.schemas import PreferenceWeights, ShoppingRequirementSchema
from app.services.catalog import all_product_dicts, get_product, product_to_dict
from app.services.ranking import METHODOLOGY, hard_constraint_violations, rank_products, tradeoff_summary


def search_products(db: Session, requirement: ShoppingRequirementSchema) -> list[dict[str, Any]]:
    return all_product_dicts(db, requirement.category)


def get_product_details(db: Session, product_id: str) -> dict[str, Any] | None:
    product = get_product(db, product_id)
    return product_to_dict(product) if product else None


def validate_constraints(products: list[dict[str, Any]], requirement: ShoppingRequirementSchema) -> dict[str, Any]:
    eligible = []
    excluded = []
    for product in products:
        reasons = hard_constraint_violations(product, requirement)
        if reasons:
            excluded.append({"product_id": product["id"], "reasons": reasons})
        else:
            eligible.append(product["id"])
    return {
        "evaluated": len(products),
        "eligible_ids": eligible,
        "excluded": excluded,
    }


def rank_tool(
    products: list[dict[str, Any]],
    requirement: ShoppingRequirementSchema,
    weights: PreferenceWeights | None = None,
) -> dict[str, Any]:
    eligible, excluded = rank_products(products, requirement, weights)
    return {
        "methodology": METHODOLOGY,
        "eligible": [item.model_dump() for item in eligible],
        "excluded": [item.model_dump() for item in excluded],
        "tradeoff_summary": tradeoff_summary(eligible),
    }


def compare_products(
    db: Session,
    product_ids: list[str],
    requirement: ShoppingRequirementSchema | None,
) -> dict[str, Any]:
    found: list[dict[str, Any]] = []
    missing: list[str] = []
    for product_id in product_ids:
        details = get_product_details(db, product_id)
        if details:
            found.append(details)
        else:
            missing.append(product_id)
    req = requirement or ShoppingRequirementSchema()
    eligible, excluded = rank_products(found, req)
    ranked = eligible + excluded
    return {
        "missing_ids": missing,
        "items": [item.model_dump() for item in ranked],
        "tradeoff_summary": tradeoff_summary(eligible),
        "methodology": METHODOLOGY,
    }


def explain_recommendation(item: dict[str, Any]) -> str:
    return str(item.get("explanation") or "No grounded explanation is available.")
