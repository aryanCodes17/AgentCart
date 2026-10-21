from collections import defaultdict
from time import time

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db
from app.models import ShoppingSession, new_id

_hits: dict[str, list[float]] = defaultdict(list)


def current_owner(
    x_demo_session: str | None = Header(default=None, alias="X-Demo-Session"),
) -> str:
    if x_demo_session and len(x_demo_session) >= 8:
        return x_demo_session[:64]
    raise HTTPException(status_code=400, detail="Missing X-Demo-Session header. This prototype uses a demo session, not production auth.")


def get_session_for_owner(
    session_id: str,
    db: Session = Depends(get_db),
    owner: str = Depends(current_owner),
) -> ShoppingSession:
    session = db.get(ShoppingSession, session_id)
    if session is None or session.demo_owner_id != owner:
        raise HTTPException(status_code=404, detail="Session not found for this demo owner.")
    return session


def rate_limit_agent(request: Request, settings: Settings = Depends(get_settings)) -> None:
    key = request.headers.get("X-Demo-Session") or request.client.host if request.client else "anon"
    now = time()
    window = 60.0
    bucket = [stamp for stamp in _hits[key] if now - stamp < window]
    if len(bucket) >= settings.agent_rate_limit_per_minute:
        raise HTTPException(status_code=429, detail="Too many AI requests. Wait a minute and retry.")
    bucket.append(now)
    _hits[key] = bucket


def get_or_create_session(db: Session, owner: str, session_id: str | None) -> ShoppingSession:
    if session_id:
        session = db.get(ShoppingSession, session_id)
        if session and session.demo_owner_id == owner:
            return session
        if session:
            raise HTTPException(status_code=403, detail="Session belongs to a different demo owner.")
    session = ShoppingSession(id=new_id(), demo_owner_id=owner)
    db.add(session)
    db.flush()
    return session
