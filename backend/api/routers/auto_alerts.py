import os
import math
from pathlib import Path
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, Request

from api.db import query_df

router = APIRouter()


def _safe(v, default=""):
    if v is None or pd.isna(v):
        return default
    s = str(v)
    return default if s in ("nan", "None", "NaT") else s


def _parse_int(v) -> Optional[int]:
    if v is None or pd.isna(v):
        return None
    try:
        f = float(v)
        return int(f) if not (math.isnan(f) or math.isinf(f)) else None
    except Exception:
        return None


def _parse_float(v) -> Optional[float]:
    if v is None or pd.isna(v):
        return None
    try:
        f = float(v)
        return round(f, 1) if not (math.isnan(f) or math.isinf(f)) else None
    except Exception:
        return None


@router.get("/auto-alerts")
def get_auto_alerts(
    request: Request,
    limit: int = Query(20, description="Max alerts to return", le=100),
    corridor: Optional[str] = Query(None, description="Filter to specific corridor"),
):
    lim_val = limit if isinstance(limit, int) else getattr(limit, "default", 20)
    if not isinstance(lim_val, int):
        lim_val = 20

    corr_val = corridor if isinstance(corridor, str) else getattr(corridor, "default", None)
    if not isinstance(corr_val, str) or corr_val == "None":
        corr_val = None

    df = pd.DataFrame()
    try:
        if corr_val:
            df = query_df("""
                SELECT * FROM alerts
                WHERE LOWER(corridor) = LOWER(%s)
                ORDER BY triggered_at DESC
                LIMIT %s
            """, params=(corr_val, lim_val))
        else:
            df = query_df("""
                SELECT * FROM alerts
                ORDER BY triggered_at DESC
                LIMIT %s
            """, params=(lim_val,))
    except Exception as e:
        print(f"[auto-alerts API error] {e}")

    # Fallback to CSV if DB empty
    if df.empty:
        base_dir = Path(__file__).resolve().parent.parent.parent
        csv_path = base_dir / "data" / "macro_events" / "auto_triggered_alerts.csv"
        if csv_path.exists():
            try:
                df = pd.read_csv(csv_path)
                if corridor and not df.empty and "corridor" in df.columns:
                    df = df[df["corridor"].str.lower() == corridor.lower()]
                if not df.empty:
                    df = df.sort_values("triggered_at", ascending=False).head(limit)
            except Exception:
                df = pd.DataFrame()

    if df.empty:
        return {
            "alerts": [],
            "total": 0,
            "threshold": float(os.environ.get("AGENT_THRESHOLD", 66.0)),
            "source": "Neon DB / CSV",
        }

    alerts = []
    for _, row in df.iterrows():
        alerts.append({
            "cycle_id":                    _safe(row.get("cycle_id")),
            "triggered_at":                _safe(row.get("triggered_at")),
            "corridor":                    _safe(row.get("corridor")),
            "score_prev":                  _parse_float(row.get("score_prev")),
            "score_now":                   _parse_float(row.get("score_now")),
            "threshold":                   _safe(row.get("threshold")),
            "signal_detected_at":          _safe(row.get("signal_detected_at")),
            "scenario_computed_at":        _safe(row.get("scenario_computed_at")),
            "recommendation_generated_at": _safe(row.get("recommendation_generated_at")),
            "latency_ms":                  _parse_int(row.get("latency_ms")),
            "signal_to_scenario_ms":       _parse_int(row.get("signal_to_scenario_ms")),
            "scenario_to_procurement_ms":  _parse_int(row.get("scenario_to_procurement_ms")),
            "procurement_to_llm_ms":       _parse_int(row.get("procurement_to_llm_ms")),
            "supply_gap_pct":              _parse_float(row.get("supply_gap_pct")),
            "coverage_days":               _parse_float(row.get("coverage_days")),
            "coverage_note":               _safe(row.get("coverage_note")),
            "buffer_status":               _safe(row.get("buffer_status")),
            "top_recommendation":          _safe(row.get("top_recommendation")),
            "top_score":                   _parse_float(row.get("top_score")),
            "all_affected_suppliers":      _safe(row.get("all_affected_suppliers")),
        })

    return {
        "alerts":    alerts,
        "total":     len(alerts),
        "threshold": float(os.environ.get("AGENT_THRESHOLD", 66.0)),
        "source":    "Neon DB / CSV",
    }
