"""
services/rag_service.py

WHAT THIS FILE DOES:
This is the actual RAG engine — the piece that was previously just an
empty table. It does two things:

  1. `ingest_document()` — takes parsed text (from document_parser.py),
     chunks it (text_chunker.py), embeds each chunk (embedding_service.py),
     and stores the vectors in a Qdrant collection scoped to ONE company.
     Collection naming is `kb_{company_id}` — this is what guarantees
     "no mixing between customers": Company A's vectors physically live
     in a different collection than Company B's, so a search can never
     leak across tenants even by bug, since the collection name itself
     is the isolation boundary.

  2. `query()` — takes a natural-language question (from a live call, via
     action_handler.py), embeds it, searches the company's collection for
     the most similar chunks, and returns the matched text so the agent
     can answer from real business data instead of guessing.

Uses Qdrant in local file-mode by default (QDRANT_URL unset -> stores at
./qdrant_data) so this works without any external service for local dev
and testing. Point QDRANT_URL at a real Qdrant Cloud/self-hosted instance
for production — same code, just change the .env value.
"""

import uuid
import math
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from rank_bm25 import BM25Okapi

from app.core.config import settings
from app.services.text_chunker import chunk_text
from app.services.embedding_service import embed_texts, embed_query, EMBEDDING_DIMENSIONS
from app.services.reranker_service import rerank as rerank_candidates

_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    global _client
    if _client is None:
        if settings.QDRANT_URL and settings.QDRANT_URL.startswith("http"):
            _client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY or None)
        else:
            # Local on-disk mode — zero external dependencies, good for dev/small deployments.
            _client = QdrantClient(path="./qdrant_data")
    return _client


def _collection_name(company_id: str | uuid.UUID) -> str:
    return f"kb_{company_id}"


def _ensure_collection(company_id: str | uuid.UUID) -> str:
    client = _get_client()
    name = _collection_name(company_id)
    if not client.collection_exists(name):
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBEDDING_DIMENSIONS, distance=Distance.COSINE),
        )
    return name


def ingest_document(company_id: str | uuid.UUID, kb_item_id: str | uuid.UUID, text: str, category: str | None = None, file_name: str | None = None) -> int:
    """
    Chunks + embeds + stores `text` into this company's collection.
    Returns the number of chunks stored. Called by
    api/routes/knowledge_base_routes.py after document_parser.extract_text().
    """
    chunks = chunk_text(text)
    if not chunks:
        return 0

    vectors = embed_texts(chunks)
    collection = _ensure_collection(company_id)
    client = _get_client()

    points = [
        PointStruct(
            id=str(uuid.uuid4()),
            vector=vector,
            payload={
                "text": chunk,
                "kb_item_id": str(kb_item_id),
                "category": category,
                "file_name": file_name,
            },
        )
        for chunk, vector in zip(chunks, vectors)
    ]
    client.upsert(collection_name=collection, points=points)
    invalidate_cache(company_id)
    return len(chunks)


_query_cache: dict[str, list[dict]] = {}  # kept for backward-compat invalidation by prefix
_semantic_cache: dict[str, list[dict]] = {}  # company_id -> list of {"question", "vector", "category", "results"}
_CACHE_MAX_SIZE = 500
_SEMANTIC_CACHE_MAX_PER_COMPANY = 200
_SEMANTIC_SIMILARITY_THRESHOLD = 0.93  # cosine similarity above this = "close enough" to reuse cached answer


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def _check_semantic_cache(company_id: str, question_vector: list[float], category: str | None) -> list[dict] | None:
    """
    Unlike a plain string cache, this catches PARAPHRASES: "what time do
    you close" and "when do you shut" embed close together even though
    the text is completely different, so the second question reuses the
    first's cached answer instead of re-searching + re-ranking from
    scratch. This matters a lot in live voice calls, where callers ask
    the same underlying question in many different phrasings.
    """
    entries = _semantic_cache.get(str(company_id), [])
    for entry in entries:
        if entry["category"] != category:
            continue
        similarity = _cosine_similarity(question_vector, entry["vector"])
        if similarity >= _SEMANTIC_SIMILARITY_THRESHOLD:
            return entry["results"]
    return None


