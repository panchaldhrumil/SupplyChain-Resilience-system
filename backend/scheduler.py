import sys
import os
import time
import logging
import argparse
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


def _run_pipeline():
    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    week_ago_str = (now_utc - timedelta(days=7)).strftime("%Y-%m-%d")

    log.info("=" * 60)
    log.info("Pipeline run starting at %s UTC", now_utc.strftime("%Y-%m-%d %H:%M:%S"))
    log.info("Fetching articles from %s to %s", week_ago_str, today_str)
    log.info("=" * 60)

    import copy
    args = copy.copy(_pipeline_args)
    args.from_date = week_ago_str
    args.to_date = today_str

    try:
        run(args)
        log.info("Pipeline run completed successfully.")
    except Exception as exc:
        log.exception("Pipeline run failed: %s", exc)

    log.info("Next runs scheduled at: 00:00, 06:00, 12:00, 18:00 UTC")


SCHEDULE_TIMES_UTC = ["00:00", "06:00", "12:00", "18:00"]


def _register_schedule():
    for t in SCHEDULE_TIMES_UTC:
        schedule.every().day.at(t).do(_run_pipeline)
    log.info(
        "Registered fixed 6-hour schedule (UTC): %s",
        "  ".join(SCHEDULE_TIMES_UTC),
    )


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
