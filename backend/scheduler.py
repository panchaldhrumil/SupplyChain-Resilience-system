import sys
import os
import time
import json
import logging
import argparse
import threading
from datetime import date, timedelta, datetime, timezone

if getattr(sys.stdout, "encoding", "utf-8").lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if getattr(sys.stderr, "encoding", "utf-8").lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import schedule

from pipeline.runner import run
from pipeline.cli import build_arg_parser
from pipeline.settings import DEFAULT_OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")

_pipeline_args = None

# ── Overlap guard ──────────────────────────────────────────────────────────────
# Prevents a second pipeline run from starting if the previous one hasn't finished.
# Without this, a slow run spanning >6h would cause two concurrent runs.
_run_lock    = threading.Lock()
_is_running  = False

# ── Persistent run log ─────────────────────────────────────────────────────────
# Each run appends one JSON record to data/scheduler_runs.jsonl for audit trail.
_LOG_PATH = os.path.join(_THIS_DIR, "data", "scheduler_runs.jsonl")


def _append_run_log(record: dict):
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as exc:
        log.warning("Could not write run log: %s", exc)


def _run_pipeline():
    global _is_running

    # ── Overlap guard: skip if already running ─────────────────────────────
    with _run_lock:
        if _is_running:
            log.warning(
                "OVERLAP GUARD: A pipeline run is already in progress. "
                "Skipping this scheduled slot to avoid concurrent runs."
            )
            return
        _is_running = True

    now_utc = datetime.now(timezone.utc)
    today_str    = now_utc.strftime("%Y-%m-%d")
    week_ago_str = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")

    log.info("=" * 60)
    log.info("Pipeline run starting at %s UTC", now_utc.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Date range: %s → %s (7-day rolling window)", week_ago_str, today_str)
    log.info("=" * 60)

    start_ts = now_utc
    status   = "unknown"
    error    = None

    try:
        import copy
        args = copy.copy(_pipeline_args) if _pipeline_args is not None else build_arg_parser().parse_args([])
        args.from_date = week_ago_str
        args.to_date   = today_str
        run(args)
        status = "success"
        log.info("Pipeline run completed successfully.")
    except Exception as exc:
        status = "failed"
        error  = str(exc)
        log.exception("Pipeline run failed: %s", exc)
    finally:
        # Release lock regardless of outcome
        with _run_lock:
            _is_running = False

    end_ts   = datetime.now(timezone.utc)
    duration = round((end_ts - start_ts).total_seconds(), 1)

    run_record = {
        "start_time":   start_ts.isoformat(),
        "end_time":     end_ts.isoformat(),
        "duration_sec": duration,
        "status":       status,
        "date_from":    week_ago_str,
        "date_to":      today_str,
        "error":        error,
    }
    _append_run_log(run_record)

    log.info(
        "Run log: status=%s  duration=%.1fs  → %s",
        status, duration, _LOG_PATH,
    )
    log.info("Next runs scheduled at: 00:00, 06:00, 12:00, 18:00 UTC")


def _run_cleanup():
    """Automated 4-hour cleanup: purges old DB logs and resets Qdrant vectors."""
    log.info("Starting automated 4-hour cleanup of old Neon DB logs and Qdrant vectors...")
    try:
        from pipeline.db import get_connection, cleanup_db_logs
        from pipeline.qdrant_store import clear_qdrant_collection
        conn = get_connection()
        if conn:
            cleanup_db_logs(conn, keep_days=3)
            conn.close()
        clear_qdrant_collection()
        log.info("4-hour DB & Qdrant cleanup completed successfully.")
    except Exception as exc:
        log.exception("4-hour cleanup failed: %s", exc)


def _register_schedule():
    # Populate Neon DB & Qdrant every 1 hour
    schedule.every(1).hours.do(_run_pipeline)
    # Cleanup old logs & Qdrant vectors every 4 hours
    schedule.every(4).hours.do(_run_cleanup)
    log.info("Registered 1-hour population schedule & 4-hour DB/Qdrant cleanup schedule.")


def is_pipeline_running() -> bool:
    return _is_running


def trigger_manual_run():
    t = threading.Thread(target=_run_pipeline, daemon=True, name="manual-pipeline-run")
    t.start()
    return t


def start_scheduler_thread(interval_hours: int = 1, run_now: bool = True):
    def _loop():
        if run_now:
            log.info("Background pipeline scheduler: triggering initial run...")
            _run_pipeline()

        schedule.every(interval_hours).hours.do(_run_pipeline)
        schedule.every(4).hours.do(_run_cleanup)
        log.info("Background pipeline scheduler loop active (interval: %d hour(s)).", interval_hours)

        while True:
            try:
                schedule.run_pending()
            except Exception as exc:
                log.exception("Error in schedule execution: %s", exc)
            time.sleep(30)

    t = threading.Thread(target=_loop, daemon=True, name="pipeline-scheduler")
    t.start()
    return t


def main():
    global _pipeline_args

    parser = build_arg_parser()
    parser.description = "6-hour recurring scheduler for the India Energy Resilience news pipeline."
    parser.add_argument(
        "--run-now", action="store_true",
        help="Fire one pipeline run immediately on startup before waiting for the schedule.",
    )
    args = parser.parse_args()

    _pipeline_args = args

    log.info("India Energy Resilience — News Pipeline Scheduler")
    log.info("Output dir : %s", args.output)
    log.info("Enrichment : %s", "OFF (--no-enrich)" if args.no_enrich else "ON")
    log.info("Postgres   : %s", "OFF (--no-db)" if args.no_db else "ON (if available)")
    log.info("Run log    : %s", _LOG_PATH)
    log.info("Overlap guard : ENABLED — concurrent runs will be skipped.")

    if args.run_now:
        log.info("--run-now flag set: firing immediate pipeline run before first scheduled slot.")
        _run_pipeline()

    _register_schedule()

    log.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    main()

