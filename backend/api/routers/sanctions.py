"""
GET /api/sanctions/recent?days=30

Returns OFAC SDN entries flagged as new_since_last_run=True within
the specified lookback window. Useful for monitoring newly designated
entities (tankers, companies, individuals) relevant to energy supply chains.

Real data source: ofac_sanctions.csv written by fetch_ofac_sanctions_list()
(downloaded from treasury.gov/ofac/downloads/sdn.csv — public, no auth)
"""

from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter()


@router.get("/sanctions/recent")
def get_recent_sanctions(
    request: Request,
    days:    int = Query(30, description="Lookback window in days", le=365),
    sdn_type: str = Query("", description="Filter by sdn_type (e.g. 'Entity', 'Individual', 'Vessel')"),
):
    csv_dir: Path = request.app.state.csv_dir
    path = csv_dir / "ofac_sanctions.csv"

    if not path.exists():
        return {
            "entries":     [],
            "total":       0,
            "data_source": "ofac_sanctions.csv not found — run live_macro_pipeline.py first",
        }

    try:
        df = pd.read_csv(path, dtype=str, low_memory=False)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"CSV read error: {e}")

    required = {"ent_num", "sdn_name", "new_since_last_run", "fetched_at"}
    if not required.issubset(df.columns):
        return {
            "entries":     [],
            "total":       0,
            "data_source": "ofac_sanctions.csv schema mismatch — re-run pipeline",
        }

    # Filter to only net-new entries
    df["_new"] = df["new_since_last_run"].str.strip().str.lower().isin(["true", "1", "yes"])
    df = df[df["_new"]]

    # Parse fetch timestamp and apply window filter
    df["_fetched_dt"] = pd.to_datetime(df["fetched_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["_fetched_dt"])
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    df = df[df["_fetched_dt"] >= cutoff]

    if sdn_type:
        df = df[df["sdn_type"].str.strip().str.lower() == sdn_type.lower()]

    df = df.sort_values("_fetched_dt", ascending=False)

    entries = []
    for _, row in df.iterrows():
        entries.append({
            "ent_num":    row.get("ent_num", ""),
            "sdn_name":   row.get("sdn_name", ""),
            "sdn_type":   row.get("sdn_type", ""),
            "program":    row.get("program", ""),
            "remarks":    row.get("remarks", ""),
            "fetched_at": row["_fetched_dt"].isoformat(),
        })

    return {
        "entries":        entries,
        "total":          len(entries),
        "filters":        {"days": days, "sdn_type": sdn_type or "all"},
        "as_of":          datetime.now(timezone.utc).isoformat(),
        "data_source":    "ofac_sanctions.csv (OFAC SDN list — treasury.gov/ofac/downloads/sdn.csv)",
    }
