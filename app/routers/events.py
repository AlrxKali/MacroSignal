"""
Central-bank policy-decision events (FOMC/ECB) to overlay on the charts.

Two sources, with automatic fallback:
  1. Finnhub economic calendar  all scheduled decisions (incl. no-change), but
     the endpoint often requires a paid plan (free tier returns 403).
  2. FRED-derived rate changes  the dates where the policy rate actually stepped,
     detected from the same FRED data we already use. No extra dependency; always
     available. Captures actual moves only (not no-change meetings).

If Finnhub is unavailable (not configured, access denied, or empty) we fall back
to the FRED-derived markers so the overlay always works.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.config import settings
from app.finnhub_client import (
    FinnhubAccessError,
    FinnhubNotConfigured,
    fetch_economic_calendar,
)
from app.fred_client import FredError, fetch_observations
from app.models import EventsResponse, PolicyEvent

router = APIRouter(prefix="/api", tags=["events"])

# Map Finnhub country codes -> our catalog country codes.
_COUNTRY_MAP = {"US": "US", "EU": "EZ", "EA": "EZ"}

# Event-name fragments that denote a central-bank rate decision.
_DECISION_HINTS = ("interest rate decision", "deposit facility rate", "rate decision")

# Policy-rate FRED series per country, for deriving actual rate-change dates.
# These step cleanly on decision days (unlike the noisy effective rate).
_POLICY_SERIES = {
    "US": ("DFEDTARU", "Fed funds target (upper)"),
    "EZ": ("ECBDFR", "ECB Deposit Facility Rate"),
}


def _to_float(v) -> float | None:
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_decision(event_name: str) -> bool:
    name = event_name.lower()
    return any(h in name for h in _DECISION_HINTS)


def _parse_finnhub(raw: list[dict], wanted: set[str]) -> list[PolicyEvent]:
    out: list[PolicyEvent] = []
    for item in raw:
        country = _COUNTRY_MAP.get(str(item.get("country", "")).upper())
        if country is None or country not in wanted:
            continue
        event_name = str(item.get("event", ""))
        if not _is_decision(event_name):
            continue
        time = str(item.get("time", ""))
        date = time.split(" ")[0] if time else ""
        if not date:
            continue
        actual = _to_float(item.get("actual"))
        prev = _to_float(item.get("prev"))
        out.append(
            PolicyEvent(
                date=date,
                country=country,
                event=event_name,
                actual=actual,
                prev=prev,
                changed=(actual is not None and prev is not None and actual != prev),
            )
        )
    return out


async def _derive_from_fred(wanted: set[str], start: str, end: str) -> list[PolicyEvent]:
    """Detect dates where each country's policy rate stepped up or down."""
    out: list[PolicyEvent] = []
    for country in wanted:
        spec = _POLICY_SERIES.get(country)
        if spec is None:
            continue
        fred_id, label = spec
        try:
            obs = await fetch_observations(fred_id, start=start, end=end)
        except FredError:
            continue
        prev: float | None = None
        for o in obs:
            if o.value is None:
                continue
            if prev is not None and o.value != prev:
                direction = "hike" if o.value > prev else "cut"
                out.append(
                    PolicyEvent(
                        date=o.date,
                        country=country,
                        event=f"{label} {direction} ({prev:g}→{o.value:g})",
                        actual=o.value,
                        prev=prev,
                        changed=True,
                    )
                )
            prev = o.value
    out.sort(key=lambda e: e.date)
    return out


@router.get("/events", response_model=EventsResponse)
async def events(
    start: str = Query(..., description="YYYY-MM-DD"),
    end: str = Query(..., description="YYYY-MM-DD"),
    countries: str = Query(default="US,EZ", description="comma-separated: US,EZ"),
):
    wanted = {c.strip().upper() for c in countries.split(",") if c.strip()}

    finnhub_note: str | None = None
    if settings.finnhub_configured:
        try:
            raw = await fetch_economic_calendar(start, end)
            parsed = _parse_finnhub(raw, wanted)
            if parsed:
                return EventsResponse(configured=True, source="finnhub", note=None, events=parsed)
            finnhub_note = "Finnhub returned no decisions for this range; "
        except FinnhubNotConfigured:
            pass
        except FinnhubAccessError as exc:
            finnhub_note = f"{exc} "

    # Fallback: derive actual rate-change dates from FRED.
    derived = await _derive_from_fred(wanted, start, end)
    note_prefix = finnhub_note or ""
    if derived:
        note = f"{note_prefix}Showing actual policy rate changes derived from FRED (no-change meetings not shown)."
    else:
        note = f"{note_prefix}No policy rate changes found in this range."
    return EventsResponse(
        configured=settings.finnhub_configured,
        source="fred-derived",
        note=note,
        events=derived,
    )
