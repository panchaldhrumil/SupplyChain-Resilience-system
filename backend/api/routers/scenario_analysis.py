"""
backend/api/routers/scenario_analysis.py
=========================================
Endpoints for Module 2 (Scenario Simulator) and Module 3 (Procurement Recommendation Engine).
Uses live data from config files and news to run deterministic policy support models.

TIER 1 additions:
  - generate_justification() — LLM-generated one-sentence grounded justification
    (opt-in via ?llm_justify=true; requires ANTHROPIC_API_KEY)
  - rank_alternatives_internal() — extracted pure function called by both the
    FastAPI endpoint AND the autonomous response agent (no duplication)
"""

import os
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from fastapi import APIRouter, Query, Request, HTTPException
import pandas as pd

from api.routers.buffer_stack import calculate_buffer_coverage_logic

router = APIRouter()

# Anthropic key loaded from environment (never hardcoded)
_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# ──────────────────────────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────────────────────────

def _read_config(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ──────────────────────────────────────────────────────────────────
# LLM PROCUREMENT JUSTIFICATION  (TIER 1 — opt-in via ?llm_justify=true)
# ──────────────────────────────────────────────────────────────────

def generate_justification(
    rec: dict,
    rank: int,
    disrupted_id: str,
    api_key: str,
) -> Optional[str]:
    """
    Generate a single grounded sentence explaining why this supplier ranks at
    position `rank` for replacing `disrupted_id`.

    The LLM ONLY receives the pre-computed numerical scores — it cannot
    invent geopolitical facts. The prompt explicitly forbids adding information
    not present in the numbers passed to it.

    Returns None on any failure (graceful degradation).
    """
    if not api_key:
        return None

    try:
        import anthropic
    except ImportError:
        return None

    prompt = (
        f"You are a procurement analyst writing a brief for India's energy ministry.\n"
        f"A disruption at {disrupted_id} requires finding an alternative crude supplier.\n"
        f"Based ONLY on the computed scores below, write exactly ONE sentence (max 30 words) "
        f"explaining why {rec['name']} ranks #{rank}.\n"
        f"Do NOT add any external geopolitical facts not derivable from these numbers.\n\n"
        f"Computed scores for {rec['name']}:\n"
        f"  - Transit time: {rec.get('transit_days', 'N/A')} days "
        f"(transit_score={rec.get('transit_score', 'N/A')}/100)\n"
        f"  - Route safety: {rec.get('safety_score', 'N/A')}/100 "
        f"(chokepoint exposure: {rec.get('chokepoint_exposure', 'N/A')}%)\n"
        f"  - Supplier reliability: {rec.get('reliability_score', 'N/A')}/100\n"
        f"  - Final weighted score: {rec.get('final_score', 'N/A')}/100\n"
        f"  - Crude grade: {rec.get('crude_grade', 'N/A')}\n"
        f"  - Is sanctioned: {rec.get('is_sanctioned', False)}\n\n"
        f"Output ONLY the single sentence, nothing else."
    )

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=80,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────
# PROCUREMENT RANKING — PURE FUNCTION (reusable by agent + API)
# ──────────────────────────────────────────────────────────────────

def rank_alternatives_internal(
    config_dir: Path,
    csv_dir: Path,
    disrupted_id: str,
    required_volume_pct: float = 20.0,
    max_transit_days: float = 30.0,
    llm_justify: bool = False,
    llm_api_key: str = "",
) -> dict:
    """
    Pure-function version of /api/procurement-recommend.
    Called by both the FastAPI endpoint and the autonomous response agent
    (response_agent.py) — no duplication of scoring logic.

    Returns the same dict structure as the HTTP endpoint.
    """
    mix_path         = config_dir / "import_mix.json"
    assumptions_path = config_dir / "scenario_assumptions.json"
    mix         = _read_config(mix_path)
    assumptions = _read_config(assumptions_path)

    # ── Load live corridor risks from CSV (same algorithm as risk_corridors.py)
    from api.routers.risk_corridors import _load_events, _decay_weight, ALL_CORRIDORS, RAW_SCORE_CEILING
    import math
    df_events = _load_events(csv_dir, lookback_days=7)
    now_ts = pd.Timestamp.now(tz="UTC")

    corridor_risks = {}
    for corridor in ALL_CORRIDORS:
        sub = df_events[df_events["corridor"] == corridor] if not df_events.empty else pd.DataFrame()
        if sub.empty:
            corridor_risks[corridor] = 0.0
            continue
        raw = 0.0
        for _, row in sub.iterrows():
            w = _decay_weight(row["_dt"], now_ts)
            raw += float(row["severity"]) * w
        corridor_risks[corridor] = round(min(raw / RAW_SCORE_CEILING * 100.0, 100.0), 1)

    # ── Check for OFAC sanctions
    sanctions_path = csv_dir / "ofac_sanctions.csv"
    sanctioned_countries = set()
    if sanctions_path.exists():
        try:
            df_sanc = pd.read_csv(sanctions_path, dtype=str, low_memory=False)
            df_sanc["_new"] = df_sanc["new_since_last_run"].str.strip().str.lower().isin(["true", "1", "yes"])
            df_recent = df_sanc[df_sanc["_new"]]
            for _, row in df_recent.iterrows():
                name    = str(row.get("sdn_name",  "")).upper()
                remarks = str(row.get("remarks",   "")).upper()
                if "RUSSIA" in name or "RUSSIA" in remarks:
                    sanctioned_countries.add("Russia")
                if "IRAN" in name or "IRAN" in remarks:
                    sanctioned_countries.add("Iran")
        except Exception:
            pass

    # ── Cost discount citations from Alt_Crude_Sourcing news
    discount_citations = {}
    master_path = csv_dir / "macro_events_filtered.csv"
    if master_path.exists():
        try:
            df_news = pd.read_csv(master_path, dtype=str, low_memory=False)
            df_alt = df_news[df_news["category"] == "Alt_Crude_Sourcing"].copy()
            if not df_alt.empty:
                for country_key in ["Russia", "USA", "Iraq", "Nigeria", "Saudi Arabia"]:
                    cond = (
                        df_alt["title"].str.contains(country_key, case=False, na=False) |
                        df_alt["key_takeaway"].str.contains(country_key, case=False, na=False)
                    )
                    country_news = df_alt[cond]
                    if not country_news.empty:
                        latest_art = country_news.sort_values("date", ascending=False).iloc[0]
                        nums = latest_art.get("extracted_numbers")
                        if pd.notna(nums) and str(nums).strip() not in ("", "nan"):
                            discount_citations[country_key] = {
                                "citation": f"\"{latest_art.get('title')}\" ({latest_art.get('source')})",
                                "value": str(nums).strip(),
                            }
        except Exception:
            pass

    # ── Supplier list
    ALTERNATIVES = [
        {"name": "Iraq",         "country": "Iraq",         "crude_grade": "Basra Medium/Heavy"},
        {"name": "Saudi Arabia", "country": "Saudi Arabia", "crude_grade": "Arab Light/Medium"},
        {"name": "Russia",       "country": "Russia",       "crude_grade": "Urals"},
        {"name": "USA",          "country": "USA",          "crude_grade": "WTI Light Sweet"},
        {"name": "Nigeria",      "country": "Nigeria",      "crude_grade": "Bonny Light"},
        {"name": "UAE",          "country": "UAE",          "crude_grade": "Murban"},
        {"name": "Kuwait",       "country": "Kuwait",       "crude_grade": "Kuwait Export"},
    ]

    country_chokepoints = assumptions.get("country_chokepoints", {})
    reliability_scores  = assumptions.get("supplier_reliability", {})
    weights             = assumptions.get("weights", {
        "transit_speed": 0.4, "chokepoint_safety": 0.4, "supplier_reliability": 0.2
    })

    sources     = mix.get("sources", [])
    transit_map = {s.get("country"): s.get("transit_days_typical") for s in sources if s.get("country")}

    TRANSIT_FALLBACK = {
        "Iraq": 12, "Saudi Arabia": 10, "Russia": 27, "UAE": 8,
        "USA": 37, "Nigeria": 22, "Kuwait": 10,
    }

    ranked_results = []
    for alt in ALTERNATIVES:
        name    = alt["name"]
        country = alt["country"]

        if disrupted_id.lower() == country.lower():
            continue

        transit_days = transit_map.get(country) or TRANSIT_FALLBACK.get(country, 15)

        is_sanctioned = country in sanctioned_countries
        sanction_note = "Excluded: Active OFAC designations found in last 30 days" if is_sanctioned else None

        chokepoints         = country_chokepoints.get(country, [])
        choke_scores        = [corridor_risks.get(cp, 0.0) for cp in chokepoints if isinstance(cp, str)]
        chokepoint_exposure = max(choke_scores) if choke_scores else 0.0

        cost_cit      = discount_citations.get(country)
        cost_index_str = "no current cited figure"
        cost_source    = None
        if cost_cit:
            cost_index_str = cost_cit["value"]
            cost_source    = cost_cit["citation"]

        transit_score    = max(0.0, min(100.0, 100.0 - (float(transit_days) - 5.0) * (100.0 / 35.0)))
        safety_score     = 100.0 - chokepoint_exposure
        reliability_score = float(reliability_scores.get(country, 75))

        final_score = (
            transit_score      * weights.get("transit_speed",       0.4) +
            safety_score       * weights.get("chokepoint_safety",    0.4) +
            reliability_score  * weights.get("supplier_reliability", 0.2)
        )
        if is_sanctioned:
            final_score = -1.0

        ranked_results.append({
            "name":                name,
            "crude_grade":         alt["crude_grade"],
            "transit_days":        transit_days,
            "chokepoint_exposure": chokepoint_exposure,
            "route_corridors":     chokepoints,
            "reliability_score":   reliability_score,
            "is_sanctioned":       is_sanctioned,
            "sanction_note":       sanction_note,
            "cost_index":          cost_index_str,
            "cost_source":         cost_source,
            "transit_score":       round(transit_score, 1),
            "safety_score":        round(safety_score, 1),
            "final_score":         round(final_score, 1) if not is_sanctioned else 0.0,
            "justification":       None,  # filled below if llm_justify
        })

    # Sort: non-sanctioned first by score descending
    ranked_results.sort(key=lambda x: (0 if x["is_sanctioned"] else 1, x["final_score"]), reverse=True)

    # ── LLM justifications (top 3 only, opt-in)
    if llm_justify and llm_api_key:
        non_sanctioned = [r for r in ranked_results if not r["is_sanctioned"]]
        for rank_idx, rec in enumerate(non_sanctioned[:3], start=1):
            rec["justification"] = generate_justification(rec, rank_idx, disrupted_id, llm_api_key)

    return {
        "disrupted_id":                  disrupted_id,
        "required_volume_pct":           required_volume_pct,
        "max_transit_days":              max_transit_days,
        "recommendations":               ranked_results,
        "weights":                       weights,
        "sanctioned_countries_detected": list(sanctioned_countries),
        "formula_description":           "score = (transit_score * 0.4) + (safety_score * 0.4) + (reliability_score * 0.2)",
        "llm_justify":                   llm_justify,
    }


# ──────────────────────────────────────────────────────────────────
# SCENARIO SIMULATOR ENDPOINT
# ──────────────────────────────────────────────────────────────────

@router.get("/scenario-simulate")
def simulate_scenario(
    request: Request,
    scenario_id:    str   = Query(..., description="hormuz_closure / suez_blockage / spr_release / omc_import_cut"),
    severity:       float = Query(1.0, description="Severity fraction between 0.0 and 1.0 (e.g. 0.2 for 20%)"),
    duration_days:  float = Query(30.0, description="Disruption duration in days"),
):
    config_dir: Path = request.app.state.config_dir
    mix_path         = config_dir / "import_mix.json"
    assumptions_path = config_dir / "scenario_assumptions.json"
    buffer_path      = config_dir / "buffer_config.json"

    mix         = _read_config(mix_path)
    assumptions = _read_config(assumptions_path)
    buffer      = _read_config(buffer_path)

    # 1. Check if import_mix shares are configured
    sources   = mix.get("sources", [])
    shares_ok = len(sources) > 0 and all(
        s.get("import_share_pct") is not None for s in sources
    )

    # 2. Get price elasticity and country chokepoint routes
    elasticity          = assumptions.get("price_elasticity", {}).get("crude_to_retail_fuel", 0.15)
    country_chokepoints = assumptions.get("country_chokepoints", {})

    # Calculate corridor share of imports
    corridor_share = None
    if shares_ok:
        corridor_targets = []
        if scenario_id == "hormuz_closure":
            corridor_targets = ["hormuz"]
        elif scenario_id == "suez_blockage":
            corridor_targets = ["suez"]

        if corridor_targets:
            total_share = 0.0
            for src in sources:
                country    = src.get("country")
                chokepoints = country_chokepoints.get(country, [])
                if any(cp in corridor_targets for cp in chokepoints):
                    total_share += float(src.get("import_share_pct", 0.0))
            corridor_share = total_share / 100.0

    # 3. Compute impacts
    refinery_impact = None
    supply_gap_pct  = 0.0

    if scenario_id in ("hormuz_closure", "suez_blockage"):
        if corridor_share is not None:
            supply_gap_pct  = corridor_share * severity * 100.0
            refinery_impact = -supply_gap_pct
        else:
            refinery_impact = None
            supply_gap_pct  = None
    elif scenario_id == "omc_import_cut":
        supply_gap_pct  = severity * 100.0
        refinery_impact = -supply_gap_pct
    elif scenario_id == "spr_release":
        supply_gap_pct  = 0.0
        refinery_impact = 0.0

    # 4. Retail price impact
    price_impact = None
    if supply_gap_pct is not None:
        price_impact = supply_gap_pct * elasticity

    # 5. Buffer coverage
    coverage   = None
    spr_days   = buffer.get("spr", {}).get("estimated_days_cover_current", 0.0)
    refinery_days = buffer.get("refinery_stock", {}).get("days_cover", 0.0)

    if supply_gap_pct is not None and supply_gap_pct > 0:
        coverage = calculate_buffer_coverage_logic(
            supply_gap_pct, duration_days, spr_days, refinery_days
        )

    return {
        "scenario_id":                 scenario_id,
        "severity":                    severity,
        "duration_days":               duration_days,
        "inputs_complete":             shares_ok,
        "refinery_runrate_impact_pct": round(refinery_impact, 2) if refinery_impact is not None else None,
        "retail_price_impact_pct":     round(price_impact, 2)    if price_impact    is not None else None,
        "corridor_share_pct":          round(corridor_share * 100.0, 1) if corridor_share is not None else None,
        "supply_gap_pct":              round(supply_gap_pct, 1)  if supply_gap_pct  is not None else None,
        "coverage":                    coverage,
        "elasticity_assumption":       elasticity,
        "elasticity_citation":         assumptions.get("price_elasticity", {}).get("_note", ""),
    }


# ──────────────────────────────────────────────────────────────────
# PROCUREMENT RECOMMENDATION ENDPOINT
# ──────────────────────────────────────────────────────────────────

@router.get("/procurement-recommend")
def recommend_procurement(
    request:             Request,
    disrupted_id:        str   = Query(..., description="Corridor or supplier country disrupted"),
    required_volume_pct: float = Query(20.0, description="Required supply replacement as % of daily import"),
    max_transit_days:    float = Query(30.0, description="Maximum acceptable transit time in days"),
    llm_justify:         bool  = Query(False, description="Add LLM-generated one-sentence justification to top-3. Requires ANTHROPIC_API_KEY."),
):
    config_dir: Path = request.app.state.config_dir
    csv_dir:    Path = request.app.state.csv_dir

    api_key = _ANTHROPIC_API_KEY if llm_justify else ""

    return rank_alternatives_internal(
        config_dir          = config_dir,
        csv_dir             = csv_dir,
        disrupted_id        = disrupted_id,
        required_volume_pct = required_volume_pct,
        max_transit_days    = max_transit_days,
        llm_justify         = llm_justify,
        llm_api_key         = api_key,
    )
