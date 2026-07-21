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

# Gemini key loaded from environment (never hardcoded)
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")


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
        from google import genai
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
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents=prompt,
        )
        return response.text.strip()
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

    # ── Apply disrupted-corridor penalty BEFORE scoring
    # When the user selects a corridor as disrupted, force its live risk to 100
    # so that suppliers routing through it receive a correct safety_score penalty.
    KNOWN_CORRIDOR_IDS = {
        "hormuz", "suez", "russia_route", "cape_of_good_hope",
        "red_sea", "bab_el_mandeb", "malacca",
    }
    disrupted_corridor = disrupted_id.lower() if disrupted_id.lower() in KNOWN_CORRIDOR_IDS else None
    if disrupted_corridor:
        corridor_risks[disrupted_corridor] = 100.0
        # bab_el_mandeb and red_sea are the same physical strait operationally
        if disrupted_corridor == "red_sea":
            corridor_risks["bab_el_mandeb"] = 100.0
        elif disrupted_corridor == "bab_el_mandeb":
            corridor_risks["red_sea"] = 100.0

    # ── Read configurable sanctions penalty (not hardcoded)
    sanctions_multiplier = float(
        assumptions.get("sanctions_config", {}).get("active_sanctions_score_multiplier", 0.5)
    )

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

    sources     = mix.get("sources", [])
    transit_map = {s.get("country"): s.get("transit_days_typical") for s in sources if s.get("country")}

    # ── Route data from import_mix.json — single source of truth for chokepoints + display
    route_map = {
        s.get("country"): s.get("route")
        for s in sources
        if s.get("country") and s.get("route")
    }

    country_chokepoints = assumptions.get("country_chokepoints", {})
    reliability_scores  = assumptions.get("supplier_reliability", {})
    weights             = assumptions.get("weights", {
        "transit_speed": 0.4, "chokepoint_safety": 0.4, "supplier_reliability": 0.2
    })

    TRANSIT_FALLBACK = {
        "Iraq": 12, "Saudi Arabia": 10, "Russia": 27, "UAE": 8,
        "USA": 37, "Nigeria": 22, "Kuwait": 10,
    }

    ranked_results = []
    scoring_errors = []

    for alt in ALTERNATIVES:
        name    = alt["name"]
        country = alt["country"]

        try:
            # Exclude the disrupted country (only when disrupted_id is a country, not a corridor)
            if not disrupted_corridor and disrupted_id.lower() == country.lower():
                continue

            transit_days = transit_map.get(country) or TRANSIT_FALLBACK.get(country, 15)

            is_sanctioned = country in sanctioned_countries
            # OFAC caution: scored with penalty, NOT excluded
            penalty_display = round((1.0 - sanctions_multiplier) * 100)
            sanction_note   = (
                f"SANCTIONS CAUTION: Active OFAC designations found in last 30 days. "
                f"Score penalised by {penalty_display}% (configurable in scenario_assumptions.json)."
            ) if is_sanctioned else None

            # Use route-based chokepoints (from import_mix.json) as the single source of truth;
            # fall back to country_chokepoints from assumptions if route data missing
            route_data   = route_map.get(country)
            route_chokes = route_data.get("chokepoints", []) if route_data else None
            chokepoints  = route_chokes if route_chokes is not None else country_chokepoints.get(country, [])

            choke_scores        = [corridor_risks.get(cp, 0.0) for cp in chokepoints if isinstance(cp, str)]
            chokepoint_exposure = max(choke_scores) if choke_scores else 0.0

            cost_cit       = discount_citations.get(country)
            cost_index_str = "no current cited figure"
            cost_source    = None
            if cost_cit:
                cost_index_str = cost_cit["value"]
                cost_source    = cost_cit["citation"]

            transit_score     = max(0.0, min(100.0, 100.0 - (float(transit_days) - 5.0) * (100.0 / 35.0)))
            safety_score      = 100.0 - chokepoint_exposure
            reliability_score = float(reliability_scores.get(country, 75))

            final_score = (
                transit_score      * weights.get("transit_speed",       0.4) +
                safety_score       * weights.get("chokepoint_safety",    0.4) +
                reliability_score  * weights.get("supplier_reliability", 0.2)
            )
            # Apply configurable OFAC penalty multiplier (not a hard exclusion)
            if is_sanctioned:
                final_score = final_score * sanctions_multiplier

            ranked_results.append({
                "name":                name,
                "crude_grade":         alt["crude_grade"],
                "transit_days":        transit_days,
                "chokepoint_exposure": chokepoint_exposure,
                "route_corridors":     chokepoints,
                "route":               route_data,
                "reliability_score":   reliability_score,
                "is_sanctioned":       is_sanctioned,
                "sanction_note":       sanction_note,
                "cost_index":          cost_index_str,
                "cost_source":         cost_source,
                "transit_score":       round(transit_score, 1),
                "safety_score":        round(safety_score, 1),
                "final_score":         round(final_score, 1),
                "justification":       None,  # filled below if llm_justify
            })
        except Exception as country_err:
            scoring_errors.append({"country": country, "error": str(country_err)})

    # Sort all candidates by final_score descending (sanctioned countries ranked normally, just penalised)
    ranked_results.sort(key=lambda x: x["final_score"], reverse=True)

    # ── LLM justifications (top 3 only, opt-in)
    if llm_justify and llm_api_key:
        for rank_idx, rec in enumerate(ranked_results[:3], start=1):
            rec["justification"] = generate_justification(rec, rank_idx, disrupted_id, llm_api_key)

    penalty_pct = round((1.0 - sanctions_multiplier) * 100)
    return {
        "disrupted_id":                  disrupted_id,
        "disrupted_corridor_applied":    disrupted_corridor,
        "required_volume_pct":           required_volume_pct,
        "max_transit_days":              max_transit_days,
        "recommendations":               ranked_results,
        "weights":                       weights,
        "sanctioned_countries_detected": list(sanctioned_countries),
        "formula_description": (
            f"score = (transit_score × 0.4) + (safety_score × 0.4) + (reliability_score × 0.2). "
            f"Active OFAC sanctions apply a {penalty_pct}% score penalty "
            f"(sanctions_config.active_sanctions_score_multiplier in scenario_assumptions.json)."
        ),
        "llm_justify":                   llm_justify,
        "scoring_errors":                scoring_errors if scoring_errors else None,
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

    # Calculate corridor share of imports (standard chokepoint approach for corridor scenarios)
    corridor_share = None
    if shares_ok:
        corridor_targets = []
        if scenario_id in ("hormuz_closure", "persian_gulf_conflict"):
            corridor_targets = ["hormuz"]
        elif scenario_id == "suez_blockage":
            corridor_targets = ["suez"]

        if corridor_targets:
            total_share = 0.0
            for src in sources:
                country     = src.get("country")
                chokepoints = country_chokepoints.get(country, [])
                if any(cp in corridor_targets for cp in chokepoints):
                    total_share += float(src.get("import_share_pct", 0.0))
            corridor_share = total_share / 100.0

    # 3. Compute supply gap and refinery impact per scenario
    refinery_impact = None
    supply_gap_pct  = 0.0

    if scenario_id in ("hormuz_closure", "suez_blockage", "persian_gulf_conflict"):
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

    elif scenario_id == "russia_sanctions_escalation":
        # Full / partial secondary sanctions enforcement on Russian crude
        russia_share = next(
            (float(s.get("import_share_pct", 0.0)) for s in sources if s.get("country") == "Russia"),
            17.9,  # fallback to known Q1-2026 figure
        )
        supply_gap_pct  = russia_share * severity
        refinery_impact = -supply_gap_pct

    elif scenario_id == "red_sea_disruption":
        # Houthi / Bab-el-Mandeb closure — partial routing factors for each supplier
        red_sea_routing = assumptions.get("red_sea_routing", {"Saudi Arabia": 0.3, "USA": 1.0})
        if shares_ok:
            effective_share = sum(
                float(s.get("import_share_pct", 0.0)) * red_sea_routing.get(s.get("country", ""), 0.0)
                for s in sources
            )
            corridor_share  = effective_share / 100.0
            supply_gap_pct  = corridor_share * severity * 100.0
            refinery_impact = -supply_gap_pct
        else:
            corridor_share  = None
            supply_gap_pct  = None
            refinery_impact = None

    elif scenario_id == "opec_production_cut":
        # Coordinated OPEC+ output cut across all Gulf member suppliers
        opec_members = {"Iraq", "Saudi Arabia", "UAE", "Kuwait"}
        if shares_ok:
            opec_share      = sum(float(s.get("import_share_pct", 0.0)) for s in sources if s.get("country") in opec_members)
            corridor_share  = opec_share / 100.0
            supply_gap_pct  = corridor_share * severity * 100.0
            refinery_impact = -supply_gap_pct
        else:
            corridor_share  = None
            supply_gap_pct  = None
            refinery_impact = None

    elif scenario_id == "domestic_refinery_outage":
        # Internal processing capacity loss — independent of import availability
        supply_gap_pct  = severity * 100.0
        refinery_impact = -supply_gap_pct

    elif scenario_id == "rupee_depreciation_shock":
        # Currency shock: no volume disruption, import cost rises proportionally in INR terms
        supply_gap_pct  = 0.0
        refinery_impact = 0.0

    # 3b. Scenario-specific extra context (typed metadata for the frontend)
    extra_impact: dict = {}
    if scenario_id == "rupee_depreciation_shock":
        depr_pct = round(severity * 100.0, 1)
        extra_impact = {
            "type": "cost_shock",
            "import_cost_increase_pct": depr_pct,
            "description": (
                f"A {depr_pct}% INR depreciation vs USD raises India's crude import bill by "
                f"{depr_pct}% in rupee terms with no change in import volume. "
                f"At ~4.8 mb/d imports × ~$75/bbl, every 1% INR fall \u2248 \u20b92,700 Cr additional annual cost."
            ),
        }
    elif scenario_id == "russia_sanctions_escalation":
        russia_share_val = next((float(s.get("import_share_pct", 0.0)) for s in sources if s.get("country") == "Russia"), 17.9)
        extra_impact = {
            "type": "sanctions_shock",
            "sanctioned_country": "Russia",
            "ofac_connection": True,
            "supplier_share_pct": round(russia_share_val, 1),
            "description": "Full secondary sanctions enforcement on Russian crude forces India to replace its largest discount-supplier under emergency conditions. OFAC SDN watchlist is the live data source feeding this classification.",
        }
    elif scenario_id == "red_sea_disruption":
        extra_impact = {
            "type": "transit_shock",
            "affected_route": "Bab-el-Mandeb / Red Sea",
            "transit_extension_days": 14,
            "reroute_via": "Cape of Good Hope",
            "description": "Houthi-style attacks force vessels away from the Red Sea. Saudi Yanbu exports (~30% of Saudi supply) and all US-origin cargoes must reroute via Cape of Good Hope, adding ~14 transit days and significantly raising freight costs.",
        }
    elif scenario_id == "persian_gulf_conflict":
        gulf_countries = ["Iraq", "Saudi Arabia", "UAE", "Kuwait"]
        gulf_share_val  = round(sum(float(s.get("import_share_pct", 0.0)) for s in sources if s.get("country") in gulf_countries), 1) if shares_ok else None
        extra_impact = {
            "type": "multi_supplier_shock",
            "affected_countries": gulf_countries,
            "combined_share_pct": gulf_share_val,
            "description": "A broader Persian Gulf conflict simultaneously disrupts all four major Gulf suppliers — the true worst-case stress test for India's crude supply security, eclipsing a Hormuz-only closure.",
        }
    elif scenario_id == "opec_production_cut":
        opec_list      = ["Iraq", "Saudi Arabia", "UAE", "Kuwait"]
        opec_share_val = round(sum(float(s.get("import_share_pct", 0.0)) for s in sources if s.get("country") in opec_list), 1) if shares_ok else None
        extra_impact = {
            "type": "price_and_volume_shock",
            "affected_members": opec_list,
            "combined_share_pct": opec_share_val,
            "description": "Coordinated OPEC+ output cut simultaneously reduces available Gulf crude volume and elevates global benchmark prices, creating a dual supply-and-cost pressure on India's refiners.",
        }
    elif scenario_id == "domestic_refinery_outage":
        extra_impact = {
            "type": "domestic_shock",
            "description": "A domestic refinery system outage (fire, technical failure, or industrial action) reduces India's crude processing capacity regardless of import availability. Procurement diversification cannot resolve this constraint — the bottleneck is downstream, not upstream.",
        }

    # 4. Retail price impact
    price_impact = None
    if supply_gap_pct is not None:
        price_impact = supply_gap_pct * elasticity

    # 5. Buffer coverage
    coverage      = None
    spr_days      = buffer.get("spr", {}).get("estimated_days_cover_current", 0.0)
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
        "extra_impact":                extra_impact,
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
    llm_justify:         bool  = Query(False, description="Add LLM-generated one-sentence justification to top-3. Requires GEMINI_API_KEY."),
):
    config_dir: Path = request.app.state.config_dir
    csv_dir:    Path = request.app.state.csv_dir

    api_key = _GEMINI_API_KEY if llm_justify else ""

    return rank_alternatives_internal(
        config_dir          = config_dir,
        csv_dir             = csv_dir,
        disrupted_id        = disrupted_id,
        required_volume_pct = required_volume_pct,
        max_transit_days    = max_transit_days,
        llm_justify         = llm_justify,
        llm_api_key         = api_key,
    )


