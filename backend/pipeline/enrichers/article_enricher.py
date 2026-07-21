import re
import time
import hashlib

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import base64

from pipeline.settings import (
    USER_AGENT,
    ARTICLE_TIMEOUT,
    ARTICLE_RETRIES,
    ARTICLE_FETCH_DELAY,
    MAX_LLM_CLASSIFICATIONS_PER_RUN,
    GEMINI_API_KEY,
)
from pipeline.config import NUMERIC_PATTERNS, TAKEAWAY_MARKERS


def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _resolve_google_news_url(google_url):
    if "news.google.com" not in google_url:
        return google_url

    try:
        path = urlparse(google_url).path
        parts = path.split("/articles/")
        if len(parts) >= 2:
            encoded = parts[1].split("?")[0]
            for pad in range(4):
                try:
                    padded = encoded + "=" * pad
                    decoded_bytes = base64.urlsafe_b64decode(padded)
                    decoded_text = decoded_bytes.decode("utf-8", errors="ignore")
                    match = re.search(r"https?://[^\x00-\x1f\s\"\\]+", decoded_text)
                    if match:
                        candidate = match.group(0)
                        if "news.google.com" not in candidate:
                            return candidate
                except Exception:
                    continue
    except Exception:
        pass

    try:
        resp = requests.get(
            google_url,
            headers={"User-Agent": USER_AGENT},
            timeout=ARTICLE_TIMEOUT,
            allow_redirects=True,
        )
        if resp.url and "news.google.com" not in resp.url:
            return resp.url
    except Exception:
        pass

    try:
        import newspaper
        article = newspaper.Article(google_url)
        article.download()
        if article.source_url and "news.google.com" not in article.source_url:
            return article.source_url
    except Exception:
        pass

    return google_url


def _fetch_article_text(url):
    headers = {"User-Agent": USER_AGENT}

    resolved_url = _resolve_google_news_url(url)
    if resolved_url == url and "news.google.com" in url:
        try:
            resp = requests.get(url, headers=headers, timeout=ARTICLE_TIMEOUT, allow_redirects=True)
            if resp.url and "news.google.com" not in resp.url:
                resolved_url = resp.url
            else:
                return "", "unresolved_url"
        except Exception:
            return "", "unresolved_url"

    try:
        import newspaper
        article = newspaper.Article(resolved_url)
        article.download()
        article.parse()
        text = article.text.strip()
        if len(text) >= 150:
            return text, "success"
    except Exception:
        pass

    for attempt in range(ARTICLE_RETRIES + 1):
        try:
            resp = requests.get(
                resolved_url, headers=headers,
                timeout=ARTICLE_TIMEOUT, allow_redirects=True
            )
            if resp.status_code in (403, 429):
                return "", "blocked"
            if resp.status_code != 200:
                continue

            _soup = BeautifulSoup(resp.content, "html.parser")
            for tag in _soup(["script", "style", "nav", "header",
                               "footer", "aside", "form", "iframe", "noscript"]):
                tag.decompose()

            article_tag = _soup.find("article")
            paragraphs = article_tag.find_all("p") if article_tag else _soup.find_all("p")
            text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) >= 100:
                return text, "success"
            return text, "failed"

        except requests.exceptions.Timeout:
            continue
        except Exception:
            continue

    return "", "failed"


def _extract_numbers(category, text):
    if not text:
        return ""
    patterns = NUMERIC_PATTERNS.get(category, [])
    found = []
    seen = set()
    text_lower = text.lower()
    for pattern, label in patterns:
        m = re.search(pattern, text_lower, re.IGNORECASE)
        if m:
            pair = f"{label}={m.group(1)}"
            if pair not in seen:
                seen.add(pair)
                found.append(pair)
    return " | ".join(found)


def _extract_key_takeaway(text, max_sentences=3):
    if not text:
        return ""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    scored = []
    for idx, s in enumerate(sentences):
        has_number = bool(re.search(r"\d", s))
        has_marker = bool(TAKEAWAY_MARKERS.search(s))
        if has_number or has_marker:
            score = (2 if has_number and has_marker else 1)
            scored.append((score, idx, s.strip()))

    if not scored:
        return " ".join(sentences[:max_sentences]).strip()[:600]

    scored.sort(key=lambda x: (-x[0], x[1]))
    chosen = sorted(scored[:max_sentences], key=lambda x: x[1])
    top = [s for _, _, s in chosen]
    return " ".join(top).strip()[:600]


def enrich_item(row):
    link = row.get("link", "")
    category = row.get("category", "")

    if not link:
        return {
            "extracted_numbers": "",
            "key_takeaway": "",
            "article_text_snippet": "",
            "fetch_status": "skipped_no_link",
        }

    text, status = _fetch_article_text(link)

    if status == "unresolved_url":
        return {
            "extracted_numbers": "",
            "key_takeaway": "",
            "article_text_snippet": "",
            "fetch_status": "unresolved_url",
        }

    if status == "success":
        numbers = _extract_numbers(category, text)
        takeaway = _extract_key_takeaway(text)
        snippet = text[:500]
    else:
        numbers = ""
        takeaway = ""
        snippet = text[:500] if text else ""

    return {
        "extracted_numbers": numbers,
        "key_takeaway": takeaway,
        "article_text_snippet": snippet,
        "fetch_status": status,
    }


