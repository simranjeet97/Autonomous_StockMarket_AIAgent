"""
core/config.py
──────────────
Central configuration loader using Pydantic BaseSettings.
All values are read from environment variables / .env file.
"""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── ADK / Gemini ─────────────────────────────────────────────
    google_api_key: str = Field(default="", alias="GEMINI_API_KEY", description="AI Studio API key")
    trading_model: str = Field(default="gemini-3-flash-preview")

    # Vertex AI (optional, for production)
    google_cloud_project: str = Field(default="")
    google_cloud_location: str = Field(default="us-central1")
    google_genai_use_vertexai: bool = Field(default=False)

    # ── News / Sentiment ──────────────────────────────────────────
    gnews_api_key: str = Field(default="", description="GNews API key (free tier OK)")
    news_timeout_sec: int = Field(default=8, description="HTTP timeout for news fetches")

    # ── Broker — Zerodha / Kite ───────────────────────────────────
    kite_api_key: str = Field(default="")
    kite_api_secret: str = Field(default="")
    kite_access_token: str = Field(default="")

    # ── Database ──────────────────────────────────────────────────
    db_url: str = Field(default="sqlite+aiosqlite:///./trading.db")

    # ── Risk Guards ───────────────────────────────────────────────
    max_daily_loss_inr: float = Field(default=5000.0)
    max_position_lots: int = Field(default=10)
    max_orders_per_second: int = Field(default=10)

    # ── Operational ───────────────────────────────────────────────
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")
    stub_mode: bool = Field(
        default=True, description="Use stub data when broker/news APIs unavailable"
    )

    @field_validator("environment")
    @classmethod
    def validate_env(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"environment must be one of {allowed}")
        return v


# Singleton — import this everywhere
settings = Settings()


def is_production() -> bool:
    return settings.environment == "production"
