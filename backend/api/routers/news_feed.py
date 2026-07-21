import math
from datetime import datetime, timezone, timedelta, date as date_cls
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query, Request

from api.db import query_df, query_rows

router = APIRouter()

_COLS = [
    "date", "title", "source", "link", "category",
    "buffer_layer", "corridor", "severity",
    "key_takeaway", "fetch_status", "extracted_numbers",
    "llm_severity", "llm_confidence", "is_genuine_disruption",
    "llm_corridor", "llm_justification", "review_flagged", "llm_status",
]


def _load_feed(lookback_days=30):
    cutoff = date_cls.today() - timedelta(days=lookback_days)
    df = query_df("""
        SELECT date, title, source, link, category,
               buffer_layer, corridor, severity,
               key_takeaway, fetch_status, extracted_numbers,
               llm_severity, llm_confidence, is_genuine_disruption,
               llm_corridor, llm_justification, review_flagged, llm_status
        FROM macro_events
        WHERE date >= %s
        ORDER BY date DESC
    """, params=(cutoff,))
    if df.empty:
        return df
    df["_dt"] = pd.to_datetime(df["date"], utc=True, errors="coerce")
    df = df.dropna(subset=["_dt"])
    df["severity"] = pd.to_numeric(df.get("severity"), errors="coerce").fillna(0).astype(int)
    return df


@router.get("/news-feed")
def get_news_feed(
    request:  Request,
    category: Optional[str] = Query(None, description="Filter by category name"),
    corridor: Optional[str] = Query(None, description="Filter by corridor name"),
    days:     int            = Query(30,  description="Lookback window in days"),
    limit:    int            = Query(20,  description="Max items returned", le=200),
):
    df = _load_feed(lookback_days=days)

    if df.empty:
        return {
            "items": [], "total": 0,
            "llm_stats": {"total_classified": 0, "total_flagged": 0, "llm_available": False},
            "data_source": "Neon DB — macro_events",
        }

    llm_available = "llm_severity" in df.columns
    llm_stats = {"total_classified": 0, "total_flagged": 0, "llm_available": llm_available}
    if llm_available:
        classified_mask = (
            df["llm_severity"].notna() &
            df["llm_severity"].astype(str).str.strip().str.match(r"^\d+$")
        )
        llm_stats["total_classified"] = int(classified_mask.sum())
        if "review_flagged" in df.columns:
            flagged_mask = df["review_flagged"].astype(str).str.lower().isin(["true", "1", "t"])
            llm_stats["total_flagged"] = int(flagged_mask.sum())

    if category:
        df = df[df["category"].str.lower() == category.lower()]
    if corridor:
        df = df[df["corridor"].str.lower() == corridor.lower()]

    df = df.sort_values("_dt", ascending=False).head(limit)

    def _str(v, default=""):
        if v is None:
            return default
        try:
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                return default
        except Exception:
            pass
        s = str(v)
        return default if s in ("nan", "None", "NaT") else s

    items = []
    for _, row in df.iterrows():
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
            item["review_flagged"]        = flagged_raw in ("true", "1", "t")
            item["llm_justification"]     = _str(row.get("llm_justification"))
            item["is_genuine_disruption"] = _str(row.get("is_genuine_disruption"))

        items.append(item)

    return {
        "items":           items,
        "total":           len(items),
        "total_available": len(items),
        "llm_stats":       llm_stats,
        "filters":         {"category": category, "corridor": corridor, "days": days},
        "data_source":     "Neon DB — macro_events",
    }
