import os
import sys
import json
import math
import time
import logging
import traceback
from pathlib import Path
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Optional

from agent.knowledge_graph import LightweightKnowledgeGraph

_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

import pandas as pd

from api.routers.buffer_stack import calculate_buffer_coverage_logic

AGENT_THRESHOLD = float(os.environ.get("AGENT_THRESHOLD", 66.0))
AGENT_INTERVAL_SECONDS = int(os.environ.get("AGENT_INTERVAL_SECONDS", 300))
LOOKBACK_DAYS = 7
DECAY_HALF_LIFE_HOURS = 36.0
RAW_SCORE_CEILING = 25.0
DEFAULT_DURATION_DAYS = 30.0

_CSV_DIR = Path(os.environ.get("CSV_OUTPUT_DIR") or str(_BACKEND_DIR / "data" / "macro_events"))
_CONFIG_DIR = Path(os.environ.get("CONFIG_DIR") or str(_BACKEND_DIR / "config"))

logging.basicConfig(
    level=logging.INFO,
    format="[Agent %(asctime)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("response_agent")


def _decay_weight(row_dt: datetime, now: datetime) -> float:
    hours_old = (now - row_dt).total_seconds() / 3600.0
    return math.exp(-math.log(2) * hours_old / DECAY_HALF_LIFE_HOURS)


def compute_corridor_scores(csv_dir: Path) -> dict:
    ALL_CORRIDORS = [
        "hormuz", "red_sea", "suez", "cape_of_good_hope",
        "russia_route", "malacca", "india_domestic",
    ]
    scores = {c: 0.0 for c in ALL_CORRIDORS}

    try:
        from api.db import query_df
        cutoff = date_cls.today() - timedelta(days=LOOKBACK_DAYS)
        df = query_df("""
            SELECT date, title, corridor, severity
            FROM macro_events
            WHERE date >= %s
        """, params=(cutoff,))
    except Exception as e:
        log.warning("Cannot query events DB: %s", e)
        return scores

    if df.empty:
        return scores

    required = {"date", "title", "corridor", "severity"}
    if not required.issubset(df.columns):
        return scores

    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["_dt"])
    df["severity"] = pd.to_numeric(df["severity"], errors="coerce").fillna(0)

    now = datetime.now(timezone.utc)
    for corridor in ALL_CORRIDORS:
        sub = df[df["corridor"] == corridor]
        if sub.empty:
            continue
        raw = sum(
            float(row["severity"]) * _decay_weight(row["_dt"], now)
            for _, row in sub.iterrows()
        )
        scores[corridor] = round(min(raw / RAW_SCORE_CEILING * 100.0, 100.0), 1)

    return scores


