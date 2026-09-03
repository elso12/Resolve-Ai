"""
ResolveAI — Enterprise Hybrid Search Engine

Combines:
1. Dense Vector Similarity Search (pgvector cosine_distance)
2. Sparse Lexical Search (PostgreSQL Full-Text Search ts_rank / BM25)
3. Reciprocal Rank Fusion (RRF with k = 60)
"""

from __future__ import annotations

import re

from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge import KnowledgeArticle
from app.services.rag_service import generate_embedding

logger = get_logger(__name__)

DEFAULT_RRF_K = 60


def reciprocal_rank_fusion(
    dense_results: list[tuple[KnowledgeArticle, float]],
    sparse_results: list[tuple[KnowledgeArticle, float]],
    k: int = DEFAULT_RRF_K,
) -> list[tuple[KnowledgeArticle, float, int | None, int | None]]:
    """
    Combines ranked lists using Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_Score(d) = SUM(1.0 / (k + rank_m(d)))

    Returns:
        List of (article, rrf_score, dense_rank, sparse_rank) ordered by rrf_score descending.
    """
    article_map: dict[int, KnowledgeArticle] = {}
    dense_ranks: dict[int, int] = {}
    sparse_ranks: dict[int, int] = {}

    for rank, (article, _) in enumerate(dense_results, start=1):
        article_map[article.id] = article
        dense_ranks[article.id] = rank

    for rank, (article, _) in enumerate(sparse_results, start=1):
        article_map[article.id] = article
        sparse_ranks[article.id] = rank

    fused_scores: list[tuple[KnowledgeArticle, float, int | None, int | None]] = []

    for art_id, article in article_map.items():
        d_rank = dense_ranks.get(art_id)
        s_rank = sparse_ranks.get(art_id)

        rrf_score = 0.0
        if d_rank is not None:
            rrf_score += 1.0 / (k + d_rank)
        if s_rank is not None:
            rrf_score += 1.0 / (k + s_rank)

        fused_scores.append((article, rrf_score, d_rank, s_rank))

    fused_scores.sort(key=lambda x: x[1], reverse=True)
    return fused_scores


async def execute_dense_vector_search(
    db: AsyncSession,
    organization_id: int,
    query: str,
    limit: int = 10,
) -> list[tuple[KnowledgeArticle, float]]:
    """
    Execute dense vector search using pgvector cosine distance (<=>).
    """
    try:
        query_vector = await generate_embedding(query)
        distance_expr = KnowledgeArticle.embedding.cosine_distance(query_vector).label("distance")

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
            similarity = max(0.0, min(1.0, 1.0 - dist_val))
            results.append((article, similarity))

        return results
    except Exception as exc:
        logger.warning("dense_vector_search_fallback", error=str(exc))
        # Fallback if embeddings are not configured or vector extension is in fallback mode
        stmt = (
            select(KnowledgeArticle)
            .where(
                KnowledgeArticle.organization_id == organization_id,
                KnowledgeArticle.is_published.is_(True),
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        return [(a, 0.5) for a in result.scalars().all()]


async def execute_sparse_lexical_search(
    db: AsyncSession,
    organization_id: int,
    query: str,
    limit: int = 10,
) -> list[tuple[KnowledgeArticle, float]]:
    """
    Execute sparse lexical search using PostgreSQL Full-Text Search (ts_rank),
    with enhanced token matching for error codes (e.g. ERR_AUTH_OAUTH_TIMEOUT) and SKUs.
    """
    clean_query = query.strip()
    if not clean_query:
        return []

    # Check dialect
    bind = db.bind
    dialect_name = bind.dialect.name if bind else "sqlite"

    if dialect_name == "postgresql":
        try:
            # PostgreSQL Full-Text Search via ts_rank_cd
            tsquery = func.plainto_tsquery("english", clean_query)
            rank_expr = func.ts_rank_cd(KnowledgeArticle.search_vector, tsquery).label("rank")

            stmt = (
                select(KnowledgeArticle, rank_expr)
                .where(
                    KnowledgeArticle.organization_id == organization_id,
                    KnowledgeArticle.is_published.is_(True),
                    KnowledgeArticle.search_vector.op("@@")(tsquery),
                )
                .order_by(desc(rank_expr))
                .limit(limit)
            )

            result = await db.execute(stmt)
            rows = result.all()
            if rows:
                return [(article, float(rank)) for article, rank in rows]
        except Exception as psql_err:
            logger.warning("postgres_fts_query_failed", error=str(psql_err))

    # Fallback / Cross-platform BM25-style lexical scoring
    # Prioritizes exact phrases, technical error codes (e.g. ERR_*), and term occurrences
    tokens = re.findall(r"[\w-]+", clean_query)
    conditions = []
    for token in tokens:
        pattern = f"%{token}%"
        conditions.append(KnowledgeArticle.title.ilike(pattern))
        conditions.append(KnowledgeArticle.content.ilike(pattern))

    stmt = select(KnowledgeArticle).where(
        KnowledgeArticle.organization_id == organization_id,
        KnowledgeArticle.is_published.is_(True),
        or_(*conditions) if conditions else True,
    )
    result = await db.execute(stmt)
    articles = list(result.scalars().all())

    scored_articles: list[tuple[KnowledgeArticle, float]] = []
    query_lower = clean_query.lower()

    for art in articles:
        score = 0.0
        title_lower = art.title.lower()
        content_lower = art.content.lower()

        # Exact query match boost (crucial for error codes)
        if query_lower in title_lower:
            score += 20.0
        if query_lower in content_lower:
            score += 15.0

        # Term matches
        for t in tokens:
            t_lower = t.lower()
            if t_lower in title_lower:
                score += 3.0
            if t_lower in content_lower:
                score += 1.0

        if score > 0.0:
            scored_articles.append((art, score))

    scored_articles.sort(key=lambda x: x[1], reverse=True)
    return scored_articles[:limit]


async def hybrid_search_articles(
    db: AsyncSession,
    organization_id: int,
    query: str,
    top_k: int = 5,
    rrf_k: int = DEFAULT_RRF_K,
) -> list[tuple[KnowledgeArticle, float, int | None, int | None]]:
    """
    Perform Enterprise Hybrid Search:
    1. Dense Vector Search (pgvector)
    2. Sparse Lexical Search (PostgreSQL FTS / BM25)
    3. Reciprocal Rank Fusion (RRF)
    """
    dense_results = await execute_dense_vector_search(
        db=db,
        organization_id=organization_id,
        query=query,
        limit=top_k * 2,
    )

    sparse_results = await execute_sparse_lexical_search(
        db=db,
        organization_id=organization_id,
        query=query,
        limit=top_k * 2,
    )

    fused = reciprocal_rank_fusion(
        dense_results=dense_results,
        sparse_results=sparse_results,
        k=rrf_k,
    )

    logger.info(
        "hybrid_search_executed",
        query=query,
        dense_count=len(dense_results),
        sparse_count=len(sparse_results),
        fused_count=len(fused),
    )

    return fused[:top_k]
