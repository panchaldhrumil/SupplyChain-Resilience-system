"""
cli.py
======
Argument parser for the live macro pipeline CLI.

Provides:
  build_arg_parser   — returns configured ArgumentParser
  resolve_default_dates — fill in missing from_date / to_date
"""

import argparse
from datetime import date, timedelta

from pipeline.settings import DEFAULT_OUTPUT_DIR, DEFAULT_MAX_ITEMS_PER_QUERY


def build_arg_parser():
    parser = argparse.ArgumentParser(description="Live macro events pipeline for Indian markets")
    parser.add_argument("--output",    default=DEFAULT_OUTPUT_DIR, help="Output folder path")
    parser.add_argument("--from-date", default=None, help="Start date YYYY-MM-DD (defaults to 7 days ago)")
    parser.add_argument("--to-date",   default=None, help="End date YYYY-MM-DD (inclusive; defaults to today)")
    parser.add_argument("--no-enrich", action="store_true",
                         help="Skip full-article fetch + numeric extraction (fast RSS-only mode)")
    parser.add_argument("--max-items-per-query", type=int, default=DEFAULT_MAX_ITEMS_PER_QUERY,
                         help="Cap on items kept per query (default 20)")
    parser.add_argument("--keep-previews", action="store_true",
                         help="Disable the outcome gate; keep pre-event preview/expectation "
                              "articles for data-release categories too")
    parser.add_argument("--no-db", action="store_true",
                         help="Skip Postgres entirely — CSV backups only (dry run; also skips "
                              "the existing-hash lookup, so enrichment runs on everything)")
    parser.add_argument("--llm-classify", action="store_true",
                         help="After enrichment, call Google Gemini (gemini-2.0-flash) to independently "
                              "classify each article's severity (capped sample of 40). Requires GEMINI_API_KEY env var. "
                              "Adds llm_severity, llm_confidence, review_flagged columns to CSV. "
                              "Skipped (no error) if key is missing.")
    return parser


def resolve_default_dates(from_date, to_date):
    today = date.today()
    if from_date is None and to_date is None:
        from_date = (today - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = today.strftime("%Y-%m-%d")
    elif from_date is None:
        from_date = (date.fromisoformat(to_date) - timedelta(days=7)).strftime("%Y-%m-%d")
    elif to_date is None:
        to_date = today.strftime("%Y-%m-%d")
    return from_date, to_date
