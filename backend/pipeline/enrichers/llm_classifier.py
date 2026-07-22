"""
llm_classifier.py
==================
Google Gemini 2.0 Flash article severity classifier.

Provides:
  classify_with_llm — call Gemini to independently score an article's
                       supply-chain disruption severity.

Key rotation:
  Pass a GeminiKeyPool instance as `pool` for automatic key rotation on 429.
  Falls back to the module-level singleton pool if neither `api_key` nor
  `pool` is supplied.
"""

import json as _json
import logging
import random as _random
import time

from pipeline.settings import USER_AGENT  # noqa: F401 — imported for consistency

log = logging.getLogger("llm_classifier")

_SKIP_BASE = {
    "llm_severity": None,
    "llm_confidence": None,
    "is_genuine_disruption": None,
    "llm_corridor": "",
    "llm_justification": "",
    "review_flagged": False,
}

MODELS_TO_TRY = [
    "gemini-2.0-flash",
    "gemini-1.5-flash",
]


def _make_prompt(title: str, snippet: str) -> str:
    return (
        "You are a geopolitical risk analyst for India's crude oil supply chain.\n"
        "Classify the article below and return ONLY valid JSON matching the schema.\n"
        f"Headline: {title}\n"
        f"Snippet: {snippet[:600]}\n\n"
        "JSON Schema:\n"
        "{\n"
        '  "is_genuine_disruption_signal": bool,  // true if this describes a real supply disruption\n'
        '  "corridor": string,  // one of: hormuz, red_sea, suez, cape_of_good_hope, russia_route, malacca, india_domestic, none\n'
        '  "llm_severity": integer,  // 1 (minor mention) to 5 (critical disruption)\n'
        '  "confidence": float,  // 0.0 to 1.0\n'
        '  "one_line_justification": string  // max 20 words, cite only text shown\n'
        "}\n\n"
        "Rules:\n"
        "- Only use information in the headline and snippet above.\n"
        "- Do NOT add external facts or vessel positions.\n"
        "- Output ONLY the raw JSON object. Do not wrap in markdown code blocks."
    )


def _parse_response(raw: str, keyword_severity: int) -> dict:
    """Parse Gemini JSON response into a normalised result dict."""
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    parsed = _json.loads(raw.strip())
    llm_sev = int(parsed.get("llm_severity", 0))
    llm_conf = float(parsed.get("confidence", 0.0))
    is_genuine = bool(parsed.get("is_genuine_disruption_signal", False))
    corridor = str(parsed.get("corridor", ""))
    justif = str(parsed.get("one_line_justification", ""))
    review_flagged = abs(llm_sev - keyword_severity) >= 2
    return {
        "llm_severity": llm_sev,
        "llm_confidence": round(llm_conf, 3),
        "is_genuine_disruption": is_genuine,
        "llm_corridor": corridor,
        "llm_justification": justif,
        "review_flagged": review_flagged,
        "llm_status": "ok",
    }


def classify_with_llm(
    title: str,
    snippet: str,
    keyword_severity: int,
    api_key: str = "",
    pool=None,
) -> dict:
    """
    Call Google Gemini to classify an article's supply-chain disruption severity.

    Parameters
    ----------
    title, snippet       : article content (snippet truncated to 600 chars)
    keyword_severity     : pre-computed keyword-based severity score (1-5)
    api_key              : explicit single key — used if provided (legacy path)
    pool                 : GeminiKeyPool instance — preferred; rotates on 429.
                           If both are omitted, falls back to module-level singleton.

    Returns a dict with llm_severity, llm_confidence, is_genuine_disruption,
    llm_corridor, llm_justification, review_flagged, llm_status.
    Gracefully returns a 'skipped' result on any unrecoverable error — never raises.
    """
    # Resolve key source
    if pool is None and not api_key:
        from pipeline.gemini_pool import pool as _default_pool
        pool = _default_pool

    # Determine active key
    def _get_key():
        if api_key:
            return api_key
        if pool:
            return pool.get_next_key()
        return ""

    def _rotate_key():
        if pool:
            return pool.rotate()
        return api_key  # single-key path has no rotation

    active_key = _get_key()
    if not active_key or active_key == "your_gemini_api_key_here":
        return {**_SKIP_BASE, "llm_status": "no_api_key"}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {**_SKIP_BASE, "llm_status": "google_genai_not_installed"}

    prompt = _make_prompt(title, snippet)

    # Outer loop: try each available key (up to pool size or 1 for single-key)
    max_key_rotations = len(pool) if pool else 1
    tried_keys: set[str] = set()
    delay = 2.0

    for _key_attempt in range(max(max_key_rotations, 1)):
        if active_key in tried_keys:
            active_key = _rotate_key()
            if active_key in tried_keys:
                break
        tried_keys.add(active_key)

        # Inner loop: try each model variant for this key
        for model_name in MODELS_TO_TRY:
            for attempt in range(3):  # up to 3 retries per model with backoff
                try:
                    client = genai.Client(api_key=active_key)
                    response = client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                        ),
                    )
                    return _parse_response(response.text.strip(), keyword_severity)

                except Exception as e:
                    err_str = str(e).lower()
                    is_rate_limit = any(x in err_str for x in ("429", "resource", "exhausted", "quota", "limit"))

                    if is_rate_limit:
                        if pool and _key_attempt < max_key_rotations - 1:
                            # Rotate immediately — don't waste retries on same key
                            log.warning("[LLM] 429 on key slot — rotating to next key.")
                            active_key = _rotate_key()
                            tried_keys.add(active_key)
                            break  # break inner model loop, try with new key
                        elif attempt < 2:
                            sleep_time = delay * (2 ** attempt) + _random.uniform(0.1, 1.0)
                            log.warning("[LLM] 429 — backing off %.1fs (attempt %d/3)", sleep_time, attempt + 1)
                            time.sleep(sleep_time)
                        else:
                            return {**_SKIP_BASE, "llm_status": "skipped_rate_limited"}
                    else:
                        log.debug("[LLM] %s failed on %s: %s", model_name, active_key[:8] + "...", e)
                        break  # non-rate-limit error — try next model

    return {**_SKIP_BASE, "llm_status": "skipped_all_keys_exhausted"}