def _store_semantic_cache(company_id: str, question_vector: list[float], category: str | None, results: list[dict]) -> None:
    key = str(company_id)
    entries = _semantic_cache.setdefault(key, [])
    entries.append({"vector": question_vector, "category": category, "results": results})
    if len(entries) > _SEMANTIC_CACHE_MAX_PER_COMPANY:
        entries.pop(0)


def _get_all_chunks(company_id: str | uuid.UUID) -> list[dict]:
    """
    Fetches every stored chunk for a company (payload + id) — used to
    build the BM25 keyword index at query time. Fine for the chunk
    volumes a single business generates (hundreds to low thousands);
    for very large knowledge bases this would move to a persistent BM25
    index instead of rebuilding per query.
    """
    client = _get_client()
    collection = _collection_name(company_id)
    if not client.collection_exists(collection):
        return []

    points, _ = client.scroll(collection_name=collection, limit=10000, with_payload=True, with_vectors=False)
    return [{"id": p.id, "payload": p.payload} for p in points]


def query(company_id: str | uuid.UUID, question: str, top_k: int = 4, category: str | None = None) -> list[dict]:
    """
    Three-stage retrieval, in order:

      1. SEMANTIC CACHE CHECK — embeds the question and checks if a
         near-identical question (by meaning, not exact text) was asked
         recently for this company. Catches paraphrases like "what time
         do you close" vs "when do you shut", which a plain string cache
         would miss entirely.

      2. HYBRID SEARCH — combines vector/semantic search (Qdrant cosine
         similarity, good at matching MEANING) with BM25 keyword search
         (good at matching EXACT terms like SKUs, prices, proper nouns),
         fused via Reciprocal Rank Fusion. Retrieves a wider candidate
         set (3x top_k) than we ultimately need, since stage 3 will
         narrow it back down more accurately.

      3. CROSS-ENCODER RERANK — re-scores each candidate chunk jointly
         against the question (not just comparing two separate vectors),
         which is meaningfully more accurate than retrieval scores alone.
         This is the standard "retrieve then rerank" production RAG
         pattern.

    `category` optionally filters to a specific knowledge base category.
    Returns [] if the company has no knowledge base yet.
    """
    query_vector = embed_query(question)

    cached = _check_semantic_cache(str(company_id), query_vector, category)
    if cached is not None:
        return cached

    client = _get_client()
    collection = _collection_name(company_id)
    if not client.collection_exists(collection):
        return []

    # ---- Stage 1: vector/semantic search ----
    vector_results = client.query_points(collection_name=collection, query=query_vector, limit=top_k * 3).points
    vector_ranked_ids = [str(r.id) for r in vector_results]
    vector_payloads = {str(r.id): r.payload for r in vector_results}

    # ---- Stage 2: BM25 keyword search ----
    all_chunks = _get_all_chunks(company_id)
    if category:
        all_chunks = [c for c in all_chunks if c["payload"].get("category") == category]

    bm25_ranked_ids: list[str] = []
    bm25_payloads: dict[str, dict] = {}
    if all_chunks:
        tokenized_corpus = [c["payload"].get("text", "").lower().split() for c in all_chunks]
        bm25 = BM25Okapi(tokenized_corpus)
        scores = bm25.get_scores(question.lower().split())
        ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[: top_k * 3]
        for i in ranked_indices:
            if scores[i] <= 0:
                continue
            chunk_id = str(all_chunks[i]["id"])
            bm25_ranked_ids.append(chunk_id)
            bm25_payloads[chunk_id] = all_chunks[i]["payload"]

    # ---- Fuse rankings: Reciprocal Rank Fusion ----
    rrf_scores: dict[str, float] = {}
    k = 60
    for rank, chunk_id in enumerate(vector_ranked_ids):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank + 1)
    for rank, chunk_id in enumerate(bm25_ranked_ids):
        rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0) + 1 / (k + rank + 1)

    all_payloads = {**vector_payloads, **bm25_payloads}
    # Take a WIDER candidate set into reranking than the final top_k, since
    # reranking is what does the precise final narrowing.
    fused = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[: top_k * 3]

    candidates = [
        {
            "text": all_payloads[chunk_id].get("text"),
            "score": round(score, 4),
            "category": all_payloads[chunk_id].get("category"),
            "file_name": all_payloads[chunk_id].get("file_name"),
        }
        for chunk_id, score in fused
        if chunk_id in all_payloads
    ]

    # ---- Stage 3: cross-encoder rerank ----
    results = rerank_candidates(question, candidates, top_k=top_k)

    _store_semantic_cache(str(company_id), query_vector, category, results)
    return results


