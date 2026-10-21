"""Rule-based requirement extraction used when no LLM is configured.

This is intentionally conservative: it does not invent preferences that are
not present in the text.
"""

from __future__ import annotations

import re

from app.schemas import Budget, HardConstraints, PreferenceWeights, ShoppingRequirementSchema
from app.services.ranking import normalize_category

_BUDGET_PATTERNS = [
    re.compile(r"(?:under|below|upto|up to|max(?:imum)?)\s*(?:[₹$€£\?]|rs\.?\s*|inr\s*)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?", re.I),
    re.compile(r"(?:[₹$€£\?]|rs\.?\s*|inr\s*)(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?\s*(?:budget|max|cap)?", re.I),
    re.compile(r"budget\s*(?:of|is|:)?\s*(?:[₹$€£\?]|rs\.?\s*)?\s*(\d[\d,]*(?:\.\d+)?)\s*(k|thousand)?", re.I),
]


_RAM = re.compile(r"(?:at least|min(?:imum)?|>=)?\s*(\d+)\s*gb\s*ram", re.I)
_RAM2 = re.compile(r"(\d+)\s*gb\s*(?:of\s*)?ram", re.I)

CATEGORY_KEYWORDS = {
    "laptop": ["laptop", "notebook", "coding machine", "macbook"],
    "headphones": ["headphone", "headset", "earbuds", "earphones"],
    "monitor": ["monitor", "display"],
    "keyboard": ["keyboard"],
    "mouse": ["mouse"],
    "smartphone": ["smartphone", "phone", "android phone"],
    "tablet": ["tablet", "ipad"],
}


def _parse_amount(raw: str, suffix: str | None) -> float:
    value = float(raw.replace(",", ""))
    if suffix:
        value *= 1000
    return value


def extract_budget(text: str) -> float | None:
    for pattern in _BUDGET_PATTERNS:
        match = pattern.search(text)
        if match:
            return _parse_amount(match.group(1), match.group(2))
    return None


def extract_category(text: str) -> str | None:
    lowered = text.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return category
    if "coding" in lowered or "college" in lowered or "programming" in lowered:
        return "laptop"
    return None


def extract_ram(text: str) -> int | None:
    match = _RAM.search(text) or _RAM2.search(text)
    if not match:
        return None
    return int(match.group(1))


def extract_excluded_brands(text: str) -> list[str]:
    match = re.search(r"(?:exclude|not|no|avoid)\s+(?:brands?|make)?\s*([A-Za-z][\w\s,]{1,40})", text, re.I)
    if not match:
        return []
    raw = match.group(1).strip()
    tokens = re.split(r",|\band\b", raw)
    results: list[str] = []
    stop_words = {"a", "the", "any", "my", "brand", "brands", "make", "item", "items", "product", "products"}
    for tok in tokens:
        clean = tok.strip()
        if not clean:
            continue
        word = clean.split()[0]
        if word.lower() not in stop_words and word.capitalize() not in results:
            results.append(word.capitalize())
    return results



def extract_use_cases(text: str) -> list[str]:
    lowered = text.lower()
    found: list[str] = []
    for label in ("coding", "college", "programming", "productivity", "gaming", "commute", "office", "writing"):
        if label in lowered:
            found.append(label)
    return found


def merge_requirements(base: ShoppingRequirementSchema, incoming: ShoppingRequirementSchema) -> ShoppingRequirementSchema:
    data = base.model_dump()
    new = incoming.model_dump()
    if new.get("category"):
        data["category"] = new["category"]
    if new.get("budget", {}).get("amount") is not None:
        data["budget"] = new["budget"]
    for key, value in new.get("hard_constraints", {}).items():
        if value not in (None, False) or key == "in_stock_only":
            if value is not None:
                data["hard_constraints"][key] = value
    data["preferences"] = {**data.get("preferences", {}), **new.get("preferences", {})}
    data["use_cases"] = list(dict.fromkeys(data.get("use_cases", []) + new.get("use_cases", [])))
    data["excluded_brands"] = list(dict.fromkeys(data.get("excluded_brands", []) + new.get("excluded_brands", [])))
    data["preferred_brands"] = list(dict.fromkeys(data.get("preferred_brands", []) + new.get("preferred_brands", [])))
    if new.get("query_text"):
        data["query_text"] = new["query_text"]
    return ShoppingRequirementSchema.model_validate(data)


def rule_based_extract(text: str, previous: ShoppingRequirementSchema | None = None) -> ShoppingRequirementSchema:
    category = extract_category(text)
    budget_amount = extract_budget(text)
    ram = extract_ram(text)
    lowered = text.lower()

    wireless = None
    if "wireless" in lowered:
        wireless = True
    wired = True if "wired" in lowered and "wireless" not in lowered else None

    battery_pref = "high" if any(token in lowered for token in ("battery", "last through", "all day")) else None
    display_pref = "high" if any(token in lowered for token in ("display", "screen", "oled", "monitor")) else None
    durable = "high" if "last through college" in lowered or "durable" in lowered else None

    preferences: dict[str, str] = {}
    if battery_pref:
        preferences["battery_life"] = battery_pref
    if display_pref:
        preferences["display_quality"] = display_pref
    if durable:
        preferences["durability"] = durable

    weights_kwargs: dict[str, float] = {}
    if "battery" in lowered:
        weights_kwargs["battery"] = 0.35
        weights_kwargs["price"] = 0.2
    if "display" in lowered or "monitor for programming" in lowered:
        weights_kwargs["display"] = 0.35
    if "portable" in lowered or "light" in lowered:
        weights_kwargs["portability"] = 0.3

    requirement = ShoppingRequirementSchema(
        category=normalize_category(category),
        budget=Budget(amount=budget_amount, currency="INR"),
        hard_constraints=HardConstraints(
            minimum_ram_gb=ram,
            wireless=wireless,
            wired=wired,
            in_stock_only=True,
        ),
        preferences=preferences,
        use_cases=extract_use_cases(text),
        excluded_brands=extract_excluded_brands(text),
        query_text=text,
        weights=PreferenceWeights(**weights_kwargs) if weights_kwargs else PreferenceWeights(),
    )

    if previous:
        requirement = merge_requirements(previous, requirement)

    if requirement.category is None and previous is None:
        requirement.needs_clarification = True
        requirement.clarifying_question = (
            "Which category should I search — laptops, headphones, monitors, keyboards, mice, phones, or tablets?"
        )
    elif requirement.budget.amount is None and previous is None:
        requirement.needs_clarification = True
        requirement.clarifying_question = "What is your maximum budget in ₹ INR?"
    else:
        requirement.needs_clarification = False
        requirement.clarifying_question = None

    return requirement
