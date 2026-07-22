"""
GET /api/buffer-stack

Returns India's three-layer crude oil buffer:
  1. on_water      — crude currently in transit (calculated, not published)
  2. refinery_stock — petroleum product stocks at refineries + depots (PIB)
  3. spr           — strategic petroleum reserve (PIB + Rajya Sabha RTI)

SPR and refinery_stock values are read from buffer_config.json (real cited
figures). on_water is computed by calculate_on_water_days() using
import_mix.json (fill from PPAC data before demo).

Every layer in the response carries a 'source' field and a 'methodology'
field so the frontend can display "PIB, verified [date]" style citations.
"""

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException

router = APIRouter()


# --------------------------------------------------------------------------
# calculate_on_water_days()
# --------------------------------------------------------------------------

def calculate_on_water_days(config_dir: Path) -> dict:
    """
    Estimate crude oil days currently in transit to India.

    Algorithm
    ---------
    1. Read import_mix.json — source countries, their import share (%),
       typical transit days, and India's daily crude consumption (bbl/day).
    2. Weighted-average transit time = Σ(share_i / 100 × transit_days_i)
    3. 'On-water days' = weighted_avg_transit_days
       (this equals barrels-in-transit / daily-consumption because
        barrels-in-transit = share_i × daily_consumption × transit_days_i
        summed over all sources, which simplifies to
        daily_consumption × Σ(share_i/100 × transit_days_i))
    4. Returns result with methodology="estimated" — NEVER call this live data.

    Returns a dict with:
        days_cover          — estimated days cover (float) or None if inputs missing
        weighted_avg_days   — weighted avg transit days across all sources
        methodology         — always "estimated"
        inputs_complete     — bool, False if any required field is null
        sources_used        — list of countries and their weights
        note                — human-readable caveat for UI display
    """
    mix_path = config_dir / "import_mix.json"
    if not mix_path.exists():
        return {
            "days_cover":        None,
            "methodology":       "estimated",
            "inputs_complete":   False,
            "note":              "import_mix.json not found. Cannot calculate.",
        }

    try:
        with open(mix_path, encoding="utf-8") as f:
            mix = json.load(f)
    except Exception as e:
        return {
            "days_cover":        None,
            "methodology":       "estimated",
            "inputs_complete":   False,
            "note":              f"Failed to read import_mix.json: {e}",
        }

    daily_consumption = mix.get("daily_consumption_bbl")
    sources = mix.get("sources", [])

    # Check if all required inputs are populated
    shares_ok = all(
        s.get("import_share_pct") is not None for s in sources
    )
    consumption_ok = daily_consumption is not None
    inputs_complete = shares_ok and consumption_ok

    if not inputs_complete:
        # Can still compute weighted avg days if shares are present (even without
        # consumption, weighted avg days = on_water days by definition)
        if shares_ok and sources:
            total_share = sum(s["import_share_pct"] for s in sources)
            if total_share > 0:
                wavg = sum(
                    (s["import_share_pct"] / total_share) * s.get("transit_days_typical", 0)
                    for s in sources
                )
                return {
                    "days_cover":        round(wavg, 1),
                    "weighted_avg_transit_days": round(wavg, 1),
                    "methodology":       "estimated",
                    "inputs_complete":   False,
                    "sources_used":      [
                        {"country": s["country"],
                         "share_pct": s["import_share_pct"],
                         "transit_days": s.get("transit_days_typical")}
                        for s in sources
                    ],
                    "note": (
                        "daily_consumption_bbl not set in import_mix.json — "
                        "days_cover equals weighted-avg transit days (algebraically equivalent). "
                        "Fill daily_consumption_bbl from PPAC Daily Petroleum Report for full traceability."
                    ),
                }
        return {
            "days_cover":        None,
            "methodology":       "estimated",
            "inputs_complete":   False,
            "note": (
                "TODO: Populate import_share_pct for each country and "
                "daily_consumption_bbl in backend/config/import_mix.json "
                "using PPAC Monthly Import Data (ppac.gov.in)."
            ),
        }

    # Full calculation
    total_share = sum(s["import_share_pct"] for s in sources)
    weighted_avg_days = sum(
        (s["import_share_pct"] / total_share) * s.get("transit_days_typical", 0)
        for s in sources
    )
    # days_cover = barrels_in_transit / daily_consumption
    #            = daily_consumption × weighted_avg_days / daily_consumption
    #            = weighted_avg_days   (the consumption cancels)
    days_cover = weighted_avg_days

    return {
        "days_cover":                   round(days_cover, 1),
        "weighted_avg_transit_days":    round(weighted_avg_days, 1),
        "daily_consumption_bbl":        daily_consumption,
        "methodology":                  "estimated",
        "inputs_complete":              True,
        "sources_used":                 [
            {"country": s["country"],
             "share_pct": s["import_share_pct"],
             "transit_days": s.get("transit_days_typical")}
            for s in sources
        ],
        "note": (
            "Weighted-average voyage transit time across import sources. "
            "Not an official published figure — derived from PPAC import mix data."
        ),
    }


