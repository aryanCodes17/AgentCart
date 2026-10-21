from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    frontend_origins: str = "http://localhost:3000"
    demo_session_secret: str = "dev-only-change-me"
    database_url: str = "sqlite+pysqlite:///./agentcart.db"

  
    ai_provider: str = "groq"
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-120b"
    ai_timeout_seconds: float = 25.0


    paypal_client_id: str = ""
    paypal_client_secret: str = ""
    paypal_base_url: str = "https://api-m.sandbox.paypal.com"
    paypal_currency: str = "USD"
    paypal_inr_per_usd: float = 83.0

    public_frontend_url: str = "http://localhost:3000"
    public_backend_url: str = "http://localhost:8000"

    agent_rate_limit_per_minute: int = 20

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.frontend_origins.split(",") if origin.strip()]

    
    @property
    def ai_configured(self) -> bool:
        return bool(self.groq_api_key.strip())


    @property
    def paypal_configured(self) -> bool:
        return bool(self.paypal_client_id.strip() and self.paypal_client_secret.strip())

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
