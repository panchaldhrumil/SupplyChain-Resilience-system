"""
GET /api/corridor-brief?corridor=hormuz

Retrieves the actual stored news articles for that corridor from the last 48 hours,
and passes ONLY those retrieved snippets to the LLM (if API key is present)
to synthesize a 2-3 sentence intelligence brief.

If zero articles exist for that corridor in the last 48 hours, returns
"insufficient recent signal" without calling the LLM.
"""

import os
import json
import math
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Query, Request, HTTPException

router = APIRouter()

# Anthropic key loaded from environment
_ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


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


def synthesize_brief(corridor: str, articles: list, api_key: str) -> str:
    """
    RAG-grounded prompt: Synthesizes a 2-3 sentence intelligence brief
    citing the sources by name. Explicitly forbids inventing facts.
    """
    if not api_key:
        # Fallback if no LLM key
        summary_lines = []
        for i, a in enumerate(articles[:3], 1):
            takeaway = a["key_takeaway"] or a["title"]
            source = a["source"] or "Unknown source"
            summary_lines.append(f"• According to {source}: {takeaway}")
        return "(Auto-compiled) Recent updates:\n" + "\n".join(summary_lines)

    try:
        import anthropic
    except ImportError:
        summary_lines = []
        for i, a in enumerate(articles[:3], 1):
            takeaway = a["key_takeaway"] or a["title"]
            source = a["source"] or "Unknown source"
            summary_lines.append(f"• According to {source}: {takeaway}")
        return "(Auto-compiled) Recent updates:\n" + "\n".join(summary_lines)

    articles_text = ""
    for idx, art in enumerate(articles, 1):
        articles_text += (
            f"Article [{idx}]:\n"
            f"  Title: {art['title']}\n"
            f"  Source: {art['source']}\n"
            f"  Takeaway: {art['key_takeaway']}\n"
            f"  Snippet: {art['snippet']}\n\n"
        )

    prompt = (
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

    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"Brief generation failed: {e}"


@router.get("/corridor-brief")
def get_corridor_brief(
    request: Request,
    corridor: str = Query(..., description="Corridor ID: hormuz / red_sea / suez / cape_of_good_hope / russia_route / malacca"),
):
    csv_dir: Path = request.app.state.csv_dir
    df = _load_events(csv_dir, lookback_hours=48)

    if df.empty:
        return {
            "corridor": corridor,
            "brief": "Insufficient recent signal (no news articles parsed for this corridor in the last 48 hours).",
            "articles": [],
            "llm_status": "insufficient_signal"
        }

    sub = df[df["corridor"] == corridor].copy()
    if sub.empty:
        return {
            "corridor": corridor,
            "brief": "Insufficient recent signal (no news articles parsed for this corridor in the last 48 hours).",
            "articles": [],
            "llm_status": "insufficient_signal"
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

    # Call RAG generator
    brief = synthesize_brief(corridor, articles, _ANTHROPIC_API_KEY)

    return {
        "corridor":   corridor,
        "brief":      brief,
        "articles":   articles,
        "llm_status": "ok" if _ANTHROPIC_API_KEY else "fallback_no_key"
    }