# ──────────────────────────────────────────────────────────────────
# SCENARIO CATALOGUE ENDPOINT
# ──────────────────────────────────────────────────────────────────

_SCENARIO_CATALOGUE = [
    # Physical Corridor Disruptions
    {"id": "hormuz_closure",             "label": "Strait of Hormuz Closure",           "category": "Physical",  "corridor": "hormuz",        "description": "Iran/GCC tension closes the world's most critical oil chokepoint, blocking ~50% of India's crude imports."},
    {"id": "suez_blockage",              "label": "Suez Canal Blockage",                "category": "Physical",  "corridor": "suez",          "description": "Canal grounding or military action blocks the Suez shortcut, rerouting ships around Africa (+10\u201314 days)."},
    {"id": "red_sea_disruption",         "label": "Red Sea / Bab-el-Mandeb Disruption", "category": "Physical",  "corridor": "bab_el_mandeb", "description": "Houthi-style attacks force Saudi Yanbu exports and US-origin cargoes to reroute via Cape of Good Hope (+14 transit days)."},
    {"id": "persian_gulf_conflict",      "label": "Persian Gulf Regional Conflict",     "category": "Physical",  "corridor": "hormuz",        "description": "Broader Gulf conflict simultaneously disrupts Iraq + Saudi + UAE + Kuwait \u2014 the worst-case stress test for India."},
    # Political / Sanctions
    {"id": "russia_sanctions_escalation","label": "Russia Sanctions Escalation",        "category": "Political", "corridor": "russia_route",  "description": "Secondary sanctions enforcement forces India to rapidly replace Russian crude (17.9% of imports) under emergency conditions."},
    {"id": "opec_production_cut",        "label": "OPEC+ Production Cut",               "category": "Political", "corridor": None,            "description": "Coordinated OPEC+ output cut reduces available Gulf crude volume and simultaneously raises global prices."},
    {"id": "omc_import_cut",             "label": "General OMC Import Curtailment",     "category": "Political", "corridor": None,            "description": "Indian Oil Marketing Companies voluntarily or mandatorily reduce crude imports by a given percentage."},
    # Domestic / Financial
    {"id": "domestic_refinery_outage",   "label": "Domestic Refinery Outage",           "category": "Domestic",  "corridor": None,            "description": "Fire, technical failure, or industrial action reduces domestic refinery capacity regardless of import availability."},
    {"id": "rupee_depreciation_shock",   "label": "Rupee Depreciation Shock (\u20b9/USD)", "category": "Financial", "corridor": None,            "description": "INR depreciation raises the rupee-denominated import bill with no change in crude import volume."},
    {"id": "spr_release",                "label": "Strategic Reserve (SPR) Drawdown",   "category": "Domestic",  "corridor": None,            "description": "Government releases crude from Strategic Petroleum Reserves to compensate for an import shortfall."},
]


@router.get("/scenario-list")
def list_scenarios():
    """Return the full catalogue of available scenario IDs with labels, categories, and descriptions."""
    return {"scenarios": _SCENARIO_CATALOGUE, "total": len(_SCENARIO_CATALOGUE)}
