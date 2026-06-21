"""
Lead/lag endpoint: do changes in a rate differential lead currency moves?

See app.analysis for the methodology. `quote_rate` is optional  omit it to
analyse changes in a single rate's level instead of a differential.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app import analysis
from app.fred_client import FredError, fetch_observations
from app.models import (
    LagAnalysisResponse,
    LagPoint,
    RegressionResponse,
    RollingCorrPoint,
    RollingCorrResponse,
    ScatterPoint,
)
from app.prep import trading_day_series
from app.realrate import RealRateUnavailable, to_real
from app.series_catalog import SeriesKind, SeriesMeta, get_series

router = APIRouter(prefix="/api", tags=["analysis"])


def _require(key: str, kinds: tuple[SeriesKind, ...], role: str) -> SeriesMeta:
    meta = get_series(key)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown {role} series '{key}'")
    if meta.kind not in kinds:
        wanted = " or ".join(k.value for k in kinds)
        raise HTTPException(
            status_code=400, detail=f"'{key}' is not a {wanted} series (needed for {role})"
        )
    return meta


async def _fetch(meta: SeriesMeta, start: str | None, end: str | None):
    try:
        return await fetch_observations(meta.fred_id, start=start, end=end)
    except FredError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _apply_real(meta: SeriesMeta, obs, real: bool):
    if not real:
        return obs
    try:
        return await to_real(meta.country, obs)
    except RealRateUnavailable:
        raise HTTPException(
            status_code=400,
            detail=f"Real rates unavailable for {meta.country}: FRED has no current CPI for it (supported: US, euro area).",
        )


@router.get("/lag-analysis", response_model=LagAnalysisResponse)
async def lag_analysis(
    base_rate: str = Query(..., description="catalog key of the base interest-rate"),
    fx: str = Query(..., description="catalog key of a currency series"),
    quote_rate: str | None = Query(default=None, description="optional: subtracted to form a differential"),
    window: int = Query(default=21, ge=1, le=252, description="trading days for change/return"),
    max_lag: int = Query(default=60, ge=1, le=180, description="±lag range, trading days"),
    real: bool = Query(default=False, description="subtract YoY CPI inflation (real rates)"),
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    base_meta = _require(base_rate, (SeriesKind.RATE,), "base rate")
    fx_meta = _require(fx, (SeriesKind.FX, SeriesKind.INDEX), "fx")
    quote_meta = _require(quote_rate, (SeriesKind.RATE,), "quote rate") if quote_rate else None

    base_obs = await _apply_real(base_meta, await _fetch(base_meta, start, end), real)
    fx_obs = await _fetch(fx_meta, start, end)
    quote_obs = (
        await _apply_real(quote_meta, await _fetch(quote_meta, start, end), real)
        if quote_meta
        else None
    )

    _, diff_series, fx_series = trading_day_series(base_obs, fx_obs, quote_obs)

    diff_changes = analysis.changes(diff_series, window)
    fx_returns = analysis.returns(fx_series, window)

    curve = analysis.lag_curve(diff_changes, fx_returns, max_lag)

    points = [LagPoint(lag=lag, r=r, n=n) for lag, r, n in curve]

    # Pick the lag with the largest |r| (the strongest lead/lag relationship).
    best_lag: int | None = None
    best_r: float | None = None
    for p in points:
        if p.r is not None and (best_r is None or abs(p.r) > abs(best_r)):
            best_r = p.r
            best_lag = p.lag

    # Significance, corrected for the heavy overlap of rolling windows.
    n_raw = next((p.n for p in points if p.lag == 0), 0)
    n_eff = analysis.effective_n(n_raw, window)
    r_crit = analysis.critical_r(n_eff)
    ci = analysis.fisher_ci(best_r, n_eff)

    return LagAnalysisResponse(
        base_rate_meta=base_meta,
        quote_rate_meta=quote_meta,
        fx_meta=fx_meta,
        window=window,
        points=points,
        best_lag=best_lag,
        best_r=best_r,
        n_raw=n_raw,
        n_effective=round(n_eff, 1),
        r_critical_95=r_crit,
        best_r_ci=list(ci) if ci else None,
    )


@router.get("/rolling-correlation", response_model=RollingCorrResponse)
async def rolling_correlation(
    base_rate: str = Query(..., description="catalog key of the base interest-rate"),
    fx: str = Query(..., description="catalog key of a currency series"),
    quote_rate: str | None = Query(default=None, description="optional: subtracted to form a differential"),
    window: int = Query(default=21, ge=1, le=252, description="change/return period, trading days"),
    corr_window: int = Query(default=252, ge=20, le=1260, description="trailing correlation length, trading days"),
    real: bool = Query(default=False, description="subtract YoY CPI inflation (real rates)"),
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    base_meta = _require(base_rate, (SeriesKind.RATE,), "base rate")
    fx_meta = _require(fx, (SeriesKind.FX, SeriesKind.INDEX), "fx")
    quote_meta = _require(quote_rate, (SeriesKind.RATE,), "quote rate") if quote_rate else None

    base_obs = await _apply_real(base_meta, await _fetch(base_meta, start, end), real)
    fx_obs = await _fetch(fx_meta, start, end)
    quote_obs = (
        await _apply_real(quote_meta, await _fetch(quote_meta, start, end), real)
        if quote_meta
        else None
    )

    dates, diff_series, fx_series = trading_day_series(base_obs, fx_obs, quote_obs)
    diff_changes = analysis.changes(diff_series, window)
    fx_returns = analysis.returns(fx_series, window)

    curve = analysis.rolling_corr(diff_changes, fx_returns, corr_window)
    points = [RollingCorrPoint(date=dates[i], r=r, n=n) for i, r, n in curve]

    overall_r, _ = analysis.corr_at_lag(diff_changes, fx_returns, 0)

    return RollingCorrResponse(
        base_rate_meta=base_meta,
        quote_rate_meta=quote_meta,
        fx_meta=fx_meta,
        window=window,
        corr_window=corr_window,
        points=points,
        overall_r=overall_r,
    )


@router.get("/regression", response_model=RegressionResponse)
async def regression(
    base_rate: str = Query(..., description="catalog key of the base interest-rate"),
    fx: str = Query(..., description="catalog key of a currency series"),
    quote_rate: str | None = Query(default=None, description="optional: subtracted to form a differential"),
    window: int = Query(default=21, ge=1, le=252, description="trading days for change/return"),
    lag: int = Query(default=0, ge=-180, le=180, description="FX measured this many days after the rate change"),
    real: bool = Query(default=False, description="subtract YoY CPI inflation (real rates)"),
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    base_meta = _require(base_rate, (SeriesKind.RATE,), "base rate")
    fx_meta = _require(fx, (SeriesKind.FX, SeriesKind.INDEX), "fx")
    quote_meta = _require(quote_rate, (SeriesKind.RATE,), "quote rate") if quote_rate else None

    base_obs = await _apply_real(base_meta, await _fetch(base_meta, start, end), real)
    fx_obs = await _fetch(fx_meta, start, end)
    quote_obs = (
        await _apply_real(quote_meta, await _fetch(quote_meta, start, end), real)
        if quote_meta
        else None
    )

    dates, diff_series, fx_series = trading_day_series(base_obs, fx_obs, quote_obs)
    diff_changes = analysis.changes(diff_series, window)
    fx_returns = analysis.returns(fx_series, window)

    xs, ys, idx = analysis.paired_at_lag(diff_changes, fx_returns, lag)
    points = [ScatterPoint(date=dates[i], x=x, y=y) for x, y, i in zip(xs, ys, idx)]

    fit = analysis.ols(xs, ys)
    r = analysis._pearson(xs, ys)
    n = len(xs)
    n_eff = analysis.effective_n(n, window)
    r_crit = analysis.critical_r(n_eff)
    significant = r is not None and r_crit is not None and abs(r) > r_crit

    return RegressionResponse(
        base_rate_meta=base_meta,
        quote_rate_meta=quote_meta,
        fx_meta=fx_meta,
        window=window,
        lag=lag,
        points=points,
        slope=fit[0] if fit else None,
        intercept=fit[1] if fit else None,
        r=r,
        r2=(r * r) if r is not None else None,
        n=n,
        n_effective=round(n_eff, 1),
        r_critical_95=r_crit,
        significant=significant,
    )
