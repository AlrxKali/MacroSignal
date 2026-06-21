"""
Compare endpoints.

- /compare: one interest-rate series vs. one currency series.
- /differential: an interest-rate *differential* (base rate - quote rate) vs. a
  currency series. This is the theoretically correct comparison for an FX pair,
  since exchange rates respond to *relative* rates between the two economies.

Both align their series on a shared, forward-filled date axis (see app.align).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.align import align
from app.fred_client import FredError, fetch_observations
from app.models import (
    ComparePoint,
    CompareResponse,
    DifferentialPoint,
    DifferentialResponse,
)
from app.realrate import RealRateUnavailable, to_real
from app.series_catalog import SeriesKind, SeriesMeta, get_series

router = APIRouter(prefix="/api", tags=["compare"])


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


@router.get("/compare", response_model=CompareResponse)
async def compare(
    rate: str = Query(..., description="catalog key of an interest-rate series"),
    fx: str = Query(..., description="catalog key of a currency series"),
    real: bool = Query(default=False, description="subtract YoY CPI inflation (real rate)"),
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    rate_meta = _require(rate, (SeriesKind.RATE,), "rate")
    fx_meta = _require(fx, (SeriesKind.FX, SeriesKind.INDEX), "fx")

    rate_obs = await _apply_real(rate_meta, await _fetch(rate_meta, start, end), real)
    fx_obs = await _fetch(fx_meta, start, end)

    rows = align({"rate": rate_obs, "fx": fx_obs})
    points = [
        ComparePoint(date=r["date"], rate=r["rate"], fx=r["fx"])  # type: ignore[arg-type]
        for r in rows
    ]
    return CompareResponse(rate_meta=rate_meta, fx_meta=fx_meta, points=points)


@router.get("/differential", response_model=DifferentialResponse)
async def differential(
    base_rate: str = Query(..., description="catalog key of the base interest-rate (e.g. us-fed-funds)"),
    quote_rate: str = Query(..., description="catalog key of the quote interest-rate (e.g. ez-deposit-rate)"),
    fx: str = Query(..., description="catalog key of a currency series"),
    real: bool = Query(default=False, description="subtract YoY CPI inflation (real rates)"),
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    base_meta = _require(base_rate, (SeriesKind.RATE,), "base rate")
    quote_meta = _require(quote_rate, (SeriesKind.RATE,), "quote rate")
    fx_meta = _require(fx, (SeriesKind.FX, SeriesKind.INDEX), "fx")

    base_obs = await _apply_real(base_meta, await _fetch(base_meta, start, end), real)
    quote_obs = await _apply_real(quote_meta, await _fetch(quote_meta, start, end), real)
    fx_obs = await _fetch(fx_meta, start, end)

    rows = align({"base": base_obs, "quote": quote_obs, "fx": fx_obs})

    points: list[DifferentialPoint] = []
    for r in rows:
        base_val = r["base"]
        quote_val = r["quote"]
        diff = (
            base_val - quote_val  # type: ignore[operator]
            if base_val is not None and quote_val is not None
            else None
        )
        points.append(
            DifferentialPoint(
                date=r["date"],            # type: ignore[arg-type]
                base_rate=base_val,        # type: ignore[arg-type]
                quote_rate=quote_val,      # type: ignore[arg-type]
                differential=diff,
                fx=r["fx"],                # type: ignore[arg-type]
            )
        )

    return DifferentialResponse(
        base_rate_meta=base_meta,
        quote_rate_meta=quote_meta,
        fx_meta=fx_meta,
        points=points,
    )
