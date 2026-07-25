import os
import time
from datetime import datetime, timezone, timedelta
import pandas as pd
from pipeline.config import _COMMODITY_TICKERS


# Alternative tickers to try if the primary rolls/expires (futures contracts)
_TICKER_FALLBACKS = {
    "BZ=F": ["BZ=F", "BRNT=F"],  # ICE Brent front-month, ICE Brent continuous
}


def _fetch_with_fallback(ticker, start_dt, lookback_days):
    """
    Fetch yfinance history for `ticker`.
    Strategy:
      1. Try start/end date range (preferred — gives exact window)
      2. If empty (e.g. futures rolled/expired), try period= which always works
      3. If still empty, try fallback tickers from _TICKER_FALLBACKS
    Returns (hist DataFrame, actual_ticker_used)
    """
    try:
        import yfinance as yf
    except ImportError:
        return pd.DataFrame(), ticker

    end_dt = datetime.now(timezone.utc).date()
    candidates = _TICKER_FALLBACKS.get(ticker, [ticker])

    for candidate in candidates:
        try:
            tkr = yf.Ticker(candidate)

            # Attempt 1: date range
            hist = tkr.history(start=str(start_dt), end=str(end_dt), interval="1d", auto_adjust=True)
            if not hist.empty:
                return hist, candidate

            # Attempt 2: period-based fallback (handles rolled/expired futures)
            period_str = f"{max(lookback_days, 7)}d"
            hist = tkr.history(period=period_str, interval="1d", auto_adjust=True)
            if not hist.empty:
                # Normalise index to tz-naive for date comparison
                idx = hist.index
                if hasattr(idx, "tz") and idx.tz is not None:
                    idx = idx.tz_localize(None)
                hist.index = idx
                hist = hist[pd.to_datetime(hist.index).date >= start_dt]
                if not hist.empty:
                    print(f"  [CommodityPrices] {candidate}: date-range empty — used period={period_str} fallback")
                    return hist, candidate
        except Exception as e:
            print(f"  [CommodityPrices] {candidate} attempt failed: {e}")
            continue

    return pd.DataFrame(), ticker


def fetch_commodity_prices(output_dir, lookback_days=7, db_conn=None):
    out_path = os.path.join(output_dir, "commodity_prices.csv")

    try:
        import yfinance as yf  # noqa: F401
    except ImportError:
        print("  [CommodityPrices] yfinance not installed — skipping. pip install yfinance")
        return 0, 0

    print(f"\n[CommodityPrices] Fetching {lookback_days}d of daily prices for {list(_COMMODITY_TICKERS.keys())} ...")

    existing_pairs: set = set()
    if db_conn:
        try:
            with db_conn.cursor() as cur:
                cur.execute("SELECT date::text, ticker FROM commodity_prices")
                existing_pairs = {(str(r[0])[:10], r[1]) for r in cur.fetchall()}
        except Exception:
            pass
    elif os.path.exists(out_path):
        try:
            df_ex = pd.read_csv(out_path, dtype=str)
            if {"date", "ticker"}.issubset(df_ex.columns):
                existing_pairs = set(zip(df_ex["date"].str.strip(), df_ex["ticker"].str.strip()))
        except Exception:
            pass

    start_dt = (datetime.now(timezone.utc).date() - timedelta(days=lookback_days))

    all_rows = []
    for ticker, label in _COMMODITY_TICKERS.items():
        try:
            hist, used_ticker = _fetch_with_fallback(ticker, start_dt, lookback_days)

            if hist.empty:
                print(f"  [CommodityPrices] {ticker}: no data from any source — skipping")
                continue

            if used_ticker != ticker:
                print(f"  [CommodityPrices] {ticker} rolled/unavailable — data sourced from {used_ticker}")

            rows_added = 0
            for row_date, row in hist.iterrows():
                date_str = str(row_date)[:10]
                if (date_str, ticker) in existing_pairs:
                    continue
                try:
                    all_rows.append({
                        "date":       date_str,
                        "ticker":     ticker,        # always store as the canonical ticker
                        "label":      label,
                        "open":       round(float(row.get("Open",  float("nan"))), 4),
                        "high":       round(float(row.get("High",  float("nan"))), 4),
                        "low":        round(float(row.get("Low",   float("nan"))), 4),
                        "close":      round(float(row.get("Close", float("nan"))), 4),
                        "volume":     int(row.get("Volume", 0) or 0),
                        "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    })
                    rows_added += 1
                except (ValueError, TypeError):
                    continue

            print(f"  [CommodityPrices] {ticker} ({label}): {len(hist)} rows fetched, {rows_added} new")
            time.sleep(0.3)

        except Exception as e:
            print(f"  [CommodityPrices] {ticker} failed: {e}")
            continue

    if not all_rows:
        print("  [CommodityPrices] No new data — already up to date")
        return 0, 0

    if db_conn:
        from pipeline.db import upsert_commodity_prices
        written = upsert_commodity_prices(db_conn, all_rows)
        print(f"  [CommodityPrices] Wrote {written} new rows to Neon")

    df_new = pd.DataFrame(all_rows)
    write_header = not os.path.exists(out_path)
    df_new.to_csv(out_path, mode="a", header=write_header, index=False, encoding="utf-8-sig")
    print(f"  [CommodityPrices] Wrote {len(df_new)} new rows -> {out_path}")
    return len(df_new), len(df_new)
