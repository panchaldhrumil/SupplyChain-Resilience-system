import json
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, Request

from api.db import query_df
from pipeline.qdrant_store import search_by_corridor
from pipeline.gemini_pool import pool as _dynamic_pool  # shared round-robin pool

router = APIRouter()
log = logging.getLogger("corridor_brief")


def _load_events_db(corridor: str, lookback_hours: int = 48) -> pd.DataFrame:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    df = query_df("""
        SELECT date, title, source, link, corridor, severity, key_takeaway, article_text_snippet
        FROM macro_events
        WHERE corridor = %s AND created_at >= %s
        ORDER BY created_at DESC
        LIMIT 5
    """, params=(corridor, cutoff))
    if df.empty:
        df = query_df("""
            SELECT date, title, source, link, corridor, severity, key_takeaway, article_text_snippet
            FROM macro_events
            WHERE corridor = %s
            ORDER BY date DESC, severity DESC
            LIMIT 5
        """, params=(corridor,))
    if df.empty:
        return pd.DataFrame()

    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    return df


def _str(v, default=''):
    if v is None:
        return default
    try:
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
    except Exception:
        pass
    s = str(v)
    return default if s in ('nan', 'None') else s


def _build_prompt(corridor: str, articles: list) -> str:
    articles_text = ""
    for idx, art in enumerate(articles, 1):
        articles_text += (
            f"Article [{idx}]:\n"
            f"  Title: {art['title']}\n"
            f"  Source: {art['source']}\n"
            f"  Takeaway: {art['key_takeaway']}\n"
            f"  Snippet: {art['snippet']}\n\n"
        )
    return (
        "You are a senior energy security analyst writing an executive intelligence briefing for India's Ministry of Petroleum.\n"
        f"Synthesize a fluid, cohesive 2-3 sentence analyst narrative summarizing security and shipping developments for the '{corridor}' corridor.\n"
        "Rules:\n"
        "- Base your narrative STRICTLY on the provided articles below. Do NOT invent, assume, or fabricate any facts, numbers, or coordinates.\n"
        "- Write connected, professional prose that reads like a human analyst's summary explaining what is happening and why it matters for India.\n"
        "- Seamlessly weave source attributions into the natural flow of the prose (e.g. 'According to reporting by Reuters...', 'as noted by The Economic Times...').\n"
        "- Do NOT format as bullet points, numbered lists, or concatenated 'According to X: headline' fragments.\n"
        "- Keep the total summary under 75 words.\n\n"
        f"Articles:\n{articles_text}\n"
        "Output ONLY the clean synthesized narrative brief, nothing else."
    )


def synthesize_brief(corridor: str, articles: list) -> tuple[str, str]:
    """Synthesize a corridor intelligence brief using Gemini with round-robin key rotation."""
    active_keys = _dynamic_pool.get_all_keys()
    if not active_keys:
        return _auto_compile(articles), "fallback_no_key"

    try:
        from google import genai
    except ImportError:
        return _auto_compile(articles), "fallback_no_key"

    prompt = _build_prompt(corridor, articles)
    tried_keys: set[str] = set()

    models_to_try = [
        'gemini-2.0-flash',
        'gemini-1.5-flash',
    ]

    # Try each key in the pool; rotate immediately on 429
    for _attempt in range(max(len(active_keys), 1)):
        api_key = _dynamic_pool.get_next_key()
        if not api_key or api_key in tried_keys:
            break
        tried_keys.add(api_key)

        for model_name in models_to_try:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                log.info("[corridor_brief] brief generated via %s (key slot %d/%d)",
                         model_name, len(tried_keys), len(active_keys))
                return response.text.strip(), "ok"

            except Exception as e:
                err_str = str(e).lower()
                if any(x in err_str for x in ("429", "quota", "exhausted", "limit")):
                    log.warning("[corridor_brief] 429 on key slot %d — rotating.", len(tried_keys))
                    api_key = _dynamic_pool.rotate()
                    tried_keys.add(api_key)
                    break  # try next key
                log.debug("[corridor_brief] %s failed: %s", model_name, e)
                continue  # try next model

    return _auto_compile(articles), "fallback_all_keys_failed"


def _auto_compile(articles: list) -> str:
    if not articles:
        return "No recent articles available for this corridor."
    takeaways = []
    sources = []
    for a in articles[:3]:
        t = a.get("key_takeaway") or a.get("title")
        s = a.get("source")
        if t and t not in takeaways:
            takeaways.append(t)
        if s and s not in sources:
            sources.append(s)
    src_str = ", ".join(sources) if sources else "recent reporting"
    prose = " ".join(takeaways)
    return f"Recent reporting from {src_str} indicates active developments across the shipping lane: {prose}"


@router.get("/corridor-brief")
def get_corridor_brief(
    request: Request,
    corridor: str = Query(..., description="Corridor ID: hormuz / red_sea / suez / cape_of_good_hope / russia_route / malacca"),
):
    active_keys = _dynamic_pool.get_all_keys()
    primary_key = active_keys[0] if active_keys else ""  # first key for Qdrant embedding

    qdrant_results = search_by_corridor(
        corridor=corridor,
        query_text=f"security disruption oil tanker shipping risk in {corridor}",
        limit=5,
        api_key=primary_key,
    )

    articles = []
    if qdrant_results:
        for item in qdrant_results:
            articles.append({
                "title":        _str(item.get("title")),
                "source":       _str(item.get("source")),
                "link":         _str(item.get("link")),
                "key_takeaway": _str(item.get("key_takeaway")),
                "snippet":      _str(item.get("article_text_snippet"))[:250],
                "date":         _str(item.get("date")),
            })
    else:
        df = _load_events_db(corridor=corridor, lookback_hours=48)
        if not df.empty:
            for _, row in df.iterrows():
                articles.append({
                    "title":        _str(row.get("title")),
                    "source":       _str(row.get("source")),
                    "link":         _str(row.get("link")),
                    "key_takeaway": _str(row.get("key_takeaway")),
                    "snippet":      _str(row.get("article_text_snippet"))[:250],
                    "date":         row["_dt"].isoformat() if pd.notna(row["_dt"]) else _str(row.get("date")),
                })

    if not articles:
        return {
            "corridor":     corridor,
            "brief":        "Insufficient recent signal (no news articles parsed for this corridor in the last 48 hours).",
            "articles":     [],
            "llm_status":   "insufficient_signal",
            "keys_in_pool": len(active_keys),
        }

    brief, llm_status = synthesize_brief(corridor, articles)

    return {
        "corridor":     corridor,
        "brief":        brief,
        "articles":     articles,
        "llm_status":   llm_status,
        "keys_in_pool": len(active_keys),
    }