def load_state() -> dict:
    try:
        from pipeline.db import get_connection, load_agent_state
        conn = get_connection()
        state = load_agent_state(conn)
        conn.close()
        return state
    except Exception:
        pass

    state_file = _CSV_DIR / "agent_state.json"
    if state_file.exists():
        try:
            with open(state_file, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_state(scores: dict) -> None:
    try:
        from pipeline.db import get_connection, save_agent_state as db_save_agent_state
        conn = get_connection()
        db_save_agent_state(conn, scores)
        conn.close()
    except Exception as e:
        log.warning("Could not save agent state to DB: %s", e)

    _CSV_DIR.mkdir(parents=True, exist_ok=True)
    state_file = _CSV_DIR / "agent_state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump({
            "scores": scores,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _get_corridor_import_share(corridor_id: str, import_mix: dict, country_chokepoints: dict) -> float:
    sources = import_mix.get("sources", [])
    total = 0.0
    for src in sources:
        country = src.get("country", "")
        chokepoints = country_chokepoints.get(country, [])
        if corridor_id in chokepoints:
            total += float(src.get("import_share_pct", 0.0))
    return total / 100.0


def _get_affected_suppliers(corridor_id: str, country_chokepoints: dict) -> list:
    affected = []
    for country, chokepoints in country_chokepoints.items():
        if country.startswith("_"):
            continue
        if isinstance(chokepoints, list) and corridor_id in chokepoints:
            affected.append(country)
    return affected


def _rank_procurement(
    disrupted_corridor: str,
    affected_suppliers: list,
    import_mix: dict,
    assumptions: dict,
    corridor_scores: dict,
) -> list:
    ALTERNATIVES = [
        {"name": "Iraq",         "crude_grade": "Basra Medium/Heavy"},
        {"name": "Saudi Arabia", "crude_grade": "Arab Light/Medium"},
        {"name": "UAE",          "crude_grade": "Murban"},
        {"name": "Kuwait",       "crude_grade": "Kuwait Export"},
        {"name": "Russia",       "crude_grade": "Urals"},
        {"name": "USA",          "crude_grade": "WTI Light Sweet"},
        {"name": "Nigeria",      "crude_grade": "Bonny Light"},
    ]
    TRANSIT_FALLBACK = {
        "Iraq": 12, "Saudi Arabia": 10, "UAE": 8, "Kuwait": 10,
        "Russia": 27, "USA": 37, "Nigeria": 22,
    }

    country_chokepoints = assumptions.get("country_chokepoints", {})
    reliability_scores  = assumptions.get("supplier_reliability", {})
    weights             = assumptions.get("weights", {
        "transit_speed": 0.40, "chokepoint_safety": 0.40, "supplier_reliability": 0.20
    })

    sources = import_mix.get("sources", [])
    transit_map = {
        s.get("country"): s.get("transit_days_typical")
        for s in sources if s.get("country")
    }

    results = []
    for alt in ALTERNATIVES:
        name = alt["name"]
        if name in affected_suppliers:
            continue

        transit_days = transit_map.get(name) or TRANSIT_FALLBACK.get(name, 15)

        chokepoints = country_chokepoints.get(name, [])
        choke_scores = [corridor_scores.get(cp, 0.0) for cp in chokepoints if isinstance(cp, str)]
        chokepoint_exposure = max(choke_scores) if choke_scores else 0.0

        transit_score    = max(0.0, min(100.0, 100.0 - (float(transit_days) - 5.0) * (100.0 / 35.0)))
        safety_score     = 100.0 - chokepoint_exposure
        reliability_score = float(reliability_scores.get(name, 75))

        final_score = (
            transit_score      * weights.get("transit_speed",       0.40) +
            safety_score       * weights.get("chokepoint_safety",    0.40) +
            reliability_score  * weights.get("supplier_reliability", 0.20)
        )

        results.append({
            "name":                name,
            "crude_grade":         alt["crude_grade"],
            "transit_days":        transit_days,
            "chokepoint_exposure": round(chokepoint_exposure, 1),
            "route_corridors":     chokepoints,
            "transit_score":       round(transit_score, 1),
            "safety_score":        round(safety_score, 1),
            "reliability_score":   round(reliability_score, 1),
            "final_score":         round(final_score, 1),
        })

    results.sort(key=lambda x: x["final_score"], reverse=True)
    return results


def _append_alert(row: dict) -> None:
    try:
        from pipeline.db import get_connection, append_alert as db_append_alert
        conn = get_connection()
        db_append_alert(conn, row)
        conn.close()
    except Exception as e:
        log.warning("Could not write alert to DB: %s", e)

    import csv as csv_mod
    _CSV_DIR.mkdir(parents=True, exist_ok=True)
    alerts_file = _CSV_DIR / "auto_triggered_alerts.csv"
    _ALERTS_COLUMNS = [
        "cycle_id", "triggered_at", "corridor", "score_prev", "score_now", "threshold",
        "signal_detected_at", "scenario_computed_at", "recommendation_generated_at",
        "latency_ms", "supply_gap_pct", "coverage_days", "buffer_status",
        "top_recommendation", "top_score", "all_affected_suppliers",
    ]
    write_header = not alerts_file.exists()
    with open(alerts_file, "a", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=_ALERTS_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def _append_score_history(scores: dict, cycle_id: str) -> None:
    try:
        from pipeline.db import get_connection, append_score_history as db_append_score_history
        conn = get_connection()
        db_append_score_history(conn, scores, cycle_id)
        conn.close()
    except Exception as e:
        log.warning("Could not write score history to DB: %s", e)

    import csv as csv_mod
    _CSV_DIR.mkdir(parents=True, exist_ok=True)
    history_file = _CSV_DIR / "corridor_score_history.csv"
    _HISTORY_COLUMNS = ["timestamp", "cycle_id", "corridor", "score", "level"]
    write_header = not history_file.exists()
    with open(history_file, "a", newline="", encoding="utf-8") as f:
        writer = csv_mod.DictWriter(f, fieldnames=_HISTORY_COLUMNS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        ts = datetime.now(timezone.utc).isoformat()
        for corridor, score in scores.items():
            score_val = round(float(score), 1)
            level = "red" if score_val >= 66 else "amber" if score_val >= 33 else "green"
            writer.writerow({
                "timestamp": ts,
                "cycle_id": cycle_id,
                "corridor": corridor,
                "score": score_val,
                "level": level,
            })


def run_cycle(csv_dir: Optional[Path] = None, config_dir: Optional[Path] = None) -> int:
    csv_dir    = csv_dir    or _CSV_DIR
    config_dir = config_dir or _CONFIG_DIR

    cycle_start = datetime.now(timezone.utc)
    cycle_id    = cycle_start.strftime("%Y%m%dT%H%M%SZ")
    alerts_fired = 0

    try:
        log.info("Cycle %s — perceiving corridor scores ...", cycle_id)
        t_signal = datetime.now(timezone.utc)
        current_scores = compute_corridor_scores(csv_dir)
        _append_score_history(current_scores, cycle_id)
        log.info("Scores: %s", {k: v for k, v in current_scores.items() if v > 0})

        state = load_state()
        prev_scores: dict = state.get("scores", {})

        new_crossings = []
        for corridor, score in current_scores.items():
            prev = float(prev_scores.get(corridor, 0.0))
            if prev < AGENT_THRESHOLD <= score:
                new_crossings.append((corridor, prev, score))
                log.info("NEW CROSSING — %s: %.1f → %.1f (threshold %.1f)",
                         corridor, prev, score, AGENT_THRESHOLD)

        if not new_crossings:
            log.info("No new threshold crossings this cycle.")
            save_state(current_scores)
            return 0

        import_mix  = _read_json(config_dir / "import_mix.json")
        assumptions = _read_json(config_dir / "scenario_assumptions.json")
        buffer_cfg  = _read_json(config_dir / "buffer_config.json")

        country_chokepoints = assumptions.get("country_chokepoints", {})
        spr_days            = float(buffer_cfg.get("spr", {}).get("estimated_days_cover_current", 0))
        refinery_days       = float(buffer_cfg.get("refinery_stock", {}).get("days_cover", 0))
        graph = LightweightKnowledgeGraph(config_dir)

        for (corridor, score_prev, score_now) in new_crossings:
            t_act_start = datetime.now(timezone.utc)

            graph_exposure = graph.traverse_disruption(corridor)
            affected_suppliers = graph_exposure.get("affected_suppliers", [])
            gap_fraction = _get_corridor_import_share(corridor, import_mix, country_chokepoints)
            severity_fraction = min(score_now / 100.0, 1.0)
            supply_gap_pct = round(gap_fraction * severity_fraction * 100.0, 1)

            log.info("  [%s] affected suppliers: %s | gap_pct: %.1f%%",
                     corridor, affected_suppliers, supply_gap_pct)

            t_scenario = datetime.now(timezone.utc)
            coverage = None
            if supply_gap_pct > 0:
                try:
                    coverage = calculate_buffer_coverage_logic(
                        supply_gap_pct, DEFAULT_DURATION_DAYS, spr_days, refinery_days
                    )
                except Exception as e:
                    log.warning("  Buffer coverage failed: %s", e)

            coverage_days = None
            buffer_status = "unknown"
            if coverage:
                coverage_days = coverage.get("total_buffer_days")
                buffer_status = coverage.get("status", "unknown")

            t_scenario_done = datetime.now(timezone.utc)

            ranking = _rank_procurement(
                corridor, affected_suppliers,
                import_mix, assumptions, current_scores
            )
            top = ranking[0] if ranking else {}

            t_recommendation = datetime.now(timezone.utc)
            latency_ms = int((t_recommendation - t_signal).total_seconds() * 1000)

            log.info("  [%s] top recommendation: %s (score %.1f) | latency: %dms",
                     corridor, top.get("name", "n/a"), top.get("final_score", 0), latency_ms)

            _append_alert({
                "cycle_id":                    cycle_id,
                "triggered_at":                t_signal.isoformat(),
                "corridor":                    corridor,
                "score_prev":                  round(score_prev, 1),
                "score_now":                   round(score_now, 1),
                "threshold":                   AGENT_THRESHOLD,
                "signal_detected_at":          t_signal.isoformat(),
                "scenario_computed_at":        t_scenario_done.isoformat(),
                "recommendation_generated_at": t_recommendation.isoformat(),
                "latency_ms":                  latency_ms,
                "supply_gap_pct":              supply_gap_pct,
                "coverage_days":               coverage_days,
                "buffer_status":               buffer_status,
                "top_recommendation":          top.get("name", ""),
                "top_score":                   top.get("final_score", ""),
                "all_affected_suppliers":      "|".join(affected_suppliers),
            })
            alerts_fired += 1

        save_state(current_scores)
        log.info("Cycle %s complete. %d alert(s) fired.", cycle_id, alerts_fired)

    except Exception as e:
        log.error("Cycle %s FAILED: %s\n%s", cycle_id, e, traceback.format_exc())

    return alerts_fired


def run_loop() -> None:
    log.info("Agent loop started. Interval: %ds, Threshold: %.1f",
             AGENT_INTERVAL_SECONDS, AGENT_THRESHOLD)
    while True:
        run_cycle()
        log.info("Next cycle in %ds …", AGENT_INTERVAL_SECONDS)
        time.sleep(AGENT_INTERVAL_SECONDS)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Autonomous Disruption Response Agent")
    parser.add_argument("--loop", action="store_true",
                        help="Run continuously (every AGENT_INTERVAL_SECONDS). Default: single cycle then exit.")
    parser.add_argument("--csv-dir", default=None, help="Override CSV_OUTPUT_DIR")
    parser.add_argument("--config-dir", default=None, help="Override CONFIG_DIR")
    args = parser.parse_args()

    csv_dir = Path(args.csv_dir) if args.csv_dir else None
    config_dir = Path(args.config_dir) if args.config_dir else None

    if args.loop:
        run_loop()
    else:
        n = run_cycle(csv_dir=csv_dir, config_dir=config_dir)
        print(f"\nDone. {n} alert(s) triggered this cycle.")
