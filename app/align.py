"""
Shared time-series alignment.

Macro series arrive at different frequencies (daily FX, monthly policy rates) and
with gaps (weekends, holidays). To overlay them we build one sorted date axis
across all series and forward-fill each: every date carries the last known value.
This is the standard way to line up mixed-frequency macro data.
"""
from __future__ import annotations

from app.models import Observation


def align(series: dict[str, list[Observation]]) -> list[dict[str, object]]:
    """Align named series onto a shared, forward-filled date axis.

    Returns a list of row dicts: ``{"date": d, name1: value-or-None, ...}``.
    Leading dates before *any* series has started are dropped.
    """
    maps: dict[str, dict[str, float]] = {
        name: {o.date: o.value for o in obs if o.value is not None}
        for name, obs in series.items()
    }

    all_dates: set[str] = set()
    for m in maps.values():
        all_dates |= m.keys()

    last: dict[str, float | None] = {name: None for name in maps}
    rows: list[dict[str, object]] = []
    for d in sorted(all_dates):
        for name, m in maps.items():
            if d in m:
                last[name] = m[d]
        if all(v is None for v in last.values()):
            continue
        row: dict[str, object] = {"date": d}
        row.update(last)
        rows.append(row)
    return rows
