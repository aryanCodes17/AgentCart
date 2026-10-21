from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.ai import tools
from app.config import Settings, get_settings
from app.db import get_db
from app.deps import current_owner, get_or_create_session, rate_limit_agent
from app.models import ShoppingSession
from app.schemas import (
    AgentCompareRequest,
    AgentMessageRequest,
    AgentRerankRequest,
    AgentSearchRequest,
    RankingResponse,
    ShoppingRequirementSchema,
)
from app.services.agent import rerank, run_search

router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(rate_limit_agent)])


def _with_session(result: RankingResponse, session_id: str) -> RankingResponse:
    return result.model_copy(update={"session_id": session_id})


@router.post("/search", response_model=RankingResponse)
async def search(
    body: AgentSearchRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> RankingResponse:
    session = get_or_create_session(db, owner, body.session_id)
    result = await run_search(db, settings, session, body.message, body.weights)
    db.commit()
    return _with_session(result, session.id)


@router.post("/message", response_model=RankingResponse)
async def message(
    body: AgentMessageRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
    settings: Settings = Depends(get_settings),
) -> RankingResponse:
    row = db.get(ShoppingSession, body.session_id)
    if row is None or row.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Session not found.")
    result = await run_search(db, settings, row, body.message)
    db.commit()
    return _with_session(result, row.id)


@router.post("/compare")
def compare(
    body: AgentCompareRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> dict:
    requirement = None
    if body.session_id:
        session = db.get(ShoppingSession, body.session_id)
        if session is None or session.demo_owner_id != owner:
            raise HTTPException(status_code=404, detail="Session not found.")
        if session.requirement:
            requirement = ShoppingRequirementSchema.model_validate(session.requirement.payload)
    return tools.compare_products(db, body.product_ids, requirement)


@router.post("/rerank", response_model=RankingResponse)
async def rerank_endpoint(
    body: AgentRerankRequest,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> RankingResponse:
    session = db.get(ShoppingSession, body.session_id)
    if session is None or session.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Session not found.")
    try:
        result = await rerank(db, session, body.weights)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    db.commit()
    return _with_session(result, session.id)
