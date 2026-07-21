"""
GET /api/risk-corridors

For each known shipping corridor, aggregate severity across recent news
(last 7 days) with exponential recency decay, scaled to 0-100.
Returns corridor, score, level (green/amber/red), and top-3 headlines.

Real data source: macro_events_filtered.csv written by live_macro_pipeline.py
"""

import math
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Request

router = APIRouter()

# All corridors CORRIDOR_IMPACT_MAP can produce
ALL_CORRIDORS = [
    "hormuz",
    "red_sea",
    "suez",
    "cape_of_good_hope",
    "russia_route",
    "malacca",
    "india_domestic",
]

# Exponential decay half-life in hours — news from 24h ago counts ~70%,
# 48h ago ~50%, 7 days ago ~12% of full weight.
DECAY_HALF_LIFE_HOURS = 36.0

# Score ceiling — maximum raw score mapped to 100
# (one sev-5 article = 5 points; we cap at 100 so 20+ sev-5 articles = 100)
RAW_SCORE_CEILING = 25.0


def _load_events(csv_dir: Path, lookback_days: int = 7) -> pd.DataFrame:
    path = csv_dir / "macro_events_filtered.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str, low_memory=False)
    except Exception:
        return pd.DataFrame()

    required = {"date", "title", "source", "link", "corridor", "severity"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    # Parse date; drop unparseable rows
    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["_dt"])

    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    df = df[df["_dt"] >= cutoff].copy()
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").fillna(0)
    return df


def decay_weight(severity: float, hours_elapsed: float) -> float:
    """
    Calculate the decayed weight of an article's severity based on hours elapsed.
    Half-life of 36 hours.
    """
    decay_lambda = math.log(2) / DECAY_HALF_LIFE_HOURS
    return severity * math.exp(-decay_lambda * hours_elapsed)


def _decay_weight(row_dt: datetime, now: datetime) -> float:
    hours_old = (now - row_dt).total_seconds() / 3600.0
    return decay_weight(1.0, hours_old)


def _load_score_history(csv_dir: Path) -> dict:
    """Read corridor_score_history.csv and return per-corridor history rows."""
    history_path = csv_dir / "corridor_score_history.csv"
    if not history_path.exists():
        return {}
    try:
        df = pd.read_csv(history_path, dtype=str, low_memory=False)
    except Exception:
        return {}
    if df.empty or "corridor" not in df.columns or "score" not in df.columns:
        return {}
    try:
        df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
        df = df.dropna(subset=["timestamp", "corridor", "score"])
    except Exception:
        return {}
    history = {}
    for corridor in ALL_CORRIDORS:
        sub = df[df["corridor"] == corridor].copy()
        if sub.empty:
            continue
        sub = sub.sort_values("timestamp", ascending=True)
        history[corridor] = [
            {
                "timestamp": row["timestamp"].isoformat(),
                "score": float(row["score"]),
                "level": row.get("level", "green"),
            }
            for _, row in sub.iterrows()
        ]
    return history


def _trend_from_history(history_rows: list, current_score: float) -> str:
    """Return rising/falling/stable by comparing to the most-recent older snapshot."""
    if not history_rows or len(history_rows) < 2:
        return "stable"
    current_ts = pd.Timestamp(history_rows[-1]["timestamp"])
    prev_record = None
    for item in reversed(history_rows[:-1]):
        ts = pd.Timestamp(item["timestamp"])
        if current_ts - ts >= pd.Timedelta(hours=20):
            prev_record = item
            break
    if prev_record is None:
        prev_record = history_rows[-2]
    prev_score = float(prev_record.get("score", current_score))
    delta = current_score - prev_score
    if delta >= 2.0:
        return "rising"
    if delta <= -2.0:
        return "falling"
    return "stable"


def _level(score: float) -> str:
    if score >= 66:
        return "red"
    if score >= 33:
        return "amber"
    return "green"


@router.get("/risk-corridors")
def get_risk_corridors(request: Request):
    csv_dir: Path = request.app.state.csv_dir
    df = _load_events(csv_dir, lookback_days=7)
    history = _load_score_history(csv_dir)
    now = datetime.now(timezone.utc)

    results = []
    for corridor in ALL_CORRIDORS:
        sub = df[df["corridor"] == corridor].copy() if not df.empty else pd.DataFrame()

        if sub.empty:
            results.append({
                "corridor":         corridor,
                "score":            0.0,
                "level":            "green",
                "top_headlines":    [],
                "articles_in_window": 0,
            })
            continue

        # Weighted score: Σ(severity_i × decay_weight_i)
        raw = 0.0
        for _, row in sub.iterrows():
            w = _decay_weight(row["_dt"], now)
            raw += float(row["severity"]) * w

        score = round(min(raw / RAW_SCORE_CEILING * 100.0, 100.0), 1)

        # Top-3 headlines: highest severity first, then most recent
        top_df = sub.sort_values(
            ["severity", "_dt"], ascending=[False, False]
        ).head(3)
        headlines = [
            {
                "title":     r["title"],
                "source":    r.get("source", ""),
                "link":      r.get("link", ""),
                "timestamp": r["_dt"].isoformat(),
                "severity":  int(r["severity"]),
            }
            for _, r in top_df.iterrows()
        ]

        trend = _trend_from_history(history.get(corridor, []), score)
        results.append({
            "corridor":           corridor,
            "score":              score,
            "level":              _level(score),
            "trend":              trend,
            "top_headlines":      headlines,
            "articles_in_window": len(sub),
        })

    # Sort highest-risk first
    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "corridors":      results,
        "as_of":          now.isoformat(),
        "lookback_days":  7,
        "data_source":    "macro_events_filtered.csv (live_macro_pipeline.py)",
    }
