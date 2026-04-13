"""Central application settings (environment variables)."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Self

from decimal import Decimal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TradeX API settings. Prefix: TRADEX_ (see .env.example)."""

    model_config = SettingsConfigDict(
        env_prefix="TRADEX_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["development", "production"] = "development"
    jwt_secret: str = ""
    jwt_access_days: int = Field(default=14, ge=1, le=365)
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Comma-separated allowed browser origins",
    )
    cors_origin_regex: str = Field(
        default="",
        description="Optional regex for additional origins (e.g. localhost with any port in dev)",
    )
    cors_allow_all: bool = Field(
        default=False,
        description="If true, allow any Origin (allow_origins=*). Credentials must be false — use only for staging.",
    )
    cors_allow_vercel_hosts: bool = Field(
        default=False,
        description="If true, add CORS regex for https://*.vercel.app (production + preview deploys).",
    )
    database_url: str = Field(
        default="",
        description="SQLAlchemy URL; empty uses bundled SQLite under backend/data/",
    )
    log_level: str = "INFO"
    ollama_generate_url: str = "http://127.0.0.1:11434/api/generate"
    ollama_model: str = "llama3.2"
    # Fernet key (urlsafe base64, 32 bytes) — required to store per-user Binance API secrets
    exchange_fernet_key: str = ""
    # Hard cap on fraction of balance used per exchange order (additional to user max_trade_fraction)
    exchange_max_trade_fraction: Decimal = Field(default=Decimal("0.02"), ge=Decimal("0.001"), le=Decimal("1"))
    binance_spot_testnet_base: str = "https://testnet.binance.vision"
    binance_spot_live_base: str = "https://api.binance.com"

    @model_validator(mode="after")
    def _dev_cors_regex_default(self) -> Self:
        if self.environment == "development" and not (self.cors_origin_regex or "").strip():
            # Allow typical dev URLs: localhost, loopback, and LAN IPs (Next.js dev on another host).
            object.__setattr__(
                self,
                "cors_origin_regex",
                r"http://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3})(:\d+)?",
            )
        return self

    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
