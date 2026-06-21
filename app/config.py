"""Application configuration, loaded from environment / .env."""
from __future__ import annotations

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
    cache_dir: Path = ROOT_DIR / ".cache"
    cache_ttl_seconds: int = 60 * 60 * 12  # 12 hours

    # --- CORS (the React dev server) ---
    # Regex so any localhost port works (Vite may shift 5173 -> 5174 etc.).
    cors_origin_regex: str = r"http://(localhost|127\.0\.0\.1):\d+"


settings = Settings()  # type: ignore[call-arg]
