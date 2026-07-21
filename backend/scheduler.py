"""
scheduler.py
============
Recurring 6-hour news-pipeline scheduler for the India Energy Resilience dashboard.

Schedule (fixed wall-clock, UTC):
  00:00  06:00  12:00  18:00
i.e. the equivalent of cron expression: 0 */6 * * *

Each run:
  1. Recomputes the date range as (today - 7 days) → today, so the window
     always starts from "now - 7 days" — never stale.
  2. Delegates entirely to pipeline.runner.run(), which:
       fetch → deduplicate → enrich → write CSV backups
     Raw `date` (published_at) and `severity` are the only values written to
     storage.  Read-time exponential decay is computed by risk_corridors.py on
     every API request — this scheduler never touches that logic.
  3. Does NOT purge articles independently — the 7-day query window implicitly
     keeps articles from the last 7 days; anything older rolls out naturally on
     the next write.  This is separate from the 36-hour decay half-life.

Usage (run in the background, from the backend/ directory):
  python scheduler.py                  # default: no enrichment, CSV-only mode
  python scheduler.py --no-enrich      # fast RSS-only mode
  python scheduler.py --help           # full list of pipeline CLI flags

To run as a background service on Windows (example with Task Scheduler), point
it at:
  python <path_to_backend>/scheduler.py

On Linux/Mac you can also use cron:
  0 */6 * * *  cd /path/to/backend && venv/bin/python scheduler.py
"""

import sys
import os
import time
import logging
import argparse
from datetime import date, timedelta, datetime, timezone

# --------------------------------------------------------------------------
# Force UTF-8 stdout/stderr on Windows
# --------------------------------------------------------------------------
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

# --------------------------------------------------------------------------
# Ensure backend/ is on sys.path so pipeline.* imports work when run from
# any directory, e.g.  `python backend/scheduler.py`
# --------------------------------------------------------------------------
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)

import schedule

from pipeline.runner import run
from pipeline.cli import build_arg_parser, resolve_default_dates
from pipeline.settings import DEFAULT_OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [scheduler] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("scheduler")


# --------------------------------------------------------------------------
# Shared CLI flags (passed through to the underlying pipeline run)
# --------------------------------------------------------------------------
_pipeline_args = None   # populated in main() after arg parse


def _run_pipeline():
    """
    One complete pipeline pass.
    Recomputes the date range fresh on every call so each run always fetches
    the latest 7 days of articles — never a cached or stale window.
    """
    now_utc = datetime.now(timezone.utc)
    today_str     = now_utc.strftime("%Y-%m-%d")
    week_ago_str  = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")

    log.info("=" * 60)
    log.info("Pipeline run starting at %s UTC", now_utc.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Fetching articles from %s to %s", week_ago_str, today_str)
    log.info("=" * 60)

    # Build a fresh args namespace for this run
    # (re-parse from _pipeline_args defaults so CLI flags like --no-enrich carry through)
    import copy
    args = copy.copy(_pipeline_args)
    args.from_date = week_ago_str
    args.to_date   = today_str

    try:
        run(args)
        log.info("Pipeline run completed successfully.")
    except Exception as exc:
        log.exception("Pipeline run failed: %s", exc)

    log.info("Next runs scheduled at: 00:00, 06:00, 12:00, 18:00 UTC")


# --------------------------------------------------------------------------
# Schedule: four fixed wall-clock times per day (UTC) = cron 0 */6 * * *
# --------------------------------------------------------------------------
SCHEDULE_TIMES_UTC = ["00:00", "06:00", "12:00", "18:00"]


def _register_schedule():
    for t in SCHEDULE_TIMES_UTC:
        schedule.every().day.at(t).do(_run_pipeline)
    log.info(
        "Registered fixed 6-hour schedule (UTC): %s  [equivalent to cron: 0 */6 * * *]",
        "  ".join(SCHEDULE_TIMES_UTC),
    )


def main():
    global _pipeline_args

    # Parse pipeline-passthrough flags (same CLI as live_macro_pipeline.py)
    parser = build_arg_parser()
    parser.description = (
        "6-hour recurring scheduler for the India Energy Resilience news pipeline.\n"
        "Runs at 00:00, 06:00, 12:00, 18:00 UTC (cron: 0 */6 * * *).\n"
        "All pipeline flags below are forwarded to each scheduled run."
    )
    parser.add_argument(
        "--run-now", action="store_true",
        help="Fire one pipeline run immediately on startup before waiting for the schedule.",
    )
    args = parser.parse_args()

    # resolve_default_dates is intentionally NOT called here — each scheduled
    # run calls it fresh so the window always ends at "now", not at start time.
    _pipeline_args = args

    log.info("India Energy Resilience — News Pipeline Scheduler")
    log.info("Output dir : %s", args.output)
    log.info("Enrichment : %s", "OFF (--no-enrich)" if args.no_enrich else "ON")
    log.info("Postgres   : %s", "OFF (--no-db)" if args.no_db else "ON (if available)")

    if args.run_now:
        log.info("--run-now flag set: firing immediate pipeline run before first scheduled slot.")
        _run_pipeline()

    _register_schedule()

    log.info("Scheduler running. Press Ctrl+C to stop.")
    while True:
        schedule.run_pending()
        time.sleep(30)   # check every 30 s — fine-grained enough for minute-level scheduling


if __name__ == "__main__":
    main()
