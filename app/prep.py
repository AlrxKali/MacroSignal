"""
Shared preparation of the (differential, fx) series used by the changes-based
analyses (lead/lag and regression).

Builds business-day series on the currency's actual trading dates, with the
differential forward-filled. `quote_obs=None` means use the base rate's level
directly (single-rate analysis) instead of a differential.
"""
from __future__ import annotations

from app.align import align
from app.models import Observation


def trading_day_series(
    base_obs: list[Observation],
    fx_obs: list[Observation],
    quote_obs: list[Observation] | None = None,
) -> tuple[list[str], list[float | None], list[float | None]]:
    """Return (dates, differential_series, fx_series) aligned on trading dates."""
    series: dict[str, list[Observation]] = {"base": base_obs, "fx": fx_obs}
    if quote_obs is not None:
        series["quote"] = quote_obs
    rows = align(series)

    # Restrict to the currency's actual trading dates (avoid weekend fill noise).
    fx_dates = {o.date for o in fx_obs if o.value is not None}
    trading = [r for r in rows if r["date"] in fx_dates]

    dates: list[str] = []
    diff: list[float | None] = []
    fx: list[float | None] = []
    for r in trading:
        base_val = r.get("base")
        if quote_obs is not None:
            quote_val = r.get("quote")
            diff.append(
                base_val - quote_val  # type: ignore[operator]
                if base_val is not None and quote_val is not None
                else None
            )
        else:
            diff.append(base_val)  # type: ignore[arg-type]
        fx.append(r.get("fx"))  # type: ignore[arg-type]
        dates.append(r["date"])  # type: ignore[arg-type]
    return dates, diff, fx
