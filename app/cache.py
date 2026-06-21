"""
Dead-simple on-disk JSON cache.

FRED data refreshes at most once a day, so we avoid hammering the API (and stay
well under rate limits) by caching raw responses for a TTL. Survives restarts.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

from app.config import settings


def _key_to_path(key: str) -> Path:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]
    return settings.cache_dir / f"{digest}.json"


def get(key: str) -> Any | None:
    path = _key_to_path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if time.time() - payload.get("_cached_at", 0) > settings.cache_ttl_seconds:
        return None  # stale
    return payload.get("data")


def set(key: str, data: Any) -> None:
    settings.cache_dir.mkdir(parents=True, exist_ok=True)
    path = _key_to_path(key)
    payload = {"_cached_at": time.time(), "data": data}
    path.write_text(json.dumps(payload), encoding="utf-8")
