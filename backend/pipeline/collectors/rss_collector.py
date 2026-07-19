"""
rss_collector.py
================
Google News RSS feed collector for macro queries.

Provides:
  fetch_query — fetch a single query from Google News RSS
"""

import feedparser
from urllib.parse import quote_plus

from pipeline.settings import DEFAULT_MAX_ITEMS_PER_QUERY, USER_AGENT
from pipeline.config import GEOPOLITICAL_RELEVANCE_WORDS, ELECTION_NOISE_WORDS
from pipeline.utils.dates import _in_date_range, _parse_date, _google_news_window
from pipeline.processors.impact_mapper import _get_impact
from pipeline.processors.corridor_tagger import apply_corridor_impact
from pipeline.processors.relevance_filter import _is_relevant, _passes_outcome_gate


def fetch_query(category, query, from_date_str, to_date_str=None,
                max_items=DEFAULT_MAX_ITEMS_PER_QUERY, keep_previews=False):
    when_clause = _google_news_window(from_date_str, to_date_str)
    full_q = f"{query} {when_clause}"
    url = (f"https://news.google.com/rss/search?"
           f"q={quote_plus(full_q)}&hl=en-IN&gl=IN&ceid=IN:en")
    items = []
    try:
        feed = feedparser.parse(url)

        for entry in feed.entries:
            if len(items) >= max_items:
                break

            pub = entry.get("published", "")
            if not _in_date_range(pub, from_date_str, to_date_str):
                continue
            title = entry.get("title", "").strip()
            if not title:
                continue

            if category == "Geopolitical":
                title_lower_check = title.lower()
                if not any(w in title_lower_check for w in GEOPOLITICAL_RELEVANCE_WORDS):
                    continue

            if category == "India_Policy":
                title_lower_check = title.lower()
                if any(w in title_lower_check for w in ELECTION_NOISE_WORDS):
                    continue

            if not keep_previews and not _passes_outcome_gate(category, title):
                continue

            # Broad relevance gate (from filter_macro_events.py) — applied to
            # ALL categories at fetch time now, instead of as a later pass.
            if not _is_relevant(title):
                continue

            link   = entry.get("link", "")
            source = entry.get("source", {}).get("title", "") if hasattr(entry, "source") else ""
            pub_date = _parse_date(pub)
            sectors, companies = _get_impact(title)
            corridor_impact    = apply_corridor_impact(title)
            items.append({
                "date":               pub_date,
                "published_raw":      pub,
                "title":              title,
                "source":             source,
                "link":               link,
                "category":           category,
                "affected_sectors":   sectors,
                "affected_companies": companies,
                "buffer_layer":       corridor_impact["buffer_layer"],
                "corridor":           corridor_impact["corridor"],
                "severity":           corridor_impact["severity"],
            })
    except Exception as e:
        print(f"   [!] Fetch error for query '{query}': {e}")
    return items
