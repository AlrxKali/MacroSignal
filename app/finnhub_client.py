"""
Finnhub economic-calendar client (optional feature).

Used to overlay central-bank rate decisions on the charts. The economic-calendar
endpoint may require a paid Finnhub plan, so callers must tolerate:
  - FinnhubNotConfigured: no usable key in .env
  - FinnhubAccessError: key present but the endpoint denied access (e.g. 403)
Both are non-fatal; the app simply shows no event markers.
"""
from __future__ import annotations

import httpx

from app import cache
from app.config import settings


class FinnhubNotConfigured(RuntimeError):
    """No usable Finnhub API key is configured."""


class FinnhubAccessError(RuntimeError):
    """Finnhub rejected the request (often a plan/permission issue)."""


async def fetch_economic_calendar(start: str, end: str) -> list[dict]:
    """Return raw Finnhub economic-calendar entries for [start, end].

    Cached on disk (the historical calendar is essentially static).
    """
    if not settings.finnhub_configured:
        raise FinnhubNotConfigured("FINNHUB_API_KEY is not set")

    cache_key = f"finnhub:econ:{start}:{end}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    url = f"{settings.finnhub_base_url}/calendar/economic"
    params = {"from": start, "to": end, "token": settings.finnhub_api_key}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise FinnhubAccessError(f"Could not reach Finnhub: {exc}") from exc

    if resp.status_code in (401, 403):
        raise FinnhubAccessError(
            f"Finnhub denied access ({resp.status_code}); the economic calendar "
            "may require a paid plan."
        )
    if resp.status_code != 200:
        raise FinnhubAccessError(f"Finnhub error {resp.status_code}: {resp.text[:200]}")

    data = resp.json()
    # Finnhub returns {"economicCalendar": [ ... ]}.
    entries = data.get("economicCalendar", []) if isinstance(data, dict) else []
    cache.set(cache_key, entries)
    return entries
