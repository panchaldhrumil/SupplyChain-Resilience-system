import os
import time
from datetime import datetime, timezone, timedelta
import pandas as pd
from pipeline.config import _COMMODITY_TICKERS

def fetch_commodity_prices(output_dir, lookback_days=7):
    """
    Pull *lookback_days* of daily OHLCV data for Brent (BZ=F), WTI (CL=F),
    and USD/INR (INR=X) from Yahoo Finance via yfinance (no API key needed).

    Writes to commodity_prices.csv in *output_dir*, appending only rows
    whose (date, ticker) pair is not already present — so re-running is
    idempotent and the file grows incrementally.

    Returns (new_rows_written, total_rows_attempted). Never raises.
    """
    out_path = os.path.join(output_dir, "commodity_prices.csv")

    try:
        import yfinance as yf
    except ImportError:
        print("  [CommodityPrices] yfinance not installed — skipping. "
              "Run: pip install yfinance")
        return 0, 0

    print(f"\n[CommodityPrices] Fetching {lookback_days}d of daily prices "
          f"for {list(_COMMODITY_TICKERS.keys())} ...")

    # Load existing (date, ticker) pairs to avoid duplicates
    existing_pairs: set = set()
    if os.path.exists(out_path):
        try:
            df_ex = pd.read_csv(out_path, dtype=str)
            if {"date", "ticker"}.issubset(df_ex.columns):
                existing_pairs = set(
                    zip(df_ex["date"].str.strip(), df_ex["ticker"].str.strip())
                )
        except Exception as e:
            print(f"  [CommodityPrices] Could not read existing file ({e}); "
                  "treating all as new.")

    end_dt   = datetime.now(timezone.utc).date()
    start_dt = end_dt - timedelta(days=lookback_days)

    all_rows = []
    for ticker, label in _COMMODITY_TICKERS.items():
        try:
            tkr  = yf.Ticker(ticker)
            hist = tkr.history(start=str(start_dt), end=str(end_dt), interval="1d")
            if hist.empty:
                print(f"  [CommodityPrices] {ticker}: no data returned")
                continue

            for row_date, row in hist.iterrows():
                date_str = str(row_date)[:10]   # "YYYY-MM-DD"
                if (date_str, ticker) in existing_pairs:
                    continue
                all_rows.append({
                    "date":        date_str,
                    "ticker":      ticker,
                    "label":       label,
                    "open":        round(float(row.get("Open",  float("nan"))), 4),
                    "high":        round(float(row.get("High",  float("nan"))), 4),
                    "low":         round(float(row.get("Low",   float("nan"))), 4),
                    "close":       round(float(row.get("Close", float("nan"))), 4),
                    "volume":      int(row.get("Volume", 0) or 0),
                    "fetched_at":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                })
            print(f"  [CommodityPrices] {ticker} ({label}): "
                  f"{len(hist)} rows fetched")
            time.sleep(0.3)

        except Exception as e:
            print(f"  [CommodityPrices] {ticker} failed: {e}")
            continue

    if not all_rows:
        print(f"  [CommodityPrices] No new data -> {out_path} is already up to date")
        return 0, 0

    df_new = pd.DataFrame(all_rows)
    write_header = not os.path.exists(out_path)
    df_new.to_csv(out_path, mode="a", header=write_header, index=False,
                  encoding="utf-8-sig")
    print(f"  [CommodityPrices] Wrote {len(df_new)} new rows -> {out_path}")
    return len(df_new), len(df_new)
