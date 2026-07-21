from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, Request, HTTPException

from api.db import query_df

router = APIRouter()

_VALID_TICKERS = {"BZ=F", "CL=F", "INR=X"}


def _safe_float(v) -> Optional[float]:
    try:
        f = float(v)
        return None if (f != f) else round(f, 4)
    except Exception:
        return None


def _safe_int(v) -> Optional[int]:
    try:
        return int(float(v))
    except Exception:
        return None


@router.get("/commodity-prices")
def get_commodity_prices(
    request: Request,
    ticker: Optional[str] = Query(None, description="Ticker: BZ=F | CL=F | INR=X. Omit for all."),
    days: int = Query(30, description="Lookback window in days", le=365),
):
    cutoff = date_cls.today() - timedelta(days=days)

    if ticker:
        t = ticker.upper().strip()
        if t not in _VALID_TICKERS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid ticker '{ticker}'. Valid: {sorted(_VALID_TICKERS)}",
            )
        df = query_df("""
            SELECT date, ticker, label, open, high, low, close, volume
            FROM commodity_prices
            WHERE date >= %s AND UPPER(TRIM(ticker)) = %s
            ORDER BY date ASC
        """, params=(cutoff, t))
    else:
        df = query_df("""
            SELECT date, ticker, label, open, high, low, close, volume
            FROM commodity_prices
            WHERE date >= %s
            ORDER BY date ASC
        """, params=(cutoff,))

    if df.empty:
        return {
            "series":      [],
            "data_source": "Neon DB — commodity_prices table",
        }

    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["_dt"])

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
        "data_source": "Neon DB — commodity_prices table",
    }
