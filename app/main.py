"""MacroSignal API  interest rates vs. currency prices, sourced from FRED."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers import analysis, compare, events, series

app = FastAPI(
    title="MacroSignal API",
    version="0.1.0",
    description="Interest rates vs. currency prices over time, sourced from FRED.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.cors_origin_regex,
    allow_methods=["GET"],
    allow_headers=["*"],
)

app.include_router(series.router)
app.include_router(compare.router)
app.include_router(analysis.router)
app.include_router(events.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "service": "macrosignal"}
