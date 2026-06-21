"""Async client for the FRED `series/observations` endpoint, with caching."""
from __future__ import annotations

import httpx

from app import cache
from app.config import settings
from app.models import Observation


class FredError(RuntimeError):
    """Raised when FRED returns an error or is unreachable."""


def _parse_observations(raw: dict) -> list[Observation]:
    out: list[Observation] = []
    for obs in raw.get("observations", []):
        raw_value = obs.get("value", ".")
        # FRED uses "." for missing values.
        value = None if raw_value in (".", "") else float(raw_value)
        out.append(Observation(date=obs["date"], value=value))
    return out


async def fetch_observations(
    fred_id: str,
    *,
    start: str | None = None,
    end: str | None = None,
    frequency: str | None = None,
) -> list[Observation]:
    """Fetch observations for a FRED series id. Cached on disk by TTL."""
    params: dict[str, str] = {
        "series_id": fred_id,
        "api_key": settings.fred_api_key,
        "file_type": "json",
    }
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end
    if frequency:
        params["frequency"] = frequency

    cache_key = "obs:" + "&".join(f"{k}={v}" for k, v in sorted(params.items()) if k != "api_key")
    cached = cache.get(cache_key)
    if cached is not None:
        return [Observation(**o) for o in cached]

    url = f"{settings.fred_base_url}/series/observations"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise FredError(f"Could not reach FRED: {exc}") from exc

    if resp.status_code != 200:
        # FRED returns a JSON {error_code, error_message} on failure.
        detail = resp.text
        try:
            detail = resp.json().get("error_message", detail)
        except ValueError:
            pass
        raise FredError(f"FRED error {resp.status_code}: {detail}")

    observations = _parse_observations(resp.json())
    cache.set(cache_key, [o.model_dump() for o in observations])
    return observations
