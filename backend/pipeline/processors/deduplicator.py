from collections import defaultdict
from pipeline.utils.text import _title_tokens
from pipeline.utils.similarity import _jaccard
from pipeline.processors.relevance_filter import _is_official, _source_score
from pipeline.settings import SIMILARITY_THRESHOLD

def _deduplicate_day_group(items):
    """
    Given items from the SAME (category, date) group:
    1. Cluster by title similarity (Jaccard >= threshold) -> same event
    2. For each cluster:
       - Official source present -> keep ALL official, drop all Google News
       - All Google News -> keep single highest-trust source
    3. Single-item clusters (unique event) -> always keep as-is
    """
    if len(items) <= 1:
        return items

    tokens = [_title_tokens(x.get("title", "")) for x in items]
    parent = list(range(len(items)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if _jaccard(tokens[i], tokens[j]) >= SIMILARITY_THRESHOLD:
                union(i, j)

    clusters = defaultdict(list)
    for i, item in enumerate(items):
        clusters[find(i)].append(item)

    result = []
    for cluster in clusters.values():
        if len(cluster) == 1:
            result.append(cluster[0])
            continue

        official = [x for x in cluster if _is_official(x.get("source", ""))]
        news = [x for x in cluster if not _is_official(x.get("source", ""))]

        if official:
            result.extend(official)
        else:
            best = max(news, key=lambda x: _source_score(x.get("source", "")))
            result.append(best)

    return result
