import math
from datetime import datetime, timezone, timedelta, date as date_cls
import pandas as pd
from fastapi import APIRouter, Request

from api.db import query_df, query_rows

router = APIRouter()

ALL_CORRIDORS = [
    "hormuz",
    "red_sea",
    "suez",
    "cape_of_good_hope",
    "russia_route",
    "malacca",
    "india_domestic",
]

DECAY_HALF_LIFE_HOURS = 36.0
RAW_SCORE_CEILING = 25.0


def _load_events(lookback_days: int = 7) -> pd.DataFrame:
    cutoff = date_cls.today() - timedelta(days=lookback_days)
    df = query_df("""
        SELECT date, title, source, link, corridor, severity
        FROM macro_events
        WHERE date >= %s
    """, params=(cutoff,))
    if df.empty:
        return pd.DataFrame()

    required = {"date", "title", "source", "link", "corridor", "severity"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["_dt"])
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").fillna(0)
    return df


def decay_weight(severity: float, hours_elapsed: float) -> float:
    decay_lambda = math.log(2) / DECAY_HALF_LIFE_HOURS
    return severity * math.exp(-decay_lambda * hours_elapsed)


def _decay_weight(row_dt: datetime, now: datetime) -> float:
    hours_old = (now - row_dt).total_seconds() / 3600.0
    return decay_weight(1.0, hours_old)


def _load_score_history() -> dict:
    rows = query_rows("""
        SELECT corridor, score, level, ts as timestamp
        FROM corridor_score_history
        ORDER BY ts ASC
    """)
    if not rows:
        return {}
    df = pd.DataFrame(rows)
    if df.empty:
        return {}
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce", utc=True)
    df = df.dropna(subset=["timestamp", "corridor", "score"])

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
        # Use earliest baseline record in history instead of 5-minute-ago record
        prev_record = history_rows[0]
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
    df = _load_events(lookback_days=7)
    history = _load_score_history()
    now = datetime.now(timezone.utc)

    results = []
    for corridor in ALL_CORRIDORS:
        sub = df[df["corridor"] == corridor].copy() if not df.empty else pd.DataFrame()

        if sub.empty:
            results.append({
                "corridor":           corridor,
                "score":              0.0,
                "level":              "green",
                "trend":              "stable",
                "top_headlines":      [],
                "articles_in_window": 0,
            })
            continue

        raw = 0.0
        for _, row in sub.iterrows():
            w = _decay_weight(row["_dt"], now)
            raw += float(row["severity"]) * w

        score = round(min(raw / RAW_SCORE_CEILING * 100.0, 100.0), 1)

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

    results.sort(key=lambda x: x["score"], reverse=True)

    return {
        "corridors":      results,
        "as_of":          now.isoformat(),
        "lookback_days":  7,
        "data_source":    "Neon DB — macro_events & corridor_score_history",
    }
