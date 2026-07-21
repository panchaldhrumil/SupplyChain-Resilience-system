import os
import math
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, Request

from api.db import query_df

router = APIRouter()


def _safe(v, default=""):
    if v is None:
        return default
    try:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
    except Exception:
        pass
    s = str(v)
    return default if s in ("nan", "None", "NaT") else s


@router.get("/auto-alerts")
def get_auto_alerts(
    request: Request,
    limit: int = Query(20, description="Max alerts to return", le=100),
    corridor: Optional[str] = Query(None, description="Filter to specific corridor"),
):
    if corridor:
        df = query_df("""
            SELECT cycle_id, triggered_at, corridor, score_prev, score_now, threshold,
                   signal_detected_at, scenario_computed_at, recommendation_generated_at,
                   latency_ms, supply_gap_pct, coverage_days, buffer_status,
                   top_recommendation, top_score, all_affected_suppliers
            FROM alerts
            WHERE LOWER(corridor) = LOWER(%s)
            ORDER BY triggered_at DESC
            LIMIT %s
        """, params=(corridor, limit))
    else:
        df = query_df("""
            SELECT cycle_id, triggered_at, corridor, score_prev, score_now, threshold,
                   signal_detected_at, scenario_computed_at, recommendation_generated_at,
                   latency_ms, supply_gap_pct, coverage_days, buffer_status,
                   top_recommendation, top_score, all_affected_suppliers
            FROM alerts
            ORDER BY triggered_at DESC
            LIMIT %s
        """, params=(limit,))

    if df.empty:
        return {
            "alerts": [],
            "total": 0,
            "threshold": float(os.environ.get("AGENT_THRESHOLD", 66.0)),
            "source": "Neon DB — alerts table",
        }

    alerts = []
    for _, row in df.iterrows():
        latency_raw = _safe(row.get("latency_ms"))
        try:
            latency_ms = int(float(latency_raw)) if latency_raw else None
        except Exception:
            latency_ms = None

        score_now_raw = _safe(row.get("score_now"))
        try:
            score_now = float(score_now_raw) if score_now_raw else None
        except Exception:
            score_now = None

        score_prev_raw = _safe(row.get("score_prev"))
        try:
            score_prev = float(score_prev_raw) if score_prev_raw else None
        except Exception:
            score_prev = None

        cov_raw = _safe(row.get("coverage_days"))
        try:
            coverage_days = float(cov_raw) if cov_raw else None
        except Exception:
            coverage_days = None

        top_score_raw = _safe(row.get("top_score"))
        try:
            top_score = float(top_score_raw) if top_score_raw else None
        except Exception:
            top_score = None

        alerts.append({
            "cycle_id":                    _safe(row.get("cycle_id")),
            "triggered_at":                _safe(row.get("triggered_at")),
            "corridor":                    _safe(row.get("corridor")),
            "score_prev":                  score_prev,
            "score_now":                   score_now,
            "threshold":                   _safe(row.get("threshold")),
            "signal_detected_at":          _safe(row.get("signal_detected_at")),
            "scenario_computed_at":        _safe(row.get("scenario_computed_at")),
            "recommendation_generated_at": _safe(row.get("recommendation_generated_at")),
            "latency_ms":                  latency_ms,
            "supply_gap_pct":              _safe(row.get("supply_gap_pct")),
            "coverage_days":               coverage_days,
            "buffer_status":               _safe(row.get("buffer_status")),
            "top_recommendation":          _safe(row.get("top_recommendation")),
            "top_score":                   top_score,
            "all_affected_suppliers":      _safe(row.get("all_affected_suppliers")),
        })

    return {
        "alerts":    alerts,
        "total":     len(alerts),
        "threshold": float(os.environ.get("AGENT_THRESHOLD", 66.0)),
        "source":    "Neon DB — alerts table",
    }
