"""
The series catalog: the single source of truth for every data series we expose.

To support a new interest rate or currency pair, add an entry here  no other
code needs to change. The routers, client, and frontend all read from this.

A note on FRED's FX convention (it is NOT consistent across series):
  - Some series quote "US Dollars to One Foreign Unit"  (e.g. DEXUSEU = USD per EUR)
  - Others quote "Foreign Units to One US Dollar"       (e.g. DEXJPUS = JPY per USD)
`quote` records which, so the UI can label axes correctly and we can later
normalize directions when computing pairs.
"""
from __future__ import annotations

from enum import Enum

from pydantic import BaseModel


class SeriesKind(str, Enum):
    RATE = "rate"  # interest rate (percent)
    FX = "fx"      # exchange rate / currency price
    INDEX = "index"  # e.g. a broad dollar index


class FxQuote(str, Enum):
    USD_PER_FOREIGN = "usd_per_foreign"  # value goes UP when USD weakens
    FOREIGN_PER_USD = "foreign_per_usd"  # value goes UP when USD strengthens
    NA = "na"


class SeriesMeta(BaseModel):
    key: str               # our friendly slug, used in URLs
    fred_id: str           # the underlying FRED series id
    name: str              # human-readable label
    kind: SeriesKind
    country: str           # ISO-ish tag: "US", "EZ" (euro area), "JP", "GB"...
    units: str             # "Percent", "USD per EUR", ...
    frequency: str         # "daily" | "monthly"
    quote: FxQuote = FxQuote.NA


# --- The catalog -----------------------------------------------------------
# MVP focus: US interest rates + USD currency. Extra entries are pre-wired so
# expansion to EUR/USD differentials is just flipping them on in the UI.
_CATALOG: list[SeriesMeta] = [
    # Interest rates  United States
    SeriesMeta(
        key="us-fed-funds",
        fred_id="DFF",
        name="US Federal Funds Rate (daily)",
        kind=SeriesKind.RATE,
        country="US",
        units="Percent",
        frequency="daily",
    ),
    SeriesMeta(
        key="us-fed-funds-monthly",
        fred_id="FEDFUNDS",
        name="US Federal Funds Rate (monthly avg)",
        kind=SeriesKind.RATE,
        country="US",
        units="Percent",
        frequency="monthly",
    ),
    SeriesMeta(
        key="us-3m",
        fred_id="DGS3MO",
        name="US 3-Month Treasury Yield",
        kind=SeriesKind.RATE,
        country="US",
        units="Percent",
        frequency="daily",
    ),
    SeriesMeta(
        key="us-2y",
        fred_id="DGS2",
        name="US 2-Year Treasury Yield",
        kind=SeriesKind.RATE,
        country="US",
        units="Percent",
        frequency="daily",
    ),
    SeriesMeta(
        key="us-10y",
        fred_id="DGS10",
        name="US 10-Year Treasury Yield",
        kind=SeriesKind.RATE,
        country="US",
        units="Percent",
        frequency="daily",
    ),
    # Currency  USD pairs
    SeriesMeta(
        key="eur-usd",
        fred_id="DEXUSEU",
        name="EUR/USD (US Dollars per Euro)",
        kind=SeriesKind.FX,
        country="EZ",
        units="USD per EUR",
        frequency="daily",
        quote=FxQuote.USD_PER_FOREIGN,
    ),
    SeriesMeta(
        key="usd-jpy",
        fred_id="DEXJPUS",
        name="USD/JPY (Japanese Yen per US Dollar)",
        kind=SeriesKind.FX,
        country="JP",
        units="JPY per USD",
        frequency="daily",
        quote=FxQuote.FOREIGN_PER_USD,
    ),
    SeriesMeta(
        key="gbp-usd",
        fred_id="DEXUSUK",
        name="GBP/USD (US Dollars per British Pound)",
        kind=SeriesKind.FX,
        country="GB",
        units="USD per GBP",
        frequency="daily",
        quote=FxQuote.USD_PER_FOREIGN,
    ),
    SeriesMeta(
        key="usd-index",
        fred_id="DTWEXBGS",
        name="Nominal Broad US Dollar Index",
        kind=SeriesKind.INDEX,
        country="US",
        units="Index",
        frequency="daily",
        quote=FxQuote.FOREIGN_PER_USD,  # rises as USD strengthens
    ),
    # Euro-area rates. The deposit rate is the policy (step-function) rate; the
    # 3M interbank and 10Y are market-based (move continuously) but monthly on
    # FRED. For a daily, market-based EUR/USD differential, pair US 2Y vs the
    # deposit rate (US side supplies the daily variation).
    SeriesMeta(
        key="ez-deposit-rate",
        fred_id="ECBDFR",
        name="ECB Deposit Facility Rate (policy)",
        kind=SeriesKind.RATE,
        country="EZ",
        units="Percent",
        frequency="daily",
    ),
    SeriesMeta(
        key="ez-3m",
        fred_id="IR3TIB01EZM156N",
        name="Euro Area 3-Month Interbank Rate (market)",
        kind=SeriesKind.RATE,
        country="EZ",
        units="Percent",
        frequency="monthly",
    ),
    SeriesMeta(
        key="ez-10y",
        fred_id="IRLTLT01EZM156N",
        name="Euro Area 10-Year Government Yield (market)",
        kind=SeriesKind.RATE,
        country="EZ",
        units="Percent",
        frequency="monthly",
    ),
    # United Kingdom (for GBP/USD). SONIA tracks the BoE Bank Rate and is daily;
    # the official BoE policy-rate series on FRED is stale (ends 2017).
    SeriesMeta(
        key="gb-sonia",
        fred_id="IUDSOIA",
        name="UK SONIA Overnight Rate (policy proxy)",
        kind=SeriesKind.RATE,
        country="GB",
        units="Percent",
        frequency="daily",
    ),
    SeriesMeta(
        key="gb-3m",
        fred_id="IR3TIB01GBM156N",
        name="UK 3-Month Interbank Rate (market)",
        kind=SeriesKind.RATE,
        country="GB",
        units="Percent",
        frequency="monthly",
    ),
    SeriesMeta(
        key="gb-10y",
        fred_id="IRLTLT01GBM156N",
        name="UK 10-Year Government Yield (market)",
        kind=SeriesKind.RATE,
        country="GB",
        units="Percent",
        frequency="monthly",
    ),
    # Japan (for USD/JPY). Market-based short and long rates (monthly on FRED).
    SeriesMeta(
        key="jp-3m",
        fred_id="IR3TIB01JPM156N",
        name="Japan 3-Month Interbank Rate (market)",
        kind=SeriesKind.RATE,
        country="JP",
        units="Percent",
        frequency="monthly",
    ),
    SeriesMeta(
        key="jp-10y",
        fred_id="IRLTLT01JPM156N",
        name="Japan 10-Year Government Yield (market)",
        kind=SeriesKind.RATE,
        country="JP",
        units="Percent",
        frequency="monthly",
    ),
]

_BY_KEY: dict[str, SeriesMeta] = {s.key: s for s in _CATALOG}


def list_series(kind: SeriesKind | None = None) -> list[SeriesMeta]:
    if kind is None:
        return list(_CATALOG)
    return [s for s in _CATALOG if s.kind == kind]


def get_series(key: str) -> SeriesMeta | None:
    return _BY_KEY.get(key)
