"""
runner.py
=========
Orchestrates the full pipeline run — fetch → dedup → enrich → persist.

Provides:
  run — execute a complete pipeline pass given parsed CLI args
"""

import os
import sys
import time
import traceback
from collections import defaultdict

# ---- Force UTF-8 output on Windows (avoids UnicodeEncodeError for ₹, →, etc.) ----
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd


from pipeline.config import MACRO_QUERIES
from pipeline.settings import (
    REQUEST_DELAY,
    GEMINI_API_KEY,
)
from pipeline.collectors import (
    fetch_query,
    fetch_official_rss,
    fetch_ofac_sanctions_list,
    fetch_commodity_prices,
)
from pipeline.processors import _deduplicate_day_group
from pipeline.enrichers import enrich_dataframe, fetch_existing_hashes
from pipeline.persistence import write_csv_outputs, to_db_macro_rows
from pipeline import logger

# db_writer — lazy import; only present when running with Postgres
try:
    import db_writer  # type: ignore[import]
except ModuleNotFoundError:
    db_writer = None  # type: ignore[assignment]


def run(args):
    """
    Execute one complete pipeline pass.
    args — namespace returned by build_arg_parser().parse_args() after
           resolve_default_dates() has been applied.
    """
    os.makedirs(args.output, exist_ok=True)
    print(f"Output dir : {args.output}")
    print(f"Date range : {args.from_date} to {args.to_date}")
    print(f"Queries    : {len(MACRO_QUERIES)}")
    print(f"Max/query  : {args.max_items_per_query}")
    print(f"Enrichment : {'OFF (--no-enrich)' if args.no_enrich else 'ON (skips already-known articles)'}")
    print(f"Outcome gate: {'OFF (--keep-previews)' if args.keep_previews else 'ON (results only for RBI/Macro/Fed/CB)'}")
    print("=" * 60)

    # ---- Open DB connection early (parent process) ----
    conn = None
    run_id = None
    if not args.no_db and db_writer is not None:
        try:
            conn = db_writer.get_connection()
            run_id = logger.start_run(conn, "live_macro_pipeline")
        except RuntimeError as e:
            print(f"DB connection failed: {e}")
            print("Continuing in CSV-only mode for this run.")
            conn = None
    elif not args.no_db and db_writer is None:
        print("[!] db_writer module not found — running in CSV-only mode (--no-db behaviour).")

    existing_hashes = fetch_existing_hashes(conn) if conn else set()

    # ---- Fetch ----
    all_items  = []
    seen_links = set()

    # Official RSS feeds first (highest priority)
    print("\nFetching official RSS feeds...")
    official_items = fetch_official_rss(args.from_date, to_date_str=args.to_date)
    for item in official_items:
        if item["link"] not in seen_links:
            seen_links.add(item["link"])
            all_items.append(item)
    print(f"Official RSS: {len(official_items)} items fetched")

    for idx, (category, query) in enumerate(MACRO_QUERIES, 1):
        print(f"[{idx}/{len(MACRO_QUERIES)}] {category} | {query[:60]}...")
        items = fetch_query(category, query, args.from_date, to_date_str=args.to_date,
                             max_items=args.max_items_per_query,
                             keep_previews=args.keep_previews)
        print(f"      -> {len(items)} items")

        for item in items:
            if item["link"] not in seen_links:
                seen_links.add(item["link"])
                all_items.append(item)

        time.sleep(REQUEST_DELAY)

    print(f"\nFetched {len(all_items)} unique items before deduplication")

    df = pd.DataFrame(all_items)
    if df.empty:
        print("No items fetched. Check network / date range.")
        if conn:
            logger.finish_run(conn, run_id, 0, 0, 0, status="success")
            conn.close()
        return

    # ---- Single-pass dedup: Jaccard clustering + official-source priority ----
    df["_group"] = df["category"] + "|" + df["date"]
    filtered_rows = []
    for group_key, group_df in df.groupby("_group", sort=False):
        items_in_group = group_df.drop(columns=["_group"]).to_dict("records")
        kept = _deduplicate_day_group(items_in_group)
        filtered_rows.extend(kept)

    df_filtered = pd.DataFrame(filtered_rows)
    df_filtered = df_filtered.sort_values(["date", "category"], ascending=[False, True])
    df_filtered = df_filtered.drop(columns=["_group"], errors="ignore")
    df_filtered = df_filtered.reset_index(drop=True)

    removed = len(all_items) - len(df_filtered)
    print(f"After deduplication: {len(df_filtered)} items ({removed} removed)")

    # ---- Enrichment ----
    llm_key = GEMINI_API_KEY if args.llm_classify else ""
    if not args.no_enrich:
        df_filtered = enrich_dataframe(
            df_filtered,
            existing_hashes=existing_hashes,
            llm_classify=args.llm_classify,
            llm_api_key=llm_key,
        )
    else:
        for col in ["extracted_numbers", "key_takeaway", "article_text_snippet", "fetch_status",
                    "llm_severity", "llm_confidence", "review_flagged", "llm_status"]:
            df_filtered[col] = ""

    out_cols = ["date", "title", "source", "link", "category",
                "affected_sectors", "affected_companies",
                "buffer_layer", "corridor", "severity",
                "extracted_numbers", "key_takeaway",
                "article_text_snippet", "fetch_status",
                # LLM validation columns (present only when --llm-classify was used)
                "llm_severity", "llm_confidence", "is_genuine_disruption",
                "llm_corridor", "llm_justification", "review_flagged", "llm_status"]
    df_filtered = df_filtered[[c for c in out_cols if c in df_filtered.columns]]

    # ---- CSV backups ----
    write_csv_outputs(df_filtered, args.output)

    # ---- Ancillary data fetches ----
    fetch_ofac_sanctions_list(args.output)
    fetch_commodity_prices(args.output)

    # ---- Postgres upsert ----
    if args.no_db:
        print("\n--no-db set: skipping Postgres upsert.")
        print("Done.")
        return

    if conn is None:
        print("\nNo DB connection available — CSV backups were written successfully, "
              "but nothing was upserted to Postgres.")
        return

    print("\nUpserting to Postgres...")
    db_status = "success"
    error_message = None
    inserted = skipped = 0

    try:
        db_rows = to_db_macro_rows(df_filtered)
        inserted, skipped = db_writer.upsert_macro_events(conn, db_rows)
        print(f"DB upsert done. Fetched: {len(db_rows)}, Inserted: {inserted}, Skipped: {skipped}")
    except Exception as e:
        db_status = "failed"
        error_message = str(e)
        print(f"DB upsert FAILED: {e}\n{traceback.format_exc()}")
    finally:
        logger.finish_run(
            conn, run_id, len(df_filtered), inserted, skipped,
            status=db_status, error_message=error_message,
        )
        conn.close()

    print(f"\nDone. Run id: {run_id}")
