"""
ResolveAI — RAG (Retrieval-Augmented Generation) Engine

Implements text chunking, OpenAI embeddings (text-embedding-3-small),
pgvector cosine distance similarity retrieval, and strict grounded answer generation.
"""

from __future__ import annotations

import asyncio
import math
import re
from typing import TYPE_CHECKING

from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.knowledge import KnowledgeArticle
from app.schemas.knowledge import ArticleRef, AskResponse

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

FALLBACK_UNAVAILABLE_MESSAGE = (
    "I cannot find this in our knowledge base; let me connect you with a human agent."
)

# Initialise OpenAI client if key is configured
openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None


def slugify(text: str) -> str:
    """Generate a clean URL-friendly slug from title."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "article"


def recursive_character_chunk(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 50,
) -> list[str]:
    """
    Splits text recursively using paragraphs, linebreaks, sentences, and words.
    """
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    separators = ["\n\n", "\n", ". ", " ", ""]
    
    def _split(t: str, seps: list[str]) -> list[str]:
        if not t.strip():
            return []
        if not seps or len(t) <= chunk_size:
            return [t]
        
        sep = seps[0]
        splits = t.split(sep) if sep else list(t)
        chunks: list[str] = []
        current = ""
        
        for piece in splits:
            candidate = current + (sep if current and sep else "") + piece
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    chunks.append(current.strip())
                if len(piece) > chunk_size and len(seps) > 1:
                    chunks.extend(_split(piece, seps[1:]))
                    current = ""
                else:
                    current = piece
        
        if current.strip():
            chunks.append(current.strip())
            
        return chunks

    raw_chunks = _split(text, separators)
    
    # Apply overlap merging
    overlapped: list[str] = []
    for i, c in enumerate(raw_chunks):
        if i > 0 and chunk_overlap > 0:
            overlap_prefix = raw_chunks[i - 1][-chunk_overlap:]
            c = overlap_prefix + " " + c
        overlapped.append(c.strip())
        
    return overlapped


def _deterministic_mock_embedding(text: str, dim: int = 1536) -> list[float]:
    """Generates a stable pseudo-embedding vector for offline testing."""
    import hashlib
    h = hashlib.sha256(text.encode("utf-8")).digest()
    vals = []
    for i in range(dim):
        b = h[i % len(h)]
        val = math.sin((b + i) * 0.1)
        vals.append(val)
    # L2 normalize
    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


async def generate_embedding(text: str) -> list[float]:
    """
    Generate 1536-dimensional vector embedding via OpenAI text-embedding-3-small.
    Falls back gracefully if key is not configured or on network timeout.
    """
    if not openai_client:
        logger.info("embedding_mock_fallback", reason="No OPENAI_API_KEY")
        return _deterministic_mock_embedding(text)

    try:
        response = await asyncio.wait_for(
            openai_client.embeddings.create(
                model="text-embedding-3-small",
                input=text.replace("\n", " ")[:8000],
            ),
            timeout=4.0,
        )
        return response.data[0].embedding
    except Exception as e:
        logger.warning("embedding_generation_failed", error=str(e))
        return _deterministic_mock_embedding(text)


async def search_similar_articles(
    db: AsyncSession,
    organization_id: int,
    query_embedding: list[float],
    limit: int = 3,
    max_cosine_distance: float = 0.65,
) -> list[tuple[KnowledgeArticle, float]]:
    """
    Perform vector cosine similarity search in PostgreSQL using pgvector (<=>).
    Returns list of (KnowledgeArticle, similarity_score).
    """
    try:
        # cosine_distance: 0.0 = identical, 2.0 = opposite
        distance_expr = KnowledgeArticle.embedding.cosine_distance(query_embedding).label("distance")
        
        stmt = (
            select(KnowledgeArticle, distance_expr)
            .where(
                KnowledgeArticle.organization_id == organization_id,
                KnowledgeArticle.is_published.is_(True),
                KnowledgeArticle.embedding.is_not(None),
            )
            .order_by(distance_expr.asc())
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        rows = result.all()
        
        results: list[tuple[KnowledgeArticle, float]] = []
        for article, distance in rows:
            dist_val = float(distance) if distance is not None else 1.0
            if dist_val <= max_cosine_distance:
                similarity = max(0.0, min(1.0, 1.0 - dist_val))
                results.append((article, similarity))
                
        return results
    except Exception as e:
        logger.error("pgvector_search_failed", error=str(e))
        # Fallback text search if pgvector query fails in environments where vector extension is initializing
        stmt = (
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.organization_id == organization_id,
                KnowledgeArticle.is_published.is_(True),
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        articles = result.scalars().all()
        return [(a, 0.75) for a in articles]


async def answer_question_with_rag(
    db: AsyncSession,
    organization_id: int,
    question: str,
) -> AskResponse:
    """
    Execute full RAG pipeline:
    1. Embed query
    2. Retrieve grounded context via pgvector
    3. Generate response strictly grounded on retrieved articles
    """
    from app.services.hybrid_search_service import hybrid_search_articles

    hybrid_results = await hybrid_search_articles(
        db=db,
        organization_id=organization_id,
        query=question,
        top_k=3,
        rrf_k=60,
    )

    if not hybrid_results:
        return AskResponse(
            answer=FALLBACK_UNAVAILABLE_MESSAGE,
            sources=[],
        )

    # Format retrieved contexts
    context_blocks: list[str] = []
    source_refs: list[ArticleRef] = []

    for article, rrf_score, dense_rank, sparse_rank in hybrid_results:
        snippet = article.content[:300].strip() + ("..." if len(article.content) > 300 else "")
        context_blocks.append(
            f"=== ARTICLE: {article.title} (Slug: {article.slug}, Category: {article.category}) ===\n{article.content}"
        )
        source_refs.append(
            ArticleRef(
                id=article.id,
                title=article.title,
                slug=article.slug,
                category=article.category,
                similarity_score=round(rrf_score, 4),
                snippet=snippet,
            )
        )

    full_context = "\n\n".join(context_blocks)

    if not openai_client:
        # Grounded heuristic answer when offline
        primary_article = hybrid_results[0][0]
        heuristic_answer = (
            f"Based on our knowledge base article **'{primary_article.title}'**:\n\n"
            f"{primary_article.content[:400]}...\n\n"
            f"*(Source: [{primary_article.title}](/help/articles/{primary_article.slug}))*"
        )
        try:
            from app.services.ai_telemetry_service import log_ai_interaction
            await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="RAG_ANSWER",
                model_name="mock-heuristic",
                prompt_tokens=max(1, len(full_context) // 4),
                completion_tokens=max(1, len(heuristic_answer) // 4),
                latency_ms=35.0,
            )
        except Exception:
            pass
        return AskResponse(answer=heuristic_answer, sources=source_refs)

    prompt = f"""
