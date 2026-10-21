from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import current_owner, get_or_create_session
from app.models import ConversationMessage, RecommendationRun, ShoppingSession
from app.schemas import ProductOut
from app.services.catalog import get_product, product_to_dict

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("")
def create_session(db: Session = Depends(get_db), owner: str = Depends(current_owner)) -> dict:
    session = get_or_create_session(db, owner, None)
    db.commit()
    return {"id": session.id, "title": session.title}


@router.get("")
def list_sessions(db: Session = Depends(get_db), owner: str = Depends(current_owner)) -> dict:
    rows = list(
        db.scalars(
            select(ShoppingSession)
            .where(ShoppingSession.demo_owner_id == owner)
            .order_by(ShoppingSession.updated_at.desc())
            .limit(20)
        )
    )
    return {
        "items": [
            {"id": row.id, "title": row.title, "status": row.status, "updated_at": row.updated_at}
            for row in rows
        ]
    }


@router.get("/{session_id}")
def get_session(
    session_id: str, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> dict:
    session = db.get(ShoppingSession, session_id)
    if session is None or session.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Session not found.")
    messages = list(
        db.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session.id)
            .order_by(ConversationMessage.created_at.asc())
        )
    )
    return {
        "id": session.id,
        "title": session.title,
        "status": session.status,
        "requirement": session.requirement.payload if session.requirement else None,
        "requirement_source": session.requirement.source if session.requirement else None,
        "messages": [
            {"id": msg.id, "role": msg.role, "content": msg.content, "extras": msg.extras, "created_at": msg.created_at}
            for msg in messages
        ],
    }


@router.get("/{session_id}/recommendations")
def get_recommendations(
    session_id: str, db: Session = Depends(get_db), owner: str = Depends(current_owner)
) -> dict:
    session = db.get(ShoppingSession, session_id)
    if session is None or session.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Session not found.")
    run = db.scalar(
        select(RecommendationRun)
        .where(RecommendationRun.session_id == session.id)
        .order_by(RecommendationRun.created_at.desc())
        .limit(1)
    )
    if run is None:
        return {"run": None, "results": []}
    results = []
    for item in sorted(run.results, key=lambda row: (not row.eligible, row.rank or 999)):
        product = get_product(db, item.product_id)
        results.append(
            {
                "rank": item.rank,
                "eligible": item.eligible,
                "exclusion_reason": item.exclusion_reason,
                "overall_score": item.overall_score,
                "component_scores": item.component_scores,
                "advantages": item.advantages,
                "disadvantages": item.disadvantages,
                "missing_information": item.missing_information,
                "match_labels": item.match_labels,
                "explanation": item.explanation,
                "product": ProductOut.model_validate(product_to_dict(product)) if product else None,
            }
        )
    return {
        "run": {
            "id": run.id,
            "mode": run.mode,
            "evaluated_count": run.evaluated_count,
            "eligible_count": run.eligible_count,
            "excluded_count": run.excluded_count,
            "weights": run.weights,
            "methodology": run.methodology,
            "created_at": run.created_at,
        },
        "results": results,
    }