def invalidate_cache(company_id: str | uuid.UUID) -> None:
    """Call after ingesting/deleting a document so stale cached answers aren't served."""
    global _query_cache, _semantic_cache
    prefix = f"{company_id}|"
    _query_cache = {k: v for k, v in _query_cache.items() if not k.startswith(prefix)}
    _semantic_cache.pop(str(company_id), None)


def delete_document(company_id: str | uuid.UUID, kb_item_id: str | uuid.UUID) -> None:
    """Removes all chunks belonging to one uploaded document (e.g. when the user deletes it)."""
    from qdrant_client.models import Filter, FieldCondition, MatchValue

    client = _get_client()
    collection = _collection_name(company_id)
    if not client.collection_exists(collection):
        return

    client.delete(
        collection_name=collection,
        points_selector=Filter(
            must=[FieldCondition(key="kb_item_id", match=MatchValue(value=str(kb_item_id)))]
        ),
    )
    invalidate_cache(company_id)


 # Conservative cutoff for the cross-encoder reranker's raw score.
    # ms-marco-MiniLM-style cross-encoders output unbounded relevance
    # logits (not 0-1 probabilities) — strongly negative scores (below
    # roughly -3) reliably indicate the match is NOT actually relevant
    # to the question. This is intentionally conservative: it only
    # filters out matches that are clearly off-topic, leaving anything
    # borderline to the LLM's own honesty check in the generation step
    # (see rag_generation_service.py's system prompt), since a single
    # hard-coded number can't perfectly judge nuanced relevance.
    MINIMUM_RERANK_CONFIDENCE = -3.0
 
 
def answer_from_knowledge_base(
        company_id: str | uuid.UUID,
        question: str,
        conversation_context: str = "",
) -> str:
        """
        The full enterprise RAG pipeline, in order:
 
          1. REWRITE — if conversation_context is provided (e.g. recent
             call transcript), rewrite vague follow-up questions like
             "what about for kids?" into standalone searchable queries
             like "what is the pediatric checkup pricing?" before
             retrieval even runs. See query_rewriter_service.py.
 
          2. RETRIEVE — hybrid search (vector + keyword) + cross-encoder
             rerank + semantic cache, exactly as before.
 
          3. CONFIDENCE CHECK — if the best match's rerank score is
             clearly too low to be relevant, skip generation entirely
             and return an honest "I don't have that information"
             response immediately — faster and cheaper than asking an
             LLM to generate from garbage context.
 
          4. GENERATE — turn the retrieved chunks into a clean, natural
             answer via Groq. The generation prompt ALSO independently
             instructs the model to admit when the context doesn't
             actually answer the question — a second, more nuanced
             safety net beyond the numeric pre-filter.
        """
        from app.services.query_rewriter_service import rewrite_query
        from app.services.rag_generation_service import generate_answer
 
        search_query = rewrite_query(question, conversation_context) if conversation_context else question
 
        matches = query(company_id, search_query, top_k=3)
        if not matches:
            return "I don't have that information available right now, but I can have someone follow up with you."
 
        # Fast numeric pre-filter — only trust this when a rerank_score
        # is actually present (it won't be if the reranker fell back
        # due to a local model issue — in that case we skip this check
        # and rely entirely on the generation step's honesty instruction).
        top_match = matches[0]
        if "rerank_score" in top_match and top_match["rerank_score"] < MINIMUM_RERANK_CONFIDENCE:
            return "I don't have that specific information available right now, but I can have someone follow up with you."
 
        context_chunks = [m["text"] for m in matches if m.get("text")]
        return generate_answer(search_query, context_chunks)