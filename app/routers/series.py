"""Catalog + raw single-series endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.fred_client import FredError, fetch_observations
from app.models import RecessionInterval, RecessionsResponse, SeriesData
from app.series_catalog import SeriesKind, get_series, list_series

router = APIRouter(prefix="/api", tags=["series"])

# NBER recession indicator (daily, 1 = recession). Used for chart shading.
_RECESSION_FRED_ID = "USRECD"


@router.get("/catalog")
def catalog(kind: SeriesKind | None = Query(default=None)):
    """List every available series (optionally filtered by kind)."""
    return list_series(kind)


@router.get("/recessions", response_model=RecessionsResponse)
async def recessions(
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    """NBER recession periods as [start, end] intervals, for chart shading."""
    try:
        obs = await fetch_observations(_RECESSION_FRED_ID, start=start, end=end)
    except FredError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    intervals: list[RecessionInterval] = []
    run_start: str | None = None
    last_one: str | None = None
    for o in obs:
        if o.value == 1:
            if run_start is None:
                run_start = o.date
            last_one = o.date
        elif run_start is not None:
            intervals.append(RecessionInterval(start=run_start, end=last_one))  # type: ignore[arg-type]
            run_start = None
    if run_start is not None:
        intervals.append(RecessionInterval(start=run_start, end=last_one))  # type: ignore[arg-type]

    return RecessionsResponse(intervals=intervals)


@router.get("/series/{key}", response_model=SeriesData)
async def series(
    key: str,
    start: str | None = Query(default=None, description="YYYY-MM-DD"),
    end: str | None = Query(default=None, description="YYYY-MM-DD"),
):
    meta = get_series(key)
    if meta is None:
        raise HTTPException(status_code=404, detail=f"Unknown series '{key}'")
    try:
        observations = await fetch_observations(meta.fred_id, start=start, end=end)
    except FredError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return SeriesData(meta=meta, observations=observations)
