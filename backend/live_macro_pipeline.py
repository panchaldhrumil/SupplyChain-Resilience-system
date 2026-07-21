import sys as _sys
if getattr(_sys.stdout, "encoding", "utf-8").lower() != "utf-8":
    try:
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io as _io
        _sys.stdout = _io.TextIOWrapper(_sys.stdout.buffer, encoding="utf-8", errors="replace")
if getattr(_sys.stderr, "encoding", "utf-8").lower() != "utf-8":
    try:
        _sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        import io as _io
        _sys.stderr = _io.TextIOWrapper(_sys.stderr.buffer, encoding="utf-8", errors="replace")

from pipeline.config import (
    MACRO_QUERIES,
    IMPACT_MAP,
    CORRIDOR_IMPACT_MAP,
    OFFICIAL_SOURCES,
    NEWS_SOURCE_PRIORITY,
    RELEVANCE_KEYWORDS,
    STOP_WORDS,
    GEOPOLITICAL_RELEVANCE_WORDS,
    ELECTION_NOISE_WORDS,
    DATA_RELEASE_CATEGORIES,
    PREVIEW_NOISE_WORDS,
    OUTCOME_SIGNAL_WORDS,
    CATEGORY_ANCHORS,
    NUMERIC_VALUE_RE,
    NUMERIC_PATTERNS,
    TAKEAWAY_MARKERS,
    OFFICIAL_RSS_FEEDS,
    _OFAC_SDN_URL,
    _OFAC_SDN_COLS,
    _COMMODITY_TICKERS,
    _CORRIDOR_NO_MATCH,
)
from pipeline.settings import (
    DEFAULT_OUTPUT_DIR,
    REQUEST_DELAY,
    ARTICLE_FETCH_DELAY,
    SIMILARITY_THRESHOLD,
    ARTICLE_TIMEOUT,
    ARTICLE_RETRIES,
    DEFAULT_MAX_ITEMS_PER_QUERY,
    USER_AGENT,
    GEMINI_API_KEY,
    MAX_LLM_CLASSIFICATIONS_PER_RUN,
)
from pipeline.processors import (
    _get_impact,
    apply_corridor_impact,
    _deduplicate_day_group,
    _is_relevant,
    _passes_outcome_gate,
    _is_official,
    _source_score,
)
from pipeline.processors.deduplicator import (
    _deduplicate_day_group,
)
from pipeline.utils.text import _title_tokens
from pipeline.utils.similarity import _jaccard
from pipeline.utils.dates import (
    _parse_date,
    _in_date_range,
    _google_news_window,
)
from pipeline.collectors import (
    fetch_query,
    fetch_official_rss,
    fetch_ofac_sanctions_list,
    fetch_commodity_prices,
)
from pipeline.enrichers import (
    enrich_item,
    enrich_dataframe,
    fetch_existing_hashes,
    classify_with_llm,
)
from pipeline.enrichers.article_enricher import (
    _resolve_google_news_url,
    _fetch_article_text,
    _extract_numbers,
    _extract_key_takeaway,
    _domain,
)
from pipeline.persistence import (
    write_csv_outputs,
    to_db_macro_rows,
)
from pipeline.cli import build_arg_parser, resolve_default_dates

try:
    import pipeline.db as db_writer
except Exception:
    db_writer = None


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    args.from_date, args.to_date = resolve_default_dates(args.from_date, args.to_date)
    from pipeline.runner import run
    run(args)


if __name__ == "__main__":
    main()