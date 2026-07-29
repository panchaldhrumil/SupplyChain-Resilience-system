import sys
import logging
from datetime import datetime, timezone, timedelta

# Reconfigure stdout/stderr for UTF-8
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

from pipeline.cli import build_arg_parser, resolve_default_dates
from pipeline.runner import run

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [run_once] %(levelname)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("run_once")

def main():
    parser = build_arg_parser()
    parser.description = "One-shot pipeline runner for GitHub Actions."
    args = parser.parse_args()

    # Resolve dates (defaults to last 7 days)
    args.from_date, args.to_date = resolve_default_dates(args.from_date, args.to_date)

    log.info("=" * 60)
    log.info("Starting one-shot pipeline run (GitHub Actions mode).")
    log.info("Date range: %s → %s", args.from_date, args.to_date)
    log.info("=" * 60)

    try:
        run(args)
        log.info("Pipeline run completed successfully.")
        sys.exit(0)
    except Exception as exc:
        log.exception("Pipeline run failed: %s", exc)
        sys.exit(1)

if __name__ == "__main__":
    main()
