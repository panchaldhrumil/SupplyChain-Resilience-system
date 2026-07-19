"""
llm_classifier.py
==================
Google Gemini 2.0 Flash article severity classifier.

Provides:
  classify_with_llm — call Gemini to independently score an article's
                       supply-chain disruption severity.
"""

import time

from pipeline.settings import USER_AGENT  # noqa: F401 — imported for consistency


def classify_with_llm(title: str, snippet: str, keyword_severity: int, api_key: str) -> dict:
    """
    Call Google Gemini 2.0 Flash to independently classify an article's severity.
    Returns a dict with:
      llm_severity          : int 1-5 (or None on failure)
      llm_confidence        : float 0.0-1.0 (or None on failure)
      is_genuine_disruption : bool
      llm_corridor          : str (the corridor the LLM thinks this is about)
      llm_justification     : str (one sentence)
      review_flagged        : bool — True if LLM severity disagrees with
                              keyword_severity by >= 2 points

    Gracefully returns a "skipped" result on any API error — never raises.
    Includes exponential backoff retries for 429 rate limit errors.
    """
    _SKIP = {
        "llm_severity": None,
        "llm_confidence": None,
        "is_genuine_disruption": None,
        "llm_corridor": "",
        "llm_justification": "",
        "review_flagged": False,
        "llm_status": "skipped",
    }
    if not api_key or api_key == "your_gemini_api_key_here":
        return {**_SKIP, "llm_status": "no_api_key"}

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        return {**_SKIP, "llm_status": "google_genai_not_installed"}

    PROMPT = (
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

    client = genai.Client(api_key=api_key)
    retries = 2
    delay = 2.0
    import random as _random

    for attempt in range(retries + 1):
        try:
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents=PROMPT,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            raw = response.text.strip()
            # Strip markdown fences if present
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]

            import json as _json
            parsed = _json.loads(raw)
            llm_sev = int(parsed.get("llm_severity", 0))
            llm_conf = float(parsed.get("confidence", 0.0))
            is_genuine = bool(parsed.get("is_genuine_disruption_signal", False))
            corridor = str(parsed.get("corridor", ""))
            justif = str(parsed.get("one_line_justification", ""))
            review_flagged = abs(llm_sev - keyword_severity) >= 2

            return {
                "llm_severity":          llm_sev,
                "llm_confidence":        round(llm_conf, 3),
                "is_genuine_disruption": is_genuine,
                "llm_corridor":          corridor,
                "llm_justification":     justif,
                "review_flagged":        review_flagged,
                "llm_status":            "ok",
            }
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limited = "429" in err_str or "resource" in err_str or "exhausted" in err_str or "limit" in err_str
            if is_rate_limited and attempt < retries:
                sleep_time = delay * (2 ** attempt) + _random.uniform(0.1, 1.0)
                print(f"       [Rate Limit] 429 received. Retrying in {sleep_time:.2f}s...")
                time.sleep(sleep_time)
            else:
                print(f"       [LLM Error] {e}")
                status_msg = "skipped_rate_limited" if is_rate_limited else f"error: {e}"
                return {**_SKIP, "llm_status": status_msg}

    return {**_SKIP, "llm_status": "skipped_rate_limited"}