You are a helpful, professional AI support assistant for ResolveAI.
Answer the customer's question using ONLY the provided Knowledge Base context below.

STRICT GROUNDING RULES:
1. Base your answer EXCLUSIVELY on the provided article context. Do NOT invent facts, URLs, or instructions not present in the text.
2. Explicitly reference the article title(s) in your answer (e.g. "According to '[Article Title]'...").
3. If the provided context does NOT contain enough information to directly and accurately answer the question, output EXACTLY this sentence and nothing else:
"{FALLBACK_UNAVAILABLE_MESSAGE}"

=== KNOWLEDGE BASE CONTEXT ===
{full_context}

=== CUSTOMER QUESTION ===
{question}
"""

    try:
        completion = await asyncio.wait_for(
            openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a strictly grounded AI knowledge assistant. You answer questions only from provided context with exact citations.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=400,
            ),
            timeout=5.0,
        )
        answer = completion.choices[0].message.content.strip() if completion.choices[0].message.content else FALLBACK_UNAVAILABLE_MESSAGE

        if FALLBACK_UNAVAILABLE_MESSAGE in answer:
            return AskResponse(answer=FALLBACK_UNAVAILABLE_MESSAGE, sources=[])

        return AskResponse(answer=answer, sources=source_refs)

    except Exception as e:
        logger.error("rag_generation_error", error=str(e))
        return AskResponse(
            answer=f"According to **{similar_articles[0][0].title}**:\n\n{similar_articles[0][0].content[:300]}...",
            sources=source_refs,
        )
