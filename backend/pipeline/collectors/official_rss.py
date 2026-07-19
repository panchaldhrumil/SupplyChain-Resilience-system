import time
import requests
import feedparser
from pipeline.settings import USER_AGENT
from pipeline.config import OFFICIAL_RSS_FEEDS
from pipeline.utils.dates import _in_date_range, _parse_date
from pipeline.processors.impact_mapper import _get_impact
from pipeline.processors.corridor_tagger import apply_corridor_impact
from pipeline.processors.relevance_filter import _is_relevant

def fetch_official_rss(from_date_str, to_date_str=None):
    """
    Fetch items from official government/regulator RSS feeds directly.
    Uses requests with a hard timeout so a hanging feed (e.g. WTO leaving
    the socket open) can't freeze the whole pipeline — feedparser.parse()
    on a URL has no timeout and will block forever on such feeds.
    Returns list of item dicts in same format as fetch_query().
    """
    items = []
    headers = {"User-Agent": USER_AGENT}

    for category, feed_url, source_name in OFFICIAL_RSS_FEEDS:
        try:
            # Fetch with a hard timeout instead of letting feedparser block
            resp = requests.get(feed_url, headers=headers, timeout=8,
                                allow_redirects=True)
            if resp.status_code != 200:
                print(f"  [Official RSS] {source_name}: HTTP {resp.status_code}, skipped")
                continue

            feed = feedparser.parse(resp.content)   # parse bytes, no network

            before = len(items)
            for entry in feed.entries:
                pub = entry.get("published", "") or entry.get("updated", "")
                if not _in_date_range(pub, from_date_str, to_date_str):
                    continue
                title = entry.get("title", "").strip()
                if not title:
                    continue
                if not _is_relevant(title):
                    continue
                link      = entry.get("link", "")
                pub_date  = _parse_date(pub)
                sectors, companies = _get_impact(title)
                corridor_impact    = apply_corridor_impact(title)
                items.append({
                    "date":               pub_date,
                    "published_raw":      pub,
                    "title":              title,
                    "source":             source_name,
                    "link":               link,
                    "category":           category,
                    "affected_sectors":   sectors,
                    "affected_companies": companies,
                    "buffer_layer":       corridor_impact["buffer_layer"],
                    "corridor":           corridor_impact["corridor"],
                    "severity":           corridor_impact["severity"],
                })
            print(f"  [Official RSS] {source_name}: {len(items) - before} items")
            time.sleep(0.5)

        except requests.exceptions.Timeout:
            print(f"  [Official RSS] {source_name}: TIMEOUT (skipped)")
            continue
        except Exception as e:
            print(f"  [Official RSS] {source_name} failed: {e}")
            continue

    return items
