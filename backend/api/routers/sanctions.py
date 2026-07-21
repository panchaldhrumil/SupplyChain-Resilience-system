from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, Request, HTTPException

from api.db import query_df

router = APIRouter()


@router.get("/sanctions/recent")
def get_recent_sanctions(
    request: Request,
    days: int = Query(30, description="Lookback window in days", le=365),
    sdn_type: str = Query("", description="Filter by sdn_type (e.g. 'Entity', 'Individual', 'Vessel')"),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    if sdn_type:
        df = query_df("""
            SELECT ent_num, sdn_name, sdn_type, program, remarks, fetched_at
            FROM sanctions
            WHERE new_since_last_run = TRUE
              AND fetched_at >= %s
              AND LOWER(TRIM(sdn_type)) = LOWER(%s)
            ORDER BY fetched_at DESC
        """, params=(cutoff, sdn_type.strip()))
    else:
        df = query_df("""
            SELECT ent_num, sdn_name, sdn_type, program, remarks, fetched_at
            FROM sanctions
            WHERE new_since_last_run = TRUE
              AND fetched_at >= %s
            ORDER BY fetched_at DESC
        """, params=(cutoff,))

    if df.empty:
        return {
            "entries":     [],
            "total":       0,
            "data_source": "Neon DB — sanctions table",
        }

    df["_fetched_dt"] = pd.to_datetime(df["fetched_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["_fetched_dt"])

    entries = []
    for _, row in df.iterrows():
        entries.append({
            "ent_num":    str(row.get("ent_num", "") or ""),
            "sdn_name":   str(row.get("sdn_name", "") or ""),
            "sdn_type":   str(row.get("sdn_type", "") or ""),
            "program":    str(row.get("program", "") or ""),
            "remarks":    str(row.get("remarks", "") or ""),
            "fetched_at": row["_fetched_dt"].isoformat(),
        })

    return {
        "entries":     entries,
        "total":       len(entries),
        "filters":     {"days": days, "sdn_type": sdn_type or "all"},
        "as_of":       datetime.now(timezone.utc).isoformat(),
        "data_source": "Neon DB — sanctions table",
    }
