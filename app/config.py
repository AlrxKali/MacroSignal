"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

import tempfile
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Project root = MacroSignal/  (this file is MacroSignal/app/config.py)
ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- FRED ---
    fred_api_key: str
    fred_base_url: str = "https://api.stlouisfed.org/fred"

    # --- Finnhub (economic calendar; optional) ---
    finnhub_api_key: str = ""
    finnhub_base_url: str = "https://finnhub.io/api/v1"

    @property
    def finnhub_configured(self) -> bool:
        key = self.finnhub_api_key.strip()
        # Treat empty or the doc placeholder as "not configured".
        return bool(key) and not key.lower().startswith("your_")

    # --- Cache ---
    # FRED macro/FX data updates at most daily, so caching for hours is safe.
    # Must be a writable dir: on serverless hosts (Vercel) the project tree is
    # read-only and only the OS temp dir (/tmp) can be written. Override via
    # the CACHE_DIR env var if you want a persistent location.
    cache_dir: Path = Path(tempfile.gettempdir()) / "macrosignal-cache"
    cache_ttl_seconds: int = 60 * 60 * 12  # 12 hours

    # --- CORS ---
    # Allows the local React dev server (any port, since Vite may shift
    # 5173 -> 5174 etc.) and any Vercel-hosted frontend (*.vercel.app).
    # Override via the CORS_ORIGIN_REGEX env var to pin a specific UI domain.
    cors_origin_regex: str = (
        r"https://([a-z0-9-]+\.)*vercel\.app|http://(localhost|127\.0\.0\.1):\d+"
    )


settings = Settings()  # type: ignore[call-arg]
