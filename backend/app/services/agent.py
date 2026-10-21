from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.provider import get_provider
from app.ai import tools
from app.config import Settings
from app.models import ConversationMessage, RecommendationResult, RecommendationRun, ShoppingRequirement, ShoppingSession
from app.schemas import PreferenceWeights, RankingResponse, ShoppingRequirementSchema
from app.services.ranking import METHODOLOGY, rank_products, tradeoff_summary


def persist_requirement(db: Session, session: ShoppingSession, requirement: ShoppingRequirementSchema, source: str) -> None:
    row = session.requirement
    payload = requirement.model_dump()
    if row is None:
        row = ShoppingRequirement(session_id=session.id, payload=payload, source=source, clarifying_question=requirement.clarifying_question)
        db.add(row)
    else:
        row.payload = payload
        row.source = source
        row.clarifying_question = requirement.clarifying_question
    db.flush()


def persist_run(
    db: Session,
    session: ShoppingSession,
    mode: str,
    requirement: ShoppingRequirementSchema,
    eligible,
    excluded,
    weights: dict[str, float],
) -> RecommendationRun:
    run = RecommendationRun(
        session_id=session.id,
        mode=mode,
        evaluated_count=len(eligible) + len(excluded),
        eligible_count=len(eligible),
        excluded_count=len(excluded),
        weights=weights,
        methodology=METHODOLOGY,
    )
    db.add(run)
    db.flush()
    for item in eligible + excluded:
        db.add(
            RecommendationResult(
                run_id=run.id,
                product_id=item.product.id,
                rank=item.rank,
                eligible=item.eligible,
                exclusion_reason=item.exclusion_reason,
                overall_score=item.overall_score,
                component_scores=[score.model_dump() for score in item.component_scores],
                advantages=item.advantages,
                disadvantages=item.disadvantages,
                missing_information=item.missing_information,
                match_labels=item.match_labels,
                explanation=item.explanation,
            )
        )
    return run


async def run_search(
    db: Session,
    settings: Settings,
    session: ShoppingSession,
    message: str,
    weights: PreferenceWeights | None = None,
) -> RankingResponse:
    previous = None
    if session.requirement:
        previous = ShoppingRequirementSchema.model_validate(session.requirement.payload)

    provider, mode = get_provider(settings)
    requirement = await provider.extract_requirements(message, previous)
    if weights:
        requirement.weights = weights
    persist_requirement(db, session, requirement, mode)

    db.add(ConversationMessage(session_id=session.id, role="user", content=message))
    stages = ["Understanding your requirements"]

    if requirement.needs_clarification:
        question = requirement.clarifying_question or "Could you add a bit more detail?"
        db.add(ConversationMessage(session_id=session.id, role="assistant", content=question, extras={"clarifying": True}))
        session.title = message[:80]
        return RankingResponse(
            mode=mode if mode == "ai" else "rule_based",
            evaluated_count=0,
            eligible_count=0,
            excluded_count=0,
            weights=requirement.weights.normalized(),
            methodology=METHODOLOGY,
            requirement=requirement,
            eligible=[],
            excluded=[],
            tradeoff_summary=question,
            stages=stages,
        )

    stages.append("Searching the catalog")
    products = tools.search_products(db, requirement)
    stages.append("Checking constraints")
    tools.validate_constraints(products, requirement)
    stages.append("Comparing suitable products")
    eligible, excluded = rank_products(products, requirement, requirement.weights)
    stages.append("Preparing your recommendations")

    persist_run(db, session, mode, requirement, eligible, excluded, requirement.weights.normalized())

    summary = tradeoff_summary(eligible)
    grounded = {
        "requirement": requirement.model_dump(),
        "top": [item.model_dump() for item in eligible[:3]],
        "excluded_sample": [item.model_dump() for item in excluded[:5]],
        "mode": mode,
    }
    llm_text = await provider.explain(message, grounded)
    assistant = llm_text or summary
    if mode == "rule_based":
        assistant = "Rule-based demo mode (no LLM key configured).\n\n" + assistant
    db.add(ConversationMessage(session_id=session.id, role="assistant", content=assistant, extras={"mode": mode}))
    session.title = message[:80]
    session.status = "active"

    return RankingResponse(
        mode="ai" if mode == "ai" else "rule_based",
        evaluated_count=len(eligible) + len(excluded),
        eligible_count=len(eligible),
        excluded_count=len(excluded),
        weights=requirement.weights.normalized(),
        methodology=METHODOLOGY,
        requirement=requirement,
        eligible=eligible,
        excluded=excluded,
        tradeoff_summary=assistant,
        stages=stages,
    )


async def rerank(db: Session, session: ShoppingSession, weights: PreferenceWeights) -> RankingResponse:
    if not session.requirement:
        raise ValueError("No stored requirements to rerank")
    requirement = ShoppingRequirementSchema.model_validate(session.requirement.payload)
    requirement.weights = weights
    persist_requirement(db, session, requirement, session.requirement.source)
    products = tools.search_products(db, requirement)
    eligible, excluded = rank_products(products, requirement, weights)
    persist_run(db, session, "rule_based", requirement, eligible, excluded, weights.normalized())
    summary = tradeoff_summary(eligible)
    db.add(
        ConversationMessage(
            session_id=session.id,
            role="assistant",
            content="Ranking recalculated from catalog data using your updated weights. No LLM call was required.\n\n" + summary,
            extras={"rerank": True},
        )
    )
    return RankingResponse(
        mode="rule_based",
        evaluated_count=len(eligible) + len(excluded),
        eligible_count=len(eligible),
        excluded_count=len(excluded),
        weights=weights.normalized(),
        methodology=METHODOLOGY,
        requirement=requirement,
        eligible=eligible,
        excluded=excluded,
        tradeoff_summary=summary,
        stages=["Checking constraints", "Comparing suitable products"],
    )