def fetch_existing_hashes(conn):
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT content_hash FROM macro_events WHERE content_hash IS NOT NULL")
            return {row[0] for row in cur.fetchall()}
    except Exception as e:
        print(f"   [!] Could not fetch existing content hashes ({e}); will enrich all surviving items this run.")
        return set()


def enrich_dataframe(df, existing_hashes=None, llm_classify=False, llm_api_key=""):
    from .llm_classifier import classify_with_llm
    import pandas as pd

    existing_hashes = existing_hashes or set()
    total = len(df)

    to_enrich_mask = []
    skip_count = 0
    for title in df["title"]:
        h = hashlib.sha256(str(title).encode()).hexdigest()
        already_known = h in existing_hashes
        to_enrich_mask.append(not already_known)
        if already_known:
            skip_count += 1

    print(f"\nEnrichment stage: {total} items, {skip_count} already known "
          f"(skipping fetch), {total - skip_count} to fetch...")

    enriched_records = []
    for i, (row, should_enrich) in enumerate(zip(df.to_dict("records"), to_enrich_mask), 1):
        if not should_enrich:
            enriched_records.append({
                "extracted_numbers": "",
                "key_takeaway": "",
                "article_text_snippet": "",
                "fetch_status": "skipped_already_known",
            })
            continue

        domain = _domain(row.get("link", ""))
        _safe_title = row["title"][:50].encode("ascii", errors="replace").decode("ascii")
        print(f"  [{i}/{total}] {row.get('category','?'):16s} | {domain or 'no-domain'} | {_safe_title}...")
        result = enrich_item(row)
        enriched_records.append(result)
        print(f"       -> status={result['fetch_status']}, "
              f"numbers={'yes' if result['extracted_numbers'] else 'no'}")
        time.sleep(ARTICLE_FETCH_DELAY)

    enrich_df = pd.DataFrame(enriched_records)
    df = df.reset_index(drop=True)
    enrich_df = enrich_df.reset_index(drop=True)
    df_combined = pd.concat([df, enrich_df], axis=1)

    llm_cols = ["llm_severity", "llm_confidence", "is_genuine_disruption",
                "llm_corridor", "llm_justification", "review_flagged", "llm_status"]

    for col in llm_cols:
        df_combined[col] = None

    if llm_classify and llm_api_key and llm_api_key != "your_gemini_api_key_here":
        print(f"\nLLM classification: ON (Google Gemini 2.0 Flash - Free Tier Sample)")

        df_combined["severity_numeric"] = pd.to_numeric(df_combined["severity"], errors="coerce").fillna(0).astype(int)

        candidates = df_combined[
            (df_combined["article_text_snippet"].notna()) &
            (df_combined["article_text_snippet"].str.strip() != "") &
            (df_combined["severity_numeric"] > 0)
        ].copy()

        if not candidates.empty:
            candidates["parsed_date"] = pd.to_datetime(candidates["date"], errors="coerce")
            candidates = candidates.sort_values(
                by=["severity_numeric", "parsed_date"],
                ascending=[False, False]
            )
            sampled_indices = candidates.index[:MAX_LLM_CLASSIFICATIONS_PER_RUN]
            print(f"Sampling {len(sampled_indices)} out of {len(candidates)} eligible articles for AI validation...")

            for idx in sampled_indices:
                row = df_combined.loc[idx]
                title = row.get("title", "")
                snippet = row.get("article_text_snippet", "")
                kw_sev = int(row.get("severity_numeric", 0))

                print(f"  Validating: {title[:45]}... (kw_severity={kw_sev})")
                llm_res = classify_with_llm(title, snippet, kw_sev, llm_api_key)

                for k, v in llm_res.items():
                    df_combined.at[idx, k] = v

                flag_str = " [REVIEW_FLAGGED]" if llm_res.get("review_flagged") else ""
                print(f"       -> llm_severity={llm_res.get('llm_severity')} status={llm_res.get('llm_status')}{flag_str}")
                time.sleep(4.0)

            df_combined.loc[~df_combined.index.isin(sampled_indices), "llm_status"] = "skipped_capped"
        else:
            print("No eligible articles found for LLM validation.")
            df_combined["llm_status"] = "skipped_no_candidates"
    else:
        df_combined["llm_status"] = "not_requested" if not llm_classify else "no_api_key"

    if "severity_numeric" in df_combined.columns:
        df_combined = df_combined.drop(columns=["severity_numeric"])
    if "parsed_date" in df_combined.columns:
        df_combined = df_combined.drop(columns=["parsed_date"])

    try:
        from pipeline.qdrant_store import upsert_articles as _qdrant_upsert
        qdrant_rows = [
            r for r in df_combined.to_dict("records")
            if r.get("article_text_snippet") or r.get("key_takeaway")
        ]
        if qdrant_rows:
            _key = llm_api_key or GEMINI_API_KEY
            _qdrant_upsert(qdrant_rows, api_key=_key)
    except Exception as e:
        print(f"[Qdrant] upsert skipped: {e}")

    return df_combined
