import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
import app.models

from app.config import get_settings
from app.db import Base, SessionLocal, engine
from app.routers import agent, checkout, health, orders, products, sessions
from app.routers import settings as settings_router
from app.seed import seed_products

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("agentcart")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        added = seed_products(db)
        logger.info("Catalog seed complete, added=%s", added)
    finally:
        db.close()
    yield


app = FastAPI(
    title="AgentCart API",
    version="0.1.0",
    description="AI shopping agent backend with deterministic ranking and PayPal Sandbox checkout.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type", "X-Demo-Session"],
)

app.include_router(health.router)
app.include_router(settings_router.router)
app.include_router(products.router)
app.include_router(agent.router)
app.include_router(sessions.router)
app.include_router(checkout.router)
app.include_router(orders.router)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_handler(_request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.exception("Database error: %s", exc)
    return JSONResponse(status_code=500, content={"detail": "Database error"})


@app.middleware("http")
async def limit_body(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > 50_000:
        return JSONResponse(status_code=413, content={"detail": "Request too large"})
    return await call_next(request)
