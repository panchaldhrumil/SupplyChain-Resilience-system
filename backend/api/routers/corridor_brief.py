import os
import json
import math
import itertools
import logging
import threading
from datetime import datetime, timezone, timedelta, date as date_cls
from typing import Optional
import pandas as pd
from fastapi import APIRouter, Query, Request

from api.db import query_df
from pipeline.qdrant_store import search_by_corridor

router = APIRouter()
log = logging.getLogger("corridor_brief")


class DynamicKeyPool:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_keys = []
        self._cycle = None

    def _get_clean_keys(self) -> list[str]:
        from dotenv import load_dotenv
        load_dotenv()

        raw_keys = [
            os.environ.get("GEMINI_API_KEY_1", ""),
            os.environ.get("GEMINI_API_KEY_2", ""),
            os.environ.get("GEMINI_API_KEY_3", ""),
            os.environ.get("GEMINI_API_KEY_4", ""),
            os.environ.get("GEMINI_API_KEY", ""),
        ]
        return list(
            dict.fromkeys(
                k.strip() for k in raw_keys
                if k and not k.strip().startswith("your_gemini_api_key")
            )
        )

    def get_next_key(self) -> str:
        keys = self._get_clean_keys()
        with self._lock:
            if not keys:
                self._last_keys = []
                self._cycle = None
                return ""

            if keys != self._last_keys or self._cycle is None:
                self._last_keys = keys
                self._cycle = itertools.cycle(keys)

            return next(self._cycle)

    def get_all_keys(self) -> list[str]:
        return self._get_clean_keys()


_dynamic_pool = DynamicKeyPool()


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
        "You are an energy security analyst for India's shipping lanes.\n"
        f"Synthesize a concise 2-3 sentence intelligence brief summarizing current conditions for the '{corridor}' shipping corridor.\n"
        "Rules:\n"
        "- Base your summary ONLY on the provided articles. Do NOT invent or assume any facts.\n"
        "- Do NOT add fake ship coordinates or fake numbers.\n"
        "- Explicitly cite which sources you drew from by name (e.g. 'Reuters reports', 'according to The Economic Times').\n"
        "- Keep it under 60 words total.\n\n"
        f"Articles:\n{articles_text}\n"
        "Output ONLY the brief text, nothing else."
    )


def synthesize_brief(corridor: str, articles: list) -> tuple[str, str]:
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
        'gemini-2.5-flash',
        'gemini-2.0-flash',
        'gemini-1.5-flash',
    ]

    for _ in range(len(active_keys)):
        api_key = _dynamic_pool.get_next_key()
        if not api_key or api_key in tried_keys:
            continue
        tried_keys.add(api_key)

        for model_name in models_to_try:
            try:
                client = genai.Client(api_key=api_key)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                )
                return response.text.strip(), "ok"

            except Exception:
                continue

        continue

    return _auto_compile(articles), "fallback_all_keys_failed"


def _auto_compile(articles: list) -> str:
    if not articles:
        return "No recent articles available for this corridor."
    lines = []
    for a in articles[:3]:
        takeaway = a["key_takeaway"] or a["title"]
        source   = a["source"] or "Unknown source"
        lines.append(f"• According to {source}: {takeaway}")
    return "(Auto-compiled) Recent updates:\n" + "\n".join(lines)


@router.get("/corridor-brief")
def get_corridor_brief(
    request: Request,
    corridor: str = Query(..., description="Corridor ID: hormuz / red_sea / suez / cape_of_good_hope / russia_route / malacca"),
):
    active_keys = _dynamic_pool.get_all_keys()
    primary_key = active_keys[0] if active_keys else ""

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
