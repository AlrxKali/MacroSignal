"""
Lead/lag analysis between an interest-rate (differential) and a currency.

Why changes, not levels: both a policy-rate differential and an FX rate are
strongly trending / non-stationary, so correlating their *levels* is misleading
(spurious-regression territory). The economically meaningful question is whether
*changes* in the rate differential line up with subsequent FX *returns*.

Method:
  1. Build daily business-day series (on the currency's trading dates).
  2. Over a rolling `window` (in trading days), compute:
       - the change in the differential (percentage points)
       - the percentage return of the currency
  3. For each lag L, correlate diff-change at time t with fx-return at t+L.
     L > 0 means the FX move comes *after* the rate move (rate leads currency).
"""
from __future__ import annotations

import math


def changes(series: list[float | None], window: int) -> list[float | None]:
    """Absolute change over `window` steps: series[t] - series[t-window]."""
    out: list[float | None] = [None] * len(series)
    for i in range(window, len(series)):
        a, b = series[i - window], series[i]
        if a is not None and b is not None:
            out[i] = b - a
    return out


def returns(series: list[float | None], window: int) -> list[float | None]:
    """Percent return over `window` steps: (series[t]/series[t-window] - 1)*100."""
    out: list[float | None] = [None] * len(series)
    for i in range(window, len(series)):
        a, b = series[i - window], series[i]
        if a not in (None, 0) and b is not None:
            out[i] = (b / a - 1.0) * 100.0  # type: ignore[operator]
    return out


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    cov = vx = vy = 0.0
    for x, y in zip(xs, ys):
        dx, dy = x - mx, y - my
        cov += dx * dy
        vx += dx * dx
        vy += dy * dy
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def ols(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    """Ordinary least-squares fit y = slope*x + intercept. None if degenerate."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    intercept = my - slope * mx
    return slope, intercept


def paired_at_lag(
    x: list[float | None], y: list[float | None], lag: int
) -> tuple[list[float], list[float], list[int]]:
    """Return (xs, ys, source_indices) for x[t] paired with y[t+lag]."""
    n = len(x)
    xs: list[float] = []
    ys: list[float] = []
    idx: list[int] = []
    for t in range(n):
        u = t + lag
        if 0 <= u < n:
            xt, yu = x[t], y[u]
            if xt is not None and yu is not None:
                xs.append(xt)
                ys.append(yu)
                idx.append(t)
    return xs, ys, idx


def corr_at_lag(x: list[float | None], y: list[float | None], lag: int) -> tuple[float | None, int]:
    """Correlate x[t] with y[t+lag] over all valid, paired points."""
    xs, ys, _ = paired_at_lag(x, y, lag)
    return _pearson(xs, ys), len(xs)


def rolling_corr(
    x: list[float | None], y: list[float | None], corr_window: int, min_points: int = 20
) -> list[tuple[int, float | None, int]]:
    """Trailing correlation of x vs y: at each index, correlate the last
    `corr_window` paired points. Returns (index, r, n) per position; r is None
    until at least `min_points` paired observations are available.
    """
    n = len(x)
    out: list[tuple[int, float | None, int]] = []
    for i in range(n):
        lo = max(0, i - corr_window + 1)
        xs: list[float] = []
        ys: list[float] = []
        for t in range(lo, i + 1):
            xt, yt = x[t], y[t]
            if xt is not None and yt is not None:
                xs.append(xt)
                ys.append(yt)
        r = _pearson(xs, ys) if len(xs) >= min_points else None
        out.append((i, r, len(xs)))
    return out


def lag_curve(
    x: list[float | None], y: list[float | None], max_lag: int
) -> list[tuple[int, float | None, int]]:
    """Correlation of x vs y across lags in [-max_lag, +max_lag]."""
    out: list[tuple[int, float | None, int]] = []
    for lag in range(-max_lag, max_lag + 1):
        r, n = corr_at_lag(x, y, lag)
        out.append((lag, r, n))
    return out


# --- Significance under overlapping windows ---------------------------------
# Rolling `window`-day changes/returns overlap heavily, so adjacent observations
# are highly autocorrelated. The naive sample size N badly overstates the
# information content. A standard, conservative correction is to count only the
# non-overlapping windows: N_eff ~= N / window. We then judge significance with
# Fisher's z-transform using N_eff rather than N.

def effective_n(n_raw: int, window: int) -> float:
    """Independent-equivalent sample size for overlapping `window` observations."""
    return n_raw / window if window > 0 else float(n_raw)


def fisher_ci(r: float | None, n_eff: float, z: float = 1.96) -> tuple[float, float] | None:
    """95%-style CI for a correlation via Fisher z, using the effective N."""
    if r is None or n_eff <= 3:
        return None
    r_clamped = max(min(r, 0.999999), -0.999999)
    zr = math.atanh(r_clamped)
    se = 1.0 / math.sqrt(n_eff - 3.0)
    return math.tanh(zr - z * se), math.tanh(zr + z * se)


def critical_r(n_eff: float, z: float = 1.96) -> float | None:
    """The |r| threshold beyond which r differs from 0 at ~95%, given N_eff."""
    if n_eff <= 3:
        return None
    se = 1.0 / math.sqrt(n_eff - 3.0)
    return math.tanh(z * se)
