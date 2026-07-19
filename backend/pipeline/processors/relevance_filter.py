from pipeline.config import (
    DATA_RELEASE_CATEGORIES, PREVIEW_NOISE_WORDS, CATEGORY_ANCHORS,
    OUTCOME_SIGNAL_WORDS, NUMERIC_VALUE_RE, OFFICIAL_SOURCES,
    NEWS_SOURCE_PRIORITY, RELEVANCE_KEYWORDS
)

def _passes_outcome_gate(category, title):
    if category not in DATA_RELEASE_CATEGORIES:
        return True

    tl = title.lower()

    if any(p in tl for p in PREVIEW_NOISE_WORDS):
        return False

    anchors = CATEGORY_ANCHORS.get(category, [])
    if anchors and not any(a in tl for a in anchors):
        return False

    if any(w in tl for w in OUTCOME_SIGNAL_WORDS):
        return True
    if NUMERIC_VALUE_RE.search(tl):
        return True
    return False

def _is_official(source_str):
    s = str(source_str).lower().strip()
    return any(key in s for key in OFFICIAL_SOURCES)

def _source_score(src):
    s = str(src).lower().strip()
    for k, v in OFFICIAL_SOURCES.items():
        if k in s:
            return v
    for k, v in NEWS_SOURCE_PRIORITY.items():
        if k in s:
            return v
    return 25

def _is_relevant(title):
    t = str(title).lower()
    return any(kw in t for kw in RELEVANCE_KEYWORDS)
