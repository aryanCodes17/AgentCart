from app.catalog_data import PRODUCTS
from app.schemas import Budget, HardConstraints, PreferenceWeights, ShoppingRequirementSchema
from app.services.ranking import hard_constraint_violations, overall_from_components, rank_products


def _req(**kwargs) -> ShoppingRequirementSchema:
    data = {
        "category": "laptop",
        "budget": Budget(amount=70000, currency="INR"),
        "hard_constraints": HardConstraints(minimum_ram_gb=16),
        "use_cases": ["coding", "college"],
        "query_text": "coding laptop",
    }
    data.update(kwargs)
    return ShoppingRequirementSchema.model_validate(data)


def test_hard_constraints_drop_low_ram_and_over_budget():
    req = _req()
    campus = next(p for p in PRODUCTS if p["id"] == "prod-laptop-campusbook-15")
    dev = next(p for p in PRODUCTS if p["id"] == "prod-laptop-devstation-16")
    north = next(p for p in PRODUCTS if p["id"] == "prod-laptop-northline-14")
    assert any("RAM" in reason for reason in hard_constraint_violations(campus, req))
    assert any("exceeds budget" in reason.lower() for reason in hard_constraint_violations(dev, req))
    assert hard_constraint_violations(north, req) == []


def test_unavailable_is_excluded():
    req = _req()
    empty = next(p for p in PRODUCTS if p["id"] == "prod-laptop-unavailable")
    reasons = hard_constraint_violations(empty, req)
    assert any("unavailable" in reason.lower() for reason in reasons)


def test_unknown_battery_is_not_scored_high():
    req = _req()
    value = next(p for p in PRODUCTS if p["id"] == "prod-laptop-valuenote-15")
    eligible, _excluded = rank_products([value], req)
    assert eligible
    battery = next(score for score in eligible[0].component_scores if score.name == "battery")
    assert battery.unknown is True
    assert battery.score is None
    assert any("battery" in item.lower() for item in eligible[0].missing_information)


def test_ranking_changes_when_battery_weight_increases():
    req = _req()
    laptops = [p for p in PRODUCTS if p["category"] == "laptop"]
    default_eligible, _ = rank_products(laptops, req, PreferenceWeights())
    battery_eligible, _ = rank_products(
        laptops, req, PreferenceWeights(battery=0.7, price=0.05, performance=0.1, display=0.1, portability=0.05)
    )
    assert default_eligible and battery_eligible
    default_ids = [item.product.id for item in default_eligible]
    battery_ids = [item.product.id for item in battery_eligible]
    assert set(default_ids) == set(battery_ids)
    # PixelView vs Aether: battery-heavy ranking should not invent scores for ValueNote battery.


def test_excluded_brands():
    req = _req(excluded_brands=["Northline"])
    north = next(p for p in PRODUCTS if p["id"] == "prod-laptop-northline-14")
    assert any("excluded" in reason.lower() for reason in hard_constraint_violations(north, req))


def test_overall_ignores_unknown_components():
    from app.schemas import ComponentScore

    score = overall_from_components(
        [
            ComponentScore(name="price", score=0.8, reason="ok"),
            ComponentScore(name="battery", score=None, reason="missing", unknown=True),
        ],
        {"price": 0.5, "battery": 0.5},
    )
    assert score == 0.8


def test_wireless_headphones_budget():
    req = ShoppingRequirementSchema(
        category="headphones",
        budget=Budget(amount=8000),
        hard_constraints=HardConstraints(wireless=True),
    )
    items = [p for p in PRODUCTS if p["category"] == "headphones"]
    eligible, excluded = rank_products(items, req)
    assert all(item.product.specs.get("connectivity") == "wireless" for item in eligible)
    assert any(item.product.id == "prod-hp-studio-wired" for item in excluded)
    assert all(item.product.price_inr <= 8000 for item in eligible)
