# MacroSignal  API

FastAPI backend for charting **interest rates vs. currency prices** over time,
sourced from [FRED](https://fred.stlouisfed.org/).

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
```

Create a `.env` (see `.env.example`) with a free FRED key:

```
FRED_API_KEY=your_key_here
```

## Run

```bash
uvicorn app.main:app --reload --port 8078
```

Interactive docs at http://127.0.0.1:8078/docs

## Endpoints

| Method | Path | Purpose |
| ------ | ---- | ------- |
| GET | `/health` | Liveness check |
| GET | `/api/catalog?kind=rate\|fx\|index` | List available series |
| GET | `/api/series/{key}?start=&end=` | Raw observations for one series |
| GET | `/api/compare?rate={key}&fx={key}&start=&end=` | Two series aligned on a shared date axis (dual-axis ready) |

Dates are `YYYY-MM-DD`. Example:

```
/api/compare?rate=us-fed-funds&fx=eur-usd&start=2020-01-01
```

## Architecture

- **`app/series_catalog.py`**  single source of truth for every series. Adding a
  rate or currency = adding one entry here; nothing else changes.
- **`app/fred_client.py`**  async FRED calls, missing-value handling, errors.
- **`app/cache.py`**  on-disk cache (12h TTL); FRED updates at most daily.
- **`app/routers/`**  `series` (catalog/raw) and `compare` (date-aligned).

Mixed frequencies (e.g. monthly rate vs. daily FX) are handled in `/compare` by
building a unified date axis and forward-filling each series.
