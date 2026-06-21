"""Typed API response models."""
from __future__ import annotations

from pydantic import BaseModel

from app.series_catalog import SeriesMeta


class Observation(BaseModel):
    date: str            # ISO date, "YYYY-MM-DD"
    value: float | None  # None when FRED reports a gap (".")


class SeriesData(BaseModel):
    meta: SeriesMeta
    observations: list[Observation]


class ComparePoint(BaseModel):
    date: str
    rate: float | None
    fx: float | None


class CompareResponse(BaseModel):
    rate_meta: SeriesMeta
    fx_meta: SeriesMeta
    points: list[ComparePoint]


class DifferentialPoint(BaseModel):
    date: str
    base_rate: float | None   # e.g. US rate
    quote_rate: float | None  # e.g. euro-area rate
    differential: float | None  # base_rate - quote_rate
    fx: float | None


class DifferentialResponse(BaseModel):
    base_rate_meta: SeriesMeta
    quote_rate_meta: SeriesMeta
    fx_meta: SeriesMeta
    points: list[DifferentialPoint]


class RecessionInterval(BaseModel):
    start: str
    end: str


class RecessionsResponse(BaseModel):
    intervals: list[RecessionInterval]


class PolicyEvent(BaseModel):
    date: str             # YYYY-MM-DD
    country: str          # mapped to our codes: "US", "EZ"
    event: str            # e.g. "Fed Interest Rate Decision"
    actual: float | None  # decided rate (%), if provided
    prev: float | None    # previous rate (%), if provided
    changed: bool         # True when actual != prev (an actual policy move)


class EventsResponse(BaseModel):
    configured: bool      # is a usable Finnhub key present?
    source: str           # "finnhub" | "fred-derived" | "none"
    note: str | None      # human-readable status (why empty, etc.)
    events: list[PolicyEvent]


class RollingCorrPoint(BaseModel):
    date: str
    r: float | None
    n: int


class RollingCorrResponse(BaseModel):
    base_rate_meta: SeriesMeta
    quote_rate_meta: SeriesMeta | None
    fx_meta: SeriesMeta
    window: int        # change/return period (trading days)
    corr_window: int   # trailing length of each correlation (trading days)
    points: list[RollingCorrPoint]
    overall_r: float | None  # correlation over the whole sample, for reference


class ScatterPoint(BaseModel):
    date: str
    x: float            # change in differential over the window (pp)
    y: float            # currency return over the window (%)


class RegressionResponse(BaseModel):
    base_rate_meta: SeriesMeta
    quote_rate_meta: SeriesMeta | None
    fx_meta: SeriesMeta
    window: int
    lag: int
    points: list[ScatterPoint]
    slope: float | None       # %FX return per 1pp change in differential
    intercept: float | None
    r: float | None
    r2: float | None
    n: int
    n_effective: float
    r_critical_95: float | None
    significant: bool


class LagPoint(BaseModel):
    lag: int            # trading days; >0 = FX move follows the rate move
    r: float | None     # Pearson correlation at this lag
    n: int              # number of paired observations


class LagAnalysisResponse(BaseModel):
    base_rate_meta: SeriesMeta
    quote_rate_meta: SeriesMeta | None  # None => single-rate (level) changes
    fx_meta: SeriesMeta
    window: int                          # trading days used for change/return
    points: list[LagPoint]
    best_lag: int | None
    best_r: float | None
    # Significance, corrected for overlapping windows.
    n_raw: int                           # paired observations at lag 0
    n_effective: float                   # ~ n_raw / window (non-overlapping)
    r_critical_95: float | None          # |r| threshold for ~95% significance
    best_r_ci: list[float] | None        # [low, high] 95% CI for best_r
