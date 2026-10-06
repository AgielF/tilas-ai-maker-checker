"""Application configuration via pydantic-settings (12-Factor App)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "Tilas"
    app_env: Literal["dev", "staging", "prod"] = "dev"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://timbang:timbang@localhost:5432/timbang"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # 9Router / LLM
    nine_router_base_url: str = "http://localhost:20128/v1"
    nine_router_api_key: str = ""  # set via env NINE_ROUTER_API_KEY

    # CORS
    cors_origins: list[str] = []

    # JWT — set via env, NEVER hardcode
    jwt_secret: str = ""
    jwt_expire_minutes: int = 30

    # Rate limit
    rate_limit_default: str = "60/minute"
    rate_limit_enabled: bool = True
    rate_limit_storage_uri: str = "memory://"  # switch to redis:// in prod

    # Langflow
    langflow_base_url: str = "http://127.0.0.1:7860"
    langflow_api_key: str = ""  # set via env LANGFLOW_API_KEY — NEVER hardcode
    langflow_maker_flow_id: str = ""
    langflow_checker_flow_id: str = ""
    langflow_narrator_flow_id: str = ""
    langflow_file_node_ids: str = ""
    langflow_timeout_seconds: float = 120.0

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors(cls, v: object) -> list[str]:
        """Accept comma-separated string or list."""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v  # type: ignore[return-value]


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
