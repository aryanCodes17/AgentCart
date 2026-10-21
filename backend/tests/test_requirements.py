from pydantic import ValidationError

from app.schemas import PreferenceWeights, ShoppingRequirementSchema
from app.services.requirements import extract_budget, merge_requirements, rule_based_extract


def test_extract_budget_under_70000():
    assert extract_budget("Find me the best laptop for coding under ₹70,000.") == 70000


def test_extract_budget_with_k_suffix():
    assert extract_budget("headphones under 8k with good battery") == 8000


def test_rule_based_laptop_coding():
    req = rule_based_extract(
        "Find me the best laptop for coding under ₹70,000. I need at least 16 GB RAM, good battery life."
    )
    assert req.category == "laptop"
    assert req.budget.amount == 70000
    assert req.hard_constraints.minimum_ram_gb == 16
    assert req.preferences.get("battery_life") == "high"
    assert "coding" in req.use_cases
    assert req.needs_clarification is False


def test_clarifies_when_category_missing():
    req = rule_based_extract("something nice under 5000")
    assert req.needs_clarification is True
    assert req.clarifying_question


def test_follow_up_merges_budget():
    first = rule_based_extract("laptop with 16 GB RAM")
    second = rule_based_extract("change budget to under 60000", first)
    assert second.category == "laptop"
    assert second.budget.amount == 60000
    assert second.hard_constraints.minimum_ram_gb == 16


def test_weights_must_be_non_negative():
    try:
        PreferenceWeights(price=-1)
        raised = False
    except ValidationError:
        raised = True
    assert raised


def test_schema_rejects_negative_budget():
    try:
        ShoppingRequirementSchema.model_validate({"budget": {"amount": -5, "currency": "INR"}})
        raised = False
    except ValidationError:
        raised = True
    assert raised


def test_merge_keeps_earlier_constraints():
    base = rule_based_extract("laptop under 70000 with 16 GB RAM")
    incoming = rule_based_extract("increase importance of battery life")
    merged = merge_requirements(base, incoming)
    assert merged.hard_constraints.minimum_ram_gb == 16
    assert merged.budget.amount == 70000


def test_extract_excluded_brands_with_prefix():
    from app.services.requirements import extract_excluded_brands

    assert extract_excluded_brands("Exclude brand Northline") == ["Northline"]
    assert extract_excluded_brands("Avoid brands Northline and Dell") == ["Northline", "Dell"]
    assert extract_excluded_brands("No brand Apple") == ["Apple"]
    assert extract_excluded_brands("Exclude Northline") == ["Northline"]