def calculate_buffer_coverage_logic(
    gap_pct: float,
    duration_days: float,
    spr_days: float,
    refinery_days: float,
) -> dict:
    """
    Core deterministic coverage calculator shared by Module 2 (Scenario Simulator)
    and Module 4 (Reserve Optimizer).

    Returns
    -------
    total_cover_days : float
        How long the combined reserve buffer can sustain the supply gap.
        Invariant to duration_days — it is a property of gap_pct and reserve levels.
    reserves_consumed_pct : float
        Percentage of total reserve buffer consumed by THIS disruption.
        Changes with BOTH severity (gap_pct) and duration_days, making it
        the primary metric to display when the user adjusts duration.
    total_sufficient : bool
        Whether total_cover_days >= duration_days.
    """
    total_reserve_days = spr_days + refinery_days

    if gap_pct <= 0:
        return {
            "spr_cover_days":        0.0,
            "total_cover_days":      0.0,
            "reserves_consumed_pct": 0.0,
            "spr_sufficient":        True,
            "total_sufficient":      True,
            "spr_difference_days":   0.0,
            "total_difference_days": 0.0,
        }

    gap_fraction     = gap_pct / 100.0
    spr_cover_days   = spr_days         / gap_fraction
    total_cover_days = total_reserve_days / gap_fraction

    # How much of the total reserve buffer does THIS disruption consume?
    # Formula: (gap_fraction × duration_days / total_reserve_days) × 100
    # This changes with both severity (gap_fraction) AND duration_days.
    reserves_consumed_pct = (
        round((gap_fraction * duration_days / total_reserve_days) * 100.0, 1)
        if total_reserve_days > 0 else None
    )

    spr_sufficient   = spr_cover_days   >= duration_days
    total_sufficient = total_cover_days >= duration_days

    return {
        "spr_cover_days":        round(spr_cover_days,   1),
        "total_cover_days":      round(total_cover_days, 1),
        "reserves_consumed_pct": reserves_consumed_pct,
        "spr_sufficient":        bool(spr_sufficient),
        "total_sufficient":      bool(total_sufficient),
        "spr_difference_days":   round(spr_cover_days   - duration_days, 1),
        "total_difference_days": round(total_cover_days - duration_days, 1),
    }


# --------------------------------------------------------------------------
# Router
# --------------------------------------------------------------------------

