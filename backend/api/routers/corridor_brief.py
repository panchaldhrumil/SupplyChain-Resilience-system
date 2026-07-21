"""
GET /api/corridor-brief?corridor=hormuz

Retrieves the actual stored news articles for that corridor from the last 48 hours,
and passes ONLY those retrieved snippets to the LLM (if API key is present)
to synthesize a 2-3 sentence intelligence brief.

If zero articles exist for that corridor in the last 48 hours, returns
"insufficient recent signal" without calling the LLM.

Key pool: reads GEMINI_API_KEY_1..4 from the environment and uses them in
round-robin order. If the current key is exhausted (429) or errors, the next
key is tried automatically. All 4 must fail before falling back to the
auto-compiled text. Rotation is thread-safe under CPython's GIL via itertools.cycle.
"""

import os
import json
import math
import itertools
import logging
import threading
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter()
log = logging.getLogger("corridor_brief")

# --------------------------------------------------------------------------
# Thread-safe class to dynamically read and cycle through Gemini API keys from `.env`
# --------------------------------------------------------------------------
class DynamicKeyPool:
    def __init__(self):
        self._lock = threading.Lock()
        self._last_keys = []
        self._cycle = None

    def _get_clean_keys(self) -> list[str]:
        # Force reload .env file to pick up any edits on the fly
        from dotenv import load_dotenv
        load_dotenv()

        raw_keys = [
            os.environ.get("GEMINI_API_KEY_1", ""),
            os.environ.get("GEMINI_API_KEY_2", ""),
            os.environ.get("GEMINI_API_KEY_3", ""),
            os.environ.get("GEMINI_API_KEY_4", ""),
            os.environ.get("GEMINI_API_KEY", ""),   # legacy single-key fallback
        ]
        # Remove empty keys, duplicates, and placeholders
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

            # If key list changed (e.g. user added keys to .env), recreate cycle
            if keys != self._last_keys or self._cycle is None:
                self._last_keys = keys
                self._cycle = itertools.cycle(keys)

            return next(self._cycle)

    def get_all_keys(self) -> list[str]:
        return self._get_clean_keys()


_dynamic_pool = DynamicKeyPool()


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------

def _load_events(csv_dir: Path, lookback_hours: int = 48) -> pd.DataFrame:
    path = csv_dir / "macro_events_filtered.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(path, dtype=str, low_memory=False)
    except Exception:
        return pd.DataFrame()

    required = {"date", "title", "source", "link", "corridor", "severity", "key_takeaway", "article_text_snippet"}
    if not required.issubset(df.columns):
        return pd.DataFrame()

    # Parse date; drop unparseable rows
    df["_dt"] = pd.to_datetime(df["date"], errors="coerce", utc=True)
    df = df.dropna(subset=["_dt"])

    cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback_hours)
    df = df[df["_dt"] >= cutoff].copy()
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


# --------------------------------------------------------------------------
# LLM brief synthesis — round-robin with per-key failover and model fallback
# --------------------------------------------------------------------------

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
    """
    Call Gemini with round-robin key rotation + per-key failover + model fallback.
    Tries multiple Gemini models sequentially to handle model unavailability.

    Returns:
        (brief_text, status)
        status: "ok" | "fallback_no_key" | "fallback_all_keys_failed"
    """
    active_keys = _dynamic_pool.get_all_keys()
    if not active_keys:
        # No keys at all — auto-compile
        return _auto_compile(articles), "fallback_no_key"

    try:
        from google import genai
    except ImportError:
        return _auto_compile(articles), "fallback_no_key"

    prompt = _build_prompt(corridor, articles)
    tried_keys: set[str] = set()

    # Define fallback models to try (preferring latest Gemini flash models)
    models_to_try = [
        'gemini-2.5-flash',  # Primary / latest flash candidate
        'gemini-2.0-flash',  # Secondary / current flash
        'gemini-1.5-flash',  # Legacy fallback
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
                log.info(
                    "corridor_brief: key ending …%s succeeded using model=%s for corridor=%s",
                    api_key[-4:], model_name, corridor,
                )
                return response.text.strip(), "ok"

            except Exception as exc:
                err_str = str(exc)
                log.warning(
                    "corridor_brief: key …%s failed with model=%s (%s) — trying fallback.",
                    api_key[-4:], model_name, err_str[:80],
                )
                continue  # try next model in fallback list

        # If all models failed for this key, proceed to next key
        continue

    # All keys & models exhausted for this request
    log.error(
        "corridor_brief: all %d key(s) failed across all models for corridor=%s — returning auto-compiled fallback.",
        len(active_keys), corridor,
    )
    return _auto_compile(articles), "fallback_all_keys_failed"


def _auto_compile(articles: list) -> str:
    """Human-readable fallback when no LLM key is available."""
    if not articles:
        return "No recent articles available for this corridor."
    lines = []
    for a in articles[:3]:
        takeaway = a["key_takeaway"] or a["title"]
        source   = a["source"] or "Unknown source"
        lines.append(f"• According to {source}: {takeaway}")
    return "(Auto-compiled) Recent updates:\n" + "\n".join(lines)


# --------------------------------------------------------------------------
# Endpoint
# --------------------------------------------------------------------------

@router.get("/corridor-brief")
def get_corridor_brief(
    request: Request,
    corridor: str = Query(..., description="Corridor ID: hormuz / red_sea / suez / cape_of_good_hope / russia_route / malacca"),
):
    csv_dir: Path = request.app.state.csv_dir
    df = _load_events(csv_dir, lookback_hours=48)

    active_keys = _dynamic_pool.get_all_keys()

    if df.empty:
        return {
            "corridor":    corridor,
            "brief":       "Insufficient recent signal (no news articles parsed for this corridor in the last 48 hours).",
            "articles":    [],
            "llm_status":  "insufficient_signal",
            "keys_in_pool": len(active_keys),
        }

    sub = df[df["corridor"] == corridor].copy()
    if sub.empty:
        return {
            "corridor":    corridor,
            "brief":       "Insufficient recent signal (no news articles parsed for this corridor in the last 48 hours).",
            "articles":    [],
            "llm_status":  "insufficient_signal",
            "keys_in_pool": len(active_keys),
        }

    # Format articles for prompt & response
    articles = []
    for _, row in sub.head(5).iterrows():
        articles.append({
            "title":        _str(row.get("title")),
            "source":       _str(row.get("source")),
            "link":         _str(row.get("link")),
            "key_takeaway": _str(row.get("key_takeaway")),
            "snippet":      _str(row.get("article_text_snippet"))[:250],
            "date":         row["_dt"].isoformat(),
        })

    # Call RAG generator (round-robin key pool with failover)
    brief, llm_status = synthesize_brief(corridor, articles)

    return {
        "corridor":     corridor,
        "brief":        brief,
        "articles":     articles,
        "llm_status":   llm_status,
        "keys_in_pool": len(active_keys),
    }
