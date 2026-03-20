from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Annotated
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


def normalize_database_url(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("postgres://"):
        normalized = f"postgresql+psycopg://{normalized.removeprefix('postgres://')}"
    elif normalized.startswith("postgresql://"):
        normalized = f"postgresql+psycopg://{normalized.removeprefix('postgresql://')}"

    parsed = urlparse(normalized)
    hostname = parsed.hostname or ""
    if parsed.scheme.startswith("postgresql") and hostname.endswith(".neon.tech"):
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        if "sslmode" not in query:
            query["sslmode"] = "require"
            normalized = urlunparse(parsed._replace(query=urlencode(query)))
    return normalized


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Household Portfolio Tracker API"
    api_prefix: str = "/api"
    portfolio_db_url: str = Field(
        default=f"sqlite:///{Path(__file__).resolve().parents[2] / 'data' / 'portfolio.db'}",
        validation_alias=AliasChoices("PORTFOLIO_DB_URL", "DATABASE_URL"),
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=lambda: ["http://127.0.0.1:5173"]
    )
    allowed_hosts: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["*"])
    finnhub_api_key: str | None = None
    alpha_vantage_api_key: str | None = None
    fx_api_base_url: str = "https://api.frankfurter.app"
    environment: str = "development"
    enable_scheduler: bool = True
    force_https: bool = False
    auth_password: str | None = None
    auth_secret: str | None = None
    auth_token_ttl_minutes: int = 720
    log_level: str = "INFO"
    observability_max_endpoints: int = 12
    brokerage_sync_provider: str = "disabled"
    brokerage_sync_local_profile_id: str = "household-primary"
    brokerage_sync_activity_lookback_days: int = 365
    snaptrade_client_id: str | None = None
    snaptrade_consumer_key: str | None = None
    snaptrade_redirect_uri: str | None = None

    @field_validator("cors_origins", "allowed_hosts", mode="before")
    @classmethod
    def split_list_settings(cls, value: str | list[str] | None) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            return value
        trimmed = value.strip()
        if not trimmed:
            return []
        if trimmed.startswith("["):
            parsed = json.loads(trimmed)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        return [origin.strip() for origin in trimmed.split(",") if origin.strip()]

    @field_validator("portfolio_db_url", mode="before")
    @classmethod
    def normalize_database_url_value(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def auth_enabled(self) -> bool:
        return bool(self.auth_password)

    @property
    def brokerage_sync_enabled(self) -> bool:
        return self.brokerage_sync_provider.lower() != "disabled"

    @property
    def database_backend(self) -> str:
        parsed = urlparse(self.portfolio_db_url)
        if parsed.scheme.startswith("sqlite"):
            return "sqlite"
        if parsed.scheme.startswith("postgresql"):
            return "postgresql"
        return parsed.scheme or "unknown"


def get_settings_file_path() -> Path:
    configured_path = os.environ.get("PORTFOLIO_SETTINGS_FILE")
    if configured_path:
        return Path(configured_path).expanduser().resolve()
    return (Path(__file__).resolve().parents[3] / ".env").resolve()


def refresh_settings_cache(updates: dict[str, str | None] | None = None) -> Settings:
    if updates:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    get_settings.cache_clear()
    return get_settings()


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings(_env_file=get_settings_file_path())
    if settings.database_backend == "sqlite":
        db_path = settings.portfolio_db_url.removeprefix("sqlite:///")
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return settings
