import re
import base64
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from pipeline.settings import USER_AGENT, ARTICLE_TIMEOUT, ARTICLE_RETRIES

def _domain(url):
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _resolve_google_news_url(google_url):
    """
    Three-method Google News URL resolver:
    Method 1: base64 decode from URL path (fastest, no network)
    Method 2: requests follow redirect (network, 1 call)
    Method 3: newspaper3k built-in resolver
    """
    if "news.google.com" not in google_url:
        return google_url

    # Method 1 — base64 decode
    try:
        path   = urlparse(google_url).path
        parts  = path.split("/articles/")
        if len(parts) >= 2:
            encoded = parts[1].split("?")[0]
            # Try multiple padding variants
            for pad in range(4):
                try:
                    padded        = encoded + "=" * pad
                    decoded_bytes = base64.urlsafe_b64decode(padded)
                    decoded_text  = decoded_bytes.decode("utf-8", errors="ignore")
                    match = re.search(r"https?://[^\x00-\x1f\s\"\\]+", decoded_text)
                    if match:
                        candidate = match.group(0)
                        if "news.google.com" not in candidate:
                            return candidate
                except Exception:
                    continue
    except Exception:
        pass

    # Method 2 — requests redirect follow
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

    # Method 3 — newspaper3k
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
    """
    Fetch article text with three-tier fallback:
    Tier 1: newspaper3k (best, handles most paywalls + redirects)
    Tier 2: requests + BeautifulSoup (fallback for sites newspaper3k fails)
    Tier 3: return empty (graceful fail, never crashes pipeline)
    """
    headers = {"User-Agent": USER_AGENT}

    # First resolve Google News redirect
    resolved_url = _resolve_google_news_url(url)
    if resolved_url == url and "news.google.com" in url:
        # Try one more time with requests direct follow
        try:
            resp = requests.get(
                url, headers=headers, timeout=ARTICLE_TIMEOUT,
                allow_redirects=True
            )
            if resp.url and "news.google.com" not in resp.url:
                resolved_url = resp.url
            else:
                return "", "unresolved_url"
        except Exception:
            return "", "unresolved_url"

    # Tier 1 — newspaper3k
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

    # Tier 2 — requests + BeautifulSoup
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
            paragraphs  = article_tag.find_all("p") if article_tag else _soup.find_all("p")
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
