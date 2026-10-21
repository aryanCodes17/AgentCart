from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import PublicSettingsOut

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/public", response_model=PublicSettingsOut)
def get_public_settings(settings: Settings = Depends(get_settings)) -> PublicSettingsOut:
    mode = "ai" if settings.ai_configured else "rule_based"
    return PublicSettingsOut(
        app_env=settings.app_env,
        ai_provider=settings.ai_provider,
        ai_configured=settings.ai_configured,
        ai_mode=mode,
        paypal_configured=settings.paypal_configured,
        paypal_environment="sandbox" if "sandbox" in settings.paypal_base_url else "production",
        paypal_currency=settings.paypal_currency,
        catalog_currency="INR",
        paypal_inr_per_usd=settings.paypal_inr_per_usd,
        public_frontend_url=settings.public_frontend_url,
        public_backend_url=settings.public_backend_url,
        database="sqlite" if settings.is_sqlite else "postgresql",
        demo=True,
    )
