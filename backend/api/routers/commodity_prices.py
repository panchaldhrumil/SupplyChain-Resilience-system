"""
GET /api/commodity-prices?ticker=BZ=F&days=30

Returns OHLCV time series for Brent crude (BZ=F), WTI crude (CL=F),
and USD/INR (INR=X) from commodity_prices.csv written by fetch_commodity_prices().

Real data source: commodity_prices.csv (fetched via yfinance from Yahoo Finance)
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter()

_VALID_TICKERS = {"BZ=F", "CL=F", "INR=X"}


@router.get("/commodity-prices")
def get_commodity_prices(
    request: Request,
    ticker:  Optional[str] = Query(None, description="Ticker: BZ=F | CL=F | INR=X. Omit for all."),
    days:    int            = Query(30,   description="Lookback window in days", le=365),
):
    csv_dir: Path = request.app.state.csv_dir
    path = csv_dir / "commodity_prices.csv"

    if not path.exists():
        return {
            "series":      [],
            "data_source": "commodity_prices.csv not found — run live_macro_pipeline.py first",
        }

    try:
        df = pd.read_csv(path, dtype=str, low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV read error: {e}")

    if ticker:
        t = ticker.upper().strip()
        if t not in _VALID_TICKERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid ticker '{ticker}'. Valid: {sorted(_VALID_TICKERS)}",
            )
        df = df[df["ticker"].str.upper().str.strip() == t]

    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["_dt"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    df = df[df["_dt"] >= cutoff]
    df = df.sort_values("_dt", ascending=True)

    # Return grouped by ticker
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    series = []
    for tkr, grp in df.groupby("ticker"):
        label = grp["label"].iloc[0] if "label" in grp.columns else tkr
        points = []
        for _, row in grp.iterrows():
            points.append({
                "date":   row["_dt"].strftime("%Y-%m-%d"),
                "open":   _safe_float(row.get("open")),
                "high":   _safe_float(row.get("high")),
                "low":    _safe_float(row.get("low")),
                "close":  _safe_float(row.get("close")),
                "volume": _safe_int(row.get("volume")),
            })
        series.append({
            "ticker": tkr,
            "label":  label,
            "points": points,
        })

    return {
        "series":      series,
        "days":        days,
        "as_of":       datetime.now(timezone.utc).isoformat(),
        "data_source": "commodity_prices.csv (yfinance / Yahoo Finance via live_macro_pipeline.py)",
    }


def _safe_float(v) -> Optional[float]:
    try:
        f = float(v)
        return None if (f != f) else round(f, 4)  # NaN check
    except Exception:
        return None


def _safe_int(v) -> Optional[int]:
    try:
        return int(float(v))
    except Exception:
        return None
