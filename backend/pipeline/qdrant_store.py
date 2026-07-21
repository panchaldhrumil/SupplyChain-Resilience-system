import uuid

from pipeline.settings import QDRANT_URL, QDRANT_API_KEY, QDRANT_COLLECTION, GEMINI_API_KEY

VECTOR_SIZE = 3072


def get_client():
    if not QDRANT_URL:
        return None
    try:
        from qdrant_client import QdrantClient
        return QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY or None)
    except ImportError:
        print("[Qdrant] qdrant-client not installed — pip install qdrant-client")
        return None
    except Exception as e:
        print(f"[Qdrant] connection failed: {e}")
        return None


def ensure_collection(client, vector_size=VECTOR_SIZE):
    try:
        from qdrant_client.models import Distance, VectorParams, PayloadSchemaType
        names = [c.name for c in client.get_collections().collections]
        if QDRANT_COLLECTION not in names:
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            )
            print(f"[Qdrant] Created collection: {QDRANT_COLLECTION} (size={vector_size})")
        else:
            info = client.get_collection(collection_name=QDRANT_COLLECTION)
            existing_size = info.config.params.vectors.size
            if existing_size != vector_size:
                client.delete_collection(collection_name=QDRANT_COLLECTION)
                client.create_collection(
                    collection_name=QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
                )
                print(f"[Qdrant] Re-created collection {QDRANT_COLLECTION} with size={vector_size}")

        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name="corridor",
                field_schema=PayloadSchemaType.KEYWORD,
            )
        except Exception:
            pass

    except Exception as e:
        print(f"[Qdrant] ensure_collection: {e}")


def embed_text(text, api_key=None):
    key = api_key or GEMINI_API_KEY
    if not key or key.startswith("your_"):
        return None

    candidate_models = [
        "models/gemini-embedding-001",
        "gemini-embedding-001",
        "models/gemini-embedding-2",
    ]

    try:
        from google import genai
        client = genai.Client(api_key=key)
        for m in candidate_models:
            try:
                result = client.models.embed_content(
                    model=m,
                    contents=str(text)[:2000],
                )
                if result.embeddings:
                    return list(result.embeddings[0].values)
            except Exception:
                continue
        return None
    except Exception as e:
        print(f"[Qdrant] embed_text: {e}")
        return None


def upsert_articles(articles, api_key=None):
    client = get_client()
    if not client:
        return
    ensure_collection(client)
    try:
        from qdrant_client.models import PointStruct
        points = []
        for art in articles:
            link = art.get("link", "")
            if not link:
                continue
            text = (
                f"{art.get('title', '')} "
                f"{art.get('key_takeaway', '')} "
                f"{str(art.get('article_text_snippet', ''))[:300]}"
            ).strip()
            if not text:
                continue
            vector = embed_text(text, api_key)
            if not vector:
                continue
            ensure_collection(client, vector_size=len(vector))
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, link))
            points.append(PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "title":                art.get("title", ""),
                    "source":               art.get("source", ""),
                    "link":                 link,
                    "key_takeaway":         art.get("key_takeaway", ""),
                    "article_text_snippet": str(art.get("article_text_snippet", ""))[:500],
                    "corridor":             str(art.get("corridor", "none")),
                    "date":                 str(art.get("date", "")),
                    "category":             art.get("category", ""),
                    "severity":             int(art.get("severity", 0) or 0),
                },
            ))
        if points:
            client.upsert(collection_name=QDRANT_COLLECTION, points=points)
            print(f"[Qdrant] Upserted {len(points)} articles to Qdrant Cloud!")
    except Exception as e:
        print(f"[Qdrant] upsert_articles: {e}")


def search_by_corridor(corridor, query_text, limit=5, api_key=None):
    client = get_client()
    if not client:
        return []
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        vector = embed_text(query_text, api_key)
        if not vector:
            return []
        ensure_collection(client, vector_size=len(vector))

        if hasattr(client, "query_points"):
            res = client.query_points(
                collection_name=QDRANT_COLLECTION,
                query=vector,
                query_filter=Filter(
                    must=[FieldCondition(key="corridor", match=MatchValue(value=corridor))]
                ),
                limit=limit,
            )
            return [p.payload for p in res.points]
        elif hasattr(client, "search"):
            results = client.search(
                collection_name=QDRANT_COLLECTION,
                query_vector=vector,
                query_filter=Filter(
                    must=[FieldCondition(key="corridor", match=MatchValue(value=corridor))]
                ),
                limit=limit,
            )
            return [hit.payload for hit in results]
        return []
    except Exception as e:
        print(f"[Qdrant] search_by_corridor: {e}")
        return []
