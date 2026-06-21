"""
Real (inflation-adjusted) interest rates.

real rate = nominal rate − year-over-year CPI inflation.

Economically, real-rate differentials often track FX better than nominal ones:
what attracts capital is the *real* return, not the headline rate.

Only countries with a CURRENT CPI series on FRED are supported. FRED's OECD CPI
feeds for the UK and Japan are discontinued/stale, so those are intentionally
left out rather than producing misleading (flat/missing) real rates.
"""
from __future__ import annotations

from app.fred_client import fetch_observations
from app.models import Observation

# Country -> a current FRED CPI index series (monthly).
COUNTRY_CPI: dict[str, str] = {
    "US": "CPIAUCSL",            # US CPI, all urban consumers
    "EZ": "CP0000EZ19M086NEST",  # Euro area HICP, all items
}


class RealRateUnavailable(RuntimeError):
    """No current CPI series is available for the given country."""

    def __init__(self, country: str):
        self.country = country
        super().__init__(f"no current CPI for {country}")


def yoy_inflation(cpi_obs: list[Observation]) -> list[Observation]:
    """Year-over-year % inflation from a monthly CPI index series."""
    vals = [o for o in cpi_obs if o.value is not None]
    out: list[Observation] = []
    # Monthly, contiguous series -> 12 steps back is one year.
    for i in range(12, len(vals)):
        cur, prev = vals[i], vals[i - 12]
        if prev.value:
            out.append(Observation(date=cur.date, value=(cur.value / prev.value - 1.0) * 100.0))
    return out


def _subtract_inflation(rate_obs: list[Observation], infl_obs: list[Observation]) -> list[Observation]:
    """real = nominal − inflation.

    Defined only on the nominal rate's OWN observation dates (no forward-fill of
    the rate, no extension beyond its range). Inflation (monthly) is forward-
    filled onto each rate date: we use the most recent inflation on-or-before it.
    """
    infl = sorted((o.date, o.value) for o in infl_obs if o.value is not None)
    out: list[Observation] = []
    j = 0
    last_infl: float | None = None
    for o in sorted(rate_obs, key=lambda x: x.date):
        if o.value is None:
            continue
        while j < len(infl) and infl[j][0] <= o.date:
            last_infl = infl[j][1]
            j += 1
        if last_infl is not None:
            out.append(Observation(date=o.date, value=o.value - last_infl))
    return out


async def to_real(country: str, rate_obs: list[Observation]) -> list[Observation]:
    """Convert nominal-rate observations to real (inflation-adjusted) ones."""
    cpi_id = COUNTRY_CPI.get(country)
    if cpi_id is None:
        raise RealRateUnavailable(country)
    cpi_obs = await fetch_observations(cpi_id)  # full history (cheap, cached)
    infl = yoy_inflation(cpi_obs)
    return _subtract_inflation(rate_obs, infl)
