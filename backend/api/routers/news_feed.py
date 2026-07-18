"""
GET /api/news-feed?category=&corridor=&limit=20

Recent enriched articles for the News Feed panel.
Sorted by date descending. Supports filtering by category and/or corridor.

Also exposes LLM signal validation columns (llm_severity, llm_confidence,
review_flagged) when they were populated by live_macro_pipeline.py --llm-classify.
Includes llm_stats summary in the response for the "Signal Validation" UI stat.

Real data source: macro_events_filtered.csv written by live_macro_pipeline.py
"""

import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query, Request

router = APIRouter()

_COLS = [
    "date", "title", "source", "link", "category",
    "buffer_layer", "corridor", "severity",
    "key_takeaway", "fetch_status", "extracted_numbers",
    # LLM validation columns — present only when --llm-classify was used
    "llm_severity", "llm_confidence", "is_genuine_disruption",
    "llm_corridor", "llm_justification", "review_flagged", "llm_status",
]


def _load_feed(csv_dir: Path) -> pd.DataFrame:
    path = csv_dir / "macro_events_filtered.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str, low_memory=False)
    except Exception:
        return pd.DataFrame()

    # Keep only columns we need (tolerate missing optional ones)
    present = [c for c in _COLS if c in df.columns]
    df = df[present].copy()

    df["_dt"] = pd.to_datetime(df.get("date", pd.Series(dtype=str)),
                               errors="coerce", utc=True)
    df["severity"] = pd.to_numeric(df.get("severity", pd.Series(dtype=str)),
                                   errors="coerce").fillna(0).astype(int)
    return df.dropna(subset=["_dt"])


@router.get("/news-feed")
def get_news_feed(
    request:  Request,
    category: Optional[str] = Query(None, description="Filter by category name"),
    corridor: Optional[str] = Query(None, description="Filter by corridor name"),
    days:     int            = Query(30,  description="Lookback window in days"),
    limit:    int            = Query(20,  description="Max items returned", le=200),
):
    csv_dir: Path = request.app.state.csv_dir
    df = _load_feed(csv_dir)

    if df.empty:
        return {
            "items": [], "total": 0,
            "llm_stats": {"total_classified": 0, "total_flagged": 0, "llm_available": False},
            "data_source": "macro_events_filtered.csv",
        }

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    df_window = df[df["_dt"] >= cutoff].copy()

    # ── LLM stats (computed over the full window before filtering)
    llm_available = "llm_severity" in df_window.columns
    llm_stats = {"total_classified": 0, "total_flagged": 0, "llm_available": llm_available}
    if llm_available:
        classified_mask = (
            df_window["llm_severity"].notna() &
            df_window["llm_severity"].astype(str).str.strip().str.match(r"^\d+$")
        )
        llm_stats["total_classified"] = int(classified_mask.sum())
        if "review_flagged" in df_window.columns:
            flagged_mask = (
                df_window["review_flagged"].astype(str).str.lower().isin(["true", "1"])
            )
            llm_stats["total_flagged"] = int(flagged_mask.sum())

    # ── Apply filters
    if category:
        df_window = df_window[df_window["category"].str.lower() == category.lower()]
    if corridor:
        df_window = df_window[df_window["corridor"].str.lower() == corridor.lower()]

    df_window = df_window.sort_values("_dt", ascending=False).head(limit)

    def _str(v, default=''):
        """Return str, converting NaN/None/inf to default."""
        if v is None:
            return default
        try:
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return default
        except Exception:
            pass
        s = str(v)
        return default if s in ('nan', 'None', 'NaT') else s

    items = []
    for _, row in df_window.iterrows():
        item = {
            "title":             _str(row.get("title")),
            "source":            _str(row.get("source")),
            "link":              _str(row.get("link")),
            "date":              row["_dt"].isoformat(),
            "category":          _str(row.get("category")),
            "corridor":          _str(row.get("corridor"), "none"),
            "buffer_layer":      _str(row.get("buffer_layer"), "none"),
            "severity":          int(row.get("severity", 0) or 0),
            "key_takeaway":      _str(row.get("key_takeaway")),
            "extracted_numbers": _str(row.get("extracted_numbers")),
        }
        # Include LLM fields if available
        if llm_available:
            llm_sev_raw = _str(row.get("llm_severity"))
            try:
                item["llm_severity"] = int(llm_sev_raw) if llm_sev_raw else None
            except Exception:
                item["llm_severity"] = None

            llm_conf_raw = _str(row.get("llm_confidence"))
            try:
                item["llm_confidence"] = float(llm_conf_raw) if llm_conf_raw else None
            except Exception:
                item["llm_confidence"] = None

            flagged_raw = _str(row.get("review_flagged")).lower()
            item["review_flagged"]    = flagged_raw in ("true", "1")
            item["llm_justification"] = _str(row.get("llm_justification"))
            item["is_genuine_disruption"] = _str(row.get("is_genuine_disruption"))

        items.append(item)

    return {
        "items":           items,
        "total":           len(items),
        "total_available": len(items),
        "llm_stats":       llm_stats,
        "filters":         {"category": category, "corridor": corridor, "days": days},
        "data_source":     "macro_events_filtered.csv (live_macro_pipeline.py)",
    }
