from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import HealthOut

router = APIRouter(tags=["health"])


@router.get("/api/health", response_model=HealthOut)
def health(settings: Settings = Depends(get_settings)) -> HealthOut:
    mode = "ai" if settings.ai_configured else "rule_based"
    return HealthOut(
        status="ok",
        database="sqlite" if settings.is_sqlite else "postgresql",
        ai={
            "configured": settings.ai_configured,
            "provider": settings.ai_provider,
            "mode": mode,
            "model": settings.groq_model if settings.ai_configured else None,
        },
        paypal={
            "configured": settings.paypal_configured,
            "environment": "sandbox" if "sandbox" in settings.paypal_base_url else "unknown",
            "charge_currency": settings.paypal_currency,
            "catalog_currency": "INR",
        },
        demo=True,
    )
