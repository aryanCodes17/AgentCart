"""Deterministic ranking after hard-constraint filtering.

Missing attributes never receive an optimistic score. They are marked unknown
and excluded from the weighted average.
"""

from __future__ import annotations

from typing import Any

from app.schemas import (
    ComponentScore,
    PreferenceWeights,
    ProductOut,
    RankedProduct,
    ShoppingRequirementSchema,
)

METHODOLOGY = (
    "Hard constraints are applied first (budget, category, availability, "
    "minimum specifications, excluded brands). Eligible products are then scored "
    "with a weighted average of available numeric attributes only. Unknown "
    "attributes contribute neither a bonus nor a penalty. Weights are user-"
    "configurable and normalized to 1.0. Scores are not AI-generated ratings."
)

CATEGORY_ALIASES = {
    "laptops": "laptop",
    "notebook": "laptop",
    "headphones": "headphones",
    "headset": "headphones",
    "earbuds": "headphones",
    "monitors": "monitor",
    "display": "monitor",
    "keyboards": "keyboard",
    "mice": "mouse",
    "smartphone": "smartphone",
    "phones": "smartphone",
    "tablets": "tablet",
}


def normalize_category(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().lower()
    return CATEGORY_ALIASES.get(key, key)


def _num(specs: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = specs.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def hard_constraint_violations(product: dict[str, Any], requirement: ShoppingRequirementSchema) -> list[str]:
    reasons: list[str] = []
    specs = product.get("specs") or {}
    category = normalize_category(requirement.category)
    if category and product.get("category") != category:
        reasons.append(f"Category is {product.get('category')}, request is {category}.")

    budget = requirement.budget.amount
    if budget is not None and float(product["price_inr"]) > budget:
        reasons.append(
            f"Price ₹{float(product['price_inr']):,.0f} exceeds budget ₹{budget:,.0f}."
        )

    constraints = requirement.hard_constraints
    if constraints.in_stock_only and not product.get("available", True):
        reasons.append("Product is marked unavailable in the demo catalog.")

    excluded = {brand.lower() for brand in requirement.excluded_brands}
    if product.get("brand", "").lower() in excluded:
        reasons.append(f"Brand {product.get('brand')} is excluded.")

    ram = _num(specs, "ram_gb")
    if constraints.minimum_ram_gb is not None:
        if ram is None:
            reasons.append("RAM is unknown, so the minimum RAM constraint cannot be verified.")
        elif ram < constraints.minimum_ram_gb:
            reasons.append(f"RAM {int(ram)} GB is below the required {constraints.minimum_ram_gb} GB.")

    storage = _num(specs, "storage_gb")
    if constraints.minimum_storage_gb is not None:
        if storage is None:
            reasons.append("Storage is unknown, so the minimum storage constraint cannot be verified.")
        elif storage < constraints.minimum_storage_gb:
            reasons.append(
                f"Storage {int(storage)} GB is below the required {constraints.minimum_storage_gb} GB."
            )

    refresh = _num(specs, "refresh_hz")
    if constraints.minimum_refresh_hz is not None:
        if refresh is None:
            reasons.append("Refresh rate is unknown.")
        elif refresh < constraints.minimum_refresh_hz:
            reasons.append(
                f"Refresh rate {int(refresh)} Hz is below {constraints.minimum_refresh_hz} Hz."
            )

    battery = _num(specs, "battery_hours")
    if constraints.minimum_battery_hours is not None:
        if battery is None:
            reasons.append("Battery life is unknown, so the minimum battery constraint cannot be verified.")
        elif battery < constraints.minimum_battery_hours:
            reasons.append(
                f"Battery {battery} hours is below the required {constraints.minimum_battery_hours} hours."
            )

    screen = _num(specs, "screen_inches")
    if constraints.minimum_screen_inches is not None:
        if screen is None:
            reasons.append("Screen size is unknown.")
        elif screen < constraints.minimum_screen_inches:
            reasons.append(
                f"Screen {screen}\" is below the required {constraints.minimum_screen_inches}\"."
            )

    weight = _num(specs, "weight_kg")
    if constraints.maximum_weight_kg is not None:
        if weight is None:
            reasons.append("Weight is unknown, so the maximum weight constraint cannot be verified.")
        elif weight > constraints.maximum_weight_kg:
            reasons.append(
                f"Weight {weight} kg exceeds the maximum {constraints.maximum_weight_kg} kg."
            )

    connectivity = str(specs.get("connectivity") or "").lower()
    if constraints.wireless is True and connectivity == "wired":
        reasons.append("Request requires wireless connectivity.")
    if constraints.wired is True and connectivity == "wireless":
        reasons.append("Request requires wired connectivity.")

    return reasons


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def component_scores(
    product: dict[str, Any],
    requirement: ShoppingRequirementSchema,
) -> list[ComponentScore]:
    specs = product.get("specs") or {}
    scores: list[ComponentScore] = []
    budget = requirement.budget.amount
    price = float(product["price_inr"])

    if budget and budget > 0:
        # Prefer using more of the budget without exceeding it. Already-excluded
        # over-budget items still get a 0 price score if scored.
        if price > budget:
            price_score = 0.0
            reason = "Over budget."
        else:
            utilization = price / budget
            price_score = _clamp(0.35 + 0.65 * utilization) if utilization >= 0.45 else _clamp(utilization / 0.45 * 0.55)
            reason = f"Uses {utilization:.0%} of the stated budget."
        scores.append(ComponentScore(name="price", score=round(price_score, 4), reason=reason, unknown=False))
    else:
        scores.append(ComponentScore(name="price", score=None, reason="No budget provided.", unknown=True))

    perf_bits: list[float] = []
    perf_notes: list[str] = []
    ram = _num(specs, "ram_gb")
    cpu = _num(specs, "cpu_tier")
    storage = _num(specs, "storage_gb")
    refresh = _num(specs, "refresh_hz")
    if ram is not None:
        perf_bits.append(_clamp(ram / 32))
        perf_notes.append(f"{int(ram)} GB RAM")
    if cpu is not None:
        perf_bits.append(_clamp(cpu / 5))
        perf_notes.append(f"CPU tier {int(cpu)}/5")
    if storage is not None:
        perf_bits.append(_clamp(storage / 1024))
        perf_notes.append(f"{int(storage)} GB storage")
    if refresh is not None:
        perf_bits.append(_clamp(refresh / 144))
        perf_notes.append(f"{int(refresh)} Hz")
    if perf_bits:
        scores.append(
            ComponentScore(
                name="performance",
                score=round(sum(perf_bits) / len(perf_bits), 4),
                reason=", ".join(perf_notes),
                unknown=False,
            )
        )
    else:
        scores.append(
            ComponentScore(
                name="performance",
                score=None,
                reason="No verified performance attributes in the catalog.",
                unknown=True,
            )
        )

    battery = _num(specs, "battery_hours")
    if battery is not None:
        scores.append(
            ComponentScore(
                name="battery",
                score=round(_clamp(battery / 12), 4),
                reason=f"Catalog battery_hours={battery}.",
                unknown=False,
            )
        )
    else:
        scores.append(
            ComponentScore(
                name="battery",
                score=None,
                reason="Battery life is not in the catalog; no battery score assigned.",
                unknown=True,
            )
        )

    display_bits: list[float] = []
    display_notes: list[str] = []
    panel = str(specs.get("panel") or specs.get("display_panel") or "").lower()
    ppi = _num(specs, "ppi")
    brightness = _num(specs, "brightness_nits")
    resolution_score = _num(specs, "display_score")
    if resolution_score is not None:
        display_bits.append(_clamp(resolution_score / 5))
        display_notes.append(f"display_score {resolution_score}/5")
    if ppi is not None:
        display_bits.append(_clamp(ppi / 300))
        display_notes.append(f"{int(ppi)} PPI")
    if brightness is not None:
        display_bits.append(_clamp(brightness / 400))
        display_notes.append(f"{int(brightness)} nits")
    if panel in {"oled", "mini-led"}:
        display_bits.append(1.0)
        display_notes.append(panel)
    elif panel in {"ips", "va"}:
        display_bits.append(0.7)
        display_notes.append(panel)
    if display_bits:
        scores.append(
            ComponentScore(
                name="display",
                score=round(sum(display_bits) / len(display_bits), 4),
                reason=", ".join(display_notes),
                unknown=False,
            )
        )
    else:
        scores.append(
            ComponentScore(
                name="display",
                score=None,
                reason="Display quality is not quantified in the catalog.",
                unknown=True,
            )
        )

    weight = _num(specs, "weight_kg")
    if weight is not None:
        # Lighter is better for portability. 1.1 kg ~ 1.0, 2.4 kg ~ 0.2
        port_score = _clamp((2.5 - weight) / 1.4)
        scores.append(
            ComponentScore(
                name="portability",
                score=round(port_score, 4),
                reason=f"{weight} kg.",
                unknown=False,
            )
        )
    else:
        scores.append(
            ComponentScore(
                name="portability",
                score=None,
                reason="Weight is not in the catalog; no portability score assigned.",
                unknown=True,
            )
        )

    return scores


def overall_from_components(components: list[ComponentScore], weights: dict[str, float]) -> float | None:
    usable: list[tuple[float, float]] = []
    for item in components:
        if item.unknown or item.score is None:
            continue
        usable.append((item.score, weights.get(item.name, 0.0)))
    weight_sum = sum(weight for _score, weight in usable)
    if weight_sum <= 0:
        return None
    return round(sum(score * weight for score, weight in usable) / weight_sum, 4)


def labels_for(product: dict[str, Any], requirement: ShoppingRequirementSchema, eligible: bool, components: list[ComponentScore]) -> list[str]:
    tags: list[str] = []
    budget = requirement.budget.amount
    if budget is not None and float(product["price_inr"]) > budget:
        tags.append("Exceeds budget")
    elif eligible:
        tags.append("Meets requirements")
    unknown = [item.name for item in components if item.unknown]
    if unknown:
        tags.append("Missing specification")
    preferred = {brand.lower() for brand in requirement.preferred_brands}
    if product.get("brand", "").lower() in preferred:
        tags.append("Preferred brand")
    return tags


def advantages_disadvantages(product: dict[str, Any], requirement: ShoppingRequirementSchema, components: list[ComponentScore]) -> tuple[list[str], list[str], list[str]]:
    adv: list[str] = []
    disadv: list[str] = []
    missing: list[str] = []
    specs = product.get("specs") or {}
    budget = requirement.budget.amount
    price = float(product["price_inr"])
    if budget and price <= budget:
        adv.append(f"Within budget at ₹{price:,.0f}.")
    if requirement.preferred_brands and product.get("brand", "").lower() in {b.lower() for b in requirement.preferred_brands}:
        adv.append(f"{product.get('brand')} matches a preferred brand.")
    for item in components:
        if item.unknown:
            missing.append(item.reason)
        elif item.score is not None and item.score >= 0.75:
            adv.append(f"Strong {item.name}: {item.reason}")
        elif item.score is not None and item.score <= 0.4:
            disadv.append(f"Weaker {item.name}: {item.reason}")
    if specs.get("notes"):
        disadv.append(str(specs["notes"]))
    return adv, disadv, missing


def grounded_explanation(
    product: dict[str, Any],
    requirement: ShoppingRequirementSchema,
    components: list[ComponentScore],
    eligible: bool,
    exclusion_reason: str | None,
) -> str:
    name = product["name"]
    if not eligible:
        return f"{name} is not eligible. {exclusion_reason or 'It violates a hard constraint.'}"
    known = [item for item in components if not item.unknown and item.score is not None]
    unknown = [item.name for item in components if item.unknown]
    parts = [f"{name} remains after hard-constraint checks."]
    if requirement.budget.amount is not None:
        parts.append(f"Catalog price is ₹{float(product['price_inr']):,.0f} against a ₹{requirement.budget.amount:,.0f} budget.")
    if known:
        ranked = sorted(known, key=lambda item: item.score or 0, reverse=True)
        parts.append("Highest verified component: " + ranked[0].name + f" ({ranked[0].reason}).")
    if unknown:
        parts.append("Not scored because catalog data is missing: " + ", ".join(unknown) + ".")
    if requirement.use_cases:
        parts.append("Use cases considered from the request: " + ", ".join(requirement.use_cases) + ".")
    return " ".join(parts)


def rank_products(
    products: list[dict[str, Any]],
    requirement: ShoppingRequirementSchema,
    weights: PreferenceWeights | None = None,
) -> tuple[list[RankedProduct], list[RankedProduct]]:
    weight_map = (weights or requirement.weights).normalized()
    eligible: list[RankedProduct] = []
    excluded: list[RankedProduct] = []

    for product in products:
        violations = hard_constraint_violations(product, requirement)
        components = component_scores(product, requirement)
        adv, disadv, missing = advantages_disadvantages(product, requirement, components)
        is_eligible = not violations
        overall = overall_from_components(components, weight_map) if is_eligible else None
        reason = " ".join(violations) if violations else None
        item = RankedProduct(
            product=ProductOut.model_validate(product),
            eligible=is_eligible,
            exclusion_reason=reason,
            overall_score=overall,
            component_scores=components,
            advantages=adv,
            disadvantages=disadv,
            missing_information=missing,
            match_labels=labels_for(product, requirement, is_eligible, components),
            explanation=grounded_explanation(product, requirement, components, is_eligible, reason),
        )
        if is_eligible:
            eligible.append(item)
        else:
            excluded.append(item)

    eligible.sort(key=lambda row: (-(row.overall_score or 0.0), float(row.product.price_inr)))
    for index, row in enumerate(eligible, start=1):
        row.rank = index
        if index == 1:
            if "Best fit for your priorities" not in row.match_labels:
                row.match_labels.append("Best fit for your priorities")
    return eligible, excluded


def tradeoff_summary(eligible: list[RankedProduct]) -> str:
    if not eligible:
        return "No catalog products satisfy the mandatory constraints."
    if len(eligible) == 1:
        top = eligible[0]
        return f"Only {top.product.name} satisfies the hard constraints in this demo catalog."
    top, second = eligible[0], eligible[1]
    return (
        f"{top.product.name} ranks first under the current weights "
        f"(score {top.overall_score}). {second.product.name} is the closest alternative "
        f"(score {second.overall_score}). Scores use only verified catalog attributes."
    )