@router.get("/buffer-stack")
def get_buffer_stack(request: Request):
    config_dir: Path = request.app.state.config_dir
    cfg_path = config_dir / "buffer_config.json"
    assumptions_path = config_dir / "scenario_assumptions.json"

    if not cfg_path.exists():
        raise HTTPException(
            status_code=500,
            detail="buffer_config.json not found. Check CONFIG_DIR env var.",
        )

    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config read error: {e}")

    # Read assumptions for average tanker cargo size
    assumptions = {}
    if assumptions_path.exists():
        try:
            with open(assumptions_path, encoding="utf-8") as f:
                assumptions = json.load(f)
        except Exception:
            pass

    avg_cargo_size = float(assumptions.get("average_tanker_cargo_size_bbl", 1500000))

    spr_cfg      = cfg.get("spr", {})
    refinery_cfg = cfg.get("refinery_stock", {})

    # on_water — calculated, not scraped
    on_water = calculate_on_water_days(config_dir)

    layers = [
        {
            "layer":            "on_water",
            "label":            "Crude on Water (in transit)",
            "days_cover":       on_water.get("days_cover"),
            "methodology":      on_water.get("methodology", "estimated"),
            "inputs_complete":  on_water.get("inputs_complete", False),
            "source":           "Derived from PPAC Monthly Import Data + voyage transit times",
            "source_url":       "https://ppac.gov.in/content/245_1_ImportExport.aspx",
            "note":             on_water.get("note", ""),
            "display_badge":    "Estimated — not a published figure",
            "calculation_detail": on_water,
        },
        {
            "layer":            "refinery_stock",
            "label":            "Refinery + Depot Stock",
            "days_cover":       refinery_cfg.get("days_cover"),
            "methodology":      "official_published",
            "inputs_complete":  refinery_cfg.get("days_cover") is not None,
            "source":           refinery_cfg.get("source", ""),
            "source_url":       "https://pib.gov.in/PressReleasePage.aspx?PRID=1694712",
            "last_verified":    refinery_cfg.get("last_verified", ""),
            "note":             refinery_cfg.get("note", ""),
            "display_badge":    "PIB Verified",
        },
        {
            "layer":            "spr",
            "label":            "Strategic Petroleum Reserve (SPR)",
            "days_cover":       spr_cfg.get("estimated_days_cover_current"),
            "days_cover_full":  spr_cfg.get("days_cover_at_full_capacity"),
            "current_fill_pct": spr_cfg.get("current_fill_pct"),
            "total_capacity_mmt": spr_cfg.get("total_capacity_mmt"),
            "sites":            spr_cfg.get("sites", []),
            "methodology":      "official_published",
            "inputs_complete":  spr_cfg.get("estimated_days_cover_current") is not None,
            "source":           spr_cfg.get("source", ""),
            "source_url":       "https://pib.gov.in/PressReleasePage.aspx?PRID=1694712",
            "last_verified":    spr_cfg.get("last_verified", ""),
            "note":             spr_cfg.get("note", ""),
            "display_badge":    "PIB + Rajya Sabha RTI Verified",
        },
    ]

    total_days = sum(
        (lay["days_cover"] or 0) for lay in layers
        if lay["days_cover"] is not None
    )

    # Derived vessel estimation
    estimated_vessels = None
    vessel_note = "daily_consumption_bbl or transit days not set in import_mix.json."
    if on_water.get("inputs_complete"):
        daily_consumption_million = float(on_water.get("daily_consumption_bbl", 0.0))
        transit_days = float(on_water.get("days_cover", 0.0))
        total_bbl_in_transit = daily_consumption_million * 1_000_000 * transit_days
        estimated_vessels = round(total_bbl_in_transit / avg_cargo_size, 1)
        vessel_note = (
            f"Estimated crude tankers currently bound for India. "
            f"Formula: (Daily crude throughput {daily_consumption_million}M bbl × Average transit {transit_days} days) / Average cargo {avg_cargo_size / 1_000_000:.2f}M bbl."
        )

    # ── Refinery stock breakdown (Item 3A + 5) ─────────────────────────────
    # Proportional allocation: each refinery gets (capacity_mmtpa / total_mapped_mmtpa) × 64.5 days
    # Source: refinery capacities from MoPNG Annual Report FY2024-25 / company reports.
    # Total installed capacity: ~258.1 MMTPA (MoPNG).
    # 11 major refineries mapped: ~206 MMTPA = ~79.8% of total.
    REFINERY_CAPACITIES = [
        {"name": "Jamnagar (Reliance)",        "operator": "Reliance Industries",    "capacity_mmtpa": 60.0},
        {"name": "Mumbai (HPCL + BPCL)",        "operator": "HPCL + BPCL",            "capacity_mmtpa": 21.5},
        {"name": "Vadinar (Nayara/Rosneft)",   "operator": "Nayara Energy",          "capacity_mmtpa": 20.0},
        {"name": "Kochi (BPCL)",               "operator": "BPCL",                   "capacity_mmtpa": 15.5},
        {"name": "Mangalore (MRPL)",            "operator": "MRPL (ONGC subsidiary)", "capacity_mmtpa": 15.0},
        {"name": "Paradip (IOCL)",              "operator": "Indian Oil",             "capacity_mmtpa": 15.0},
        {"name": "Panipat (IOCL)",              "operator": "Indian Oil",             "capacity_mmtpa": 15.0},
        {"name": "Koyali/Vadodara (IOCL)",      "operator": "Indian Oil",             "capacity_mmtpa": 13.7},
        {"name": "Bathinda (HMEL)",             "operator": "HPCL-Mittal Energy",     "capacity_mmtpa": 11.3},
        {"name": "Manali/Chennai (CPCL)",        "operator": "Chennai Petro (CPCL)",   "capacity_mmtpa": 10.5},
        {"name": "Visakhapatnam (HPCL)",        "operator": "HPCL",                   "capacity_mmtpa":  8.3},
    ]
    TOTAL_INSTALLED_MMTPA = 258.1   # MoPNG Annual Report FY2024-25
    TOTAL_MAPPED_MMTPA    = sum(r["capacity_mmtpa"] for r in REFINERY_CAPACITIES)  # ~206
    OTHERS_MMTPA          = max(TOTAL_INSTALLED_MMTPA - TOTAL_MAPPED_MMTPA, 0.0)
    AGGREGATE_DAYS        = float(refinery_cfg.get("days_cover") or 64.5)          # PIB figure

    refinery_breakdown = []
    for r in REFINERY_CAPACITIES:
        share_pct   = r["capacity_mmtpa"] / TOTAL_INSTALLED_MMTPA * 100.0
        days_alloc  = round(AGGREGATE_DAYS * r["capacity_mmtpa"] / TOTAL_INSTALLED_MMTPA, 1)
        refinery_breakdown.append({
            "name":             r["name"],
            "operator":         r["operator"],
            "capacity_mmtpa":   r["capacity_mmtpa"],
            "share_pct":        round(share_pct, 1),
            "stock_days_est":   days_alloc,
            "methodology":      "modelled_estimate",
            "note":             (
                f"Stock-days = aggregate PIB figure ({AGGREGATE_DAYS}d) × "
                f"capacity share ({r['capacity_mmtpa']}/{TOTAL_INSTALLED_MMTPA} MMTPA = {share_pct:.1f}%). "
                "Modelled estimate — real per-refinery stock is not published."
            ),
        })
    # "Others" row — remaining smaller refineries not individually mapped
    others_share  = OTHERS_MMTPA / TOTAL_INSTALLED_MMTPA * 100.0
    others_days   = round(AGGREGATE_DAYS * OTHERS_MMTPA / TOTAL_INSTALLED_MMTPA, 1)
    refinery_breakdown.append({
        "name":             "Others (smaller refineries)",
        "operator":         "Various",
        "capacity_mmtpa":   round(OTHERS_MMTPA, 1),
        "share_pct":        round(others_share, 1),
        "stock_days_est":   others_days,
        "methodology":      "modelled_estimate",
        "note":             (
            f"Aggregate for refineries not individually mapped (~{OTHERS_MMTPA:.1f} MMTPA combined). "
            "Includes Numaligarh, Haldia, Tatipaka, Bongaigaon and others."
        ),
    })
    # Sort by capacity descending so largest comes first in UI
    refinery_breakdown.sort(key=lambda x: x["capacity_mmtpa"], reverse=True)

    # ── SPR breakdown (Item 3B) ─────────────────────────────────────────────
    # National average fill: 64% (PIB + Rajya Sabha RTI, verified 2026-03-23)
    spr_fill_pct     = float(spr_cfg.get("current_fill_pct", 64))
    spr_full_days    = float(spr_cfg.get("days_cover_at_full_capacity", 9.5))
    spr_breakdown = []
    for site in spr_cfg.get("sites", []):
        site_cap_mmt  = float(site.get("capacity_mmt", 0))
        site_fill_mmt = round(site_cap_mmt * spr_fill_pct / 100, 3)
        site_days     = round(spr_full_days * (site_cap_mmt / float(spr_cfg.get("total_capacity_mmt", 5.33))) * spr_fill_pct / 100, 2)
        spr_breakdown.append({
            "site":              site["name"],
            "capacity_mmt":      site_cap_mmt,
            "fill_pct_national": spr_fill_pct,
            "est_fill_mmt":      site_fill_mmt,
            "est_days_cover":    site_days,
            "methodology":       "modelled_estimate",
            "note": (
                f"64% fill is the national average (PIB/RTI 2026-03). "
                f"Per-site breakdown is estimated by capacity share. "
                f"ISPRL does not publish site-level fill publicly."
            ),
        })

    return {
        "layers":          layers,
        "total_days_cover": round(total_days, 1),
        "note":            (
            "Total is the sum of on-water + refinery stock + SPR. "
            "on_water is an estimate; SPR fill % may have changed — "
            "verify against ISPRL/PPAC before final presentation."
        ),
        "config_source":   "backend/config/buffer_config.json",
        "vessels_in_transit": {
            "estimated_vessels": estimated_vessels,
            "average_cargo_size_bbl": avg_cargo_size,
            "note": vessel_note,
            "display_badge": "Estimated — Not Tracked"
        },
        "refinery_breakdown": {
            "refineries":              refinery_breakdown,
            "aggregate_stock_days":    AGGREGATE_DAYS,
            "total_installed_mmtpa":   TOTAL_INSTALLED_MMTPA,
            "total_mapped_mmtpa":      round(TOTAL_MAPPED_MMTPA, 1),
            "coverage_pct":            round(TOTAL_MAPPED_MMTPA / TOTAL_INSTALLED_MMTPA * 100, 1),
            "source":                  "MoPNG Annual Report FY2024-25; company annual reports",
            "aggregate_source":        "PIB Press Release PRID=1694712 (March 2026)",
            "methodology_note":        (
                "Per-refinery stock-days are modelled estimates derived by applying each refinery's "
                "installed capacity share to the published 64.5-day aggregate. "
                "Actual per-refinery inventories are not publicly available."
            ),
        },
        "spr_breakdown": {
            "sites":            spr_breakdown,
            "national_fill_pct": spr_fill_pct,
            "total_capacity_mmt": spr_cfg.get("total_capacity_mmt"),
            "source":           spr_cfg.get("source", ""),
            "last_verified":    spr_cfg.get("last_verified", ""),
            "methodology_note": (
                "Per-site fill is estimated from the 64% national average fill (PIB+RTI 2026-03). "
                "ISPRL does not publish site-level crude stock data publicly."
            ),
        },
    }


@router.get("/buffer-coverage")
def get_buffer_coverage(request: Request, gap_pct: float, duration_days: float):
    config_dir: Path = request.app.state.config_dir
    cfg_path = config_dir / "buffer_config.json"

    if not cfg_path.exists():
        raise HTTPException(
            status_code=500,
            detail="buffer_config.json not found.",
        )

    try:
        with open(cfg_path, encoding="utf-8") as f:
            cfg = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Config read error: {e}")

    spr_days = cfg.get("spr", {}).get("estimated_days_cover_current", 0.0)
    refinery_days = cfg.get("refinery_stock", {}).get("days_cover", 0.0)

    res = calculate_buffer_coverage_logic(gap_pct, duration_days, spr_days, refinery_days)
    return res

