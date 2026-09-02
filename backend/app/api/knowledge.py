"""
ResolveAI — Knowledge Base & RAG Endpoints

Handles article listing, management, and grounded Q&A generation via pgvector.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.knowledge import KnowledgeArticle
from app.models.user import User
from app.schemas.knowledge import (
    AskRequest,
    AskResponse,
    HybridSearchResult,
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
)
from app.services.hybrid_search_service import hybrid_search_articles
from app.services.rag_service import answer_question_with_rag, generate_embedding, slugify

logger = get_logger(__name__)

router = APIRouter(prefix="/knowledge", tags=["Knowledge Base & RAG"])


@router.get("/articles", response_model=list[KnowledgeArticleOut])
async def list_articles(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Text search filter"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> list[KnowledgeArticle]:
    """
    List published knowledge base articles.
    """
    stmt = select(KnowledgeArticle).where(KnowledgeArticle.is_published.is_(True))

    if category:
        stmt = stmt.where(KnowledgeArticle.category.ilike(f"%{category}%"))

    if search:
        search_pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                KnowledgeArticle.title.ilike(search_pattern),
                KnowledgeArticle.content.ilike(search_pattern),
            )
        )

    stmt = stmt.order_by(KnowledgeArticle.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/search", response_model=list[HybridSearchResult])
async def search_articles(
    q: str = Query(..., min_length=1, description="Query string for Enterprise Hybrid Search"),
    limit: int = Query(5, ge=1, le=20),
    db: Annotated[AsyncSession, Depends(get_db)] = None,
    current_user: Annotated[User, Depends(get_current_user)] = None,
) -> list[dict[str, Any]]:
    """
    Enterprise Hybrid Search combining Dense Vector pgvector + Sparse Lexical FTS + RRF.
    """
    org_id = current_user.organization_id if current_user else 1
    fused_results = await hybrid_search_articles(
        db=db,
        organization_id=org_id,
        query=q,
        top_k=limit,
    )
    return [
        {
            "article": article,
            "rrf_score": round(score, 5),
            "dense_rank": d_rank,
            "sparse_rank": s_rank,
        }
        for article, score, d_rank, s_rank in fused_results
    ]


@router.get("/articles/{slug}", response_model=KnowledgeArticleOut)
async def get_article_by_slug(
    slug: str,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeArticle:
    """
    Get a single published article by its slug.
    """
    stmt = select(KnowledgeArticle).where(
        KnowledgeArticle.slug == slug,
        KnowledgeArticle.is_published.is_(True),
    )
    result = await db.execute(stmt)
    article = result.scalar_one_or_none()

    if not article:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Article not found",
        )

    return article


async def async_generate_article_embedding(article_id: int, full_text: str) -> None:
    """Asynchronously compute and store vector embedding for article."""
    from app.db.session import async_session_factory
    from app.services.rag_service import generate_embedding

    try:
        vec = await generate_embedding(full_text)
        async with async_session_factory() as db:
            stmt = select(KnowledgeArticle).where(KnowledgeArticle.id == article_id)
            res = await db.execute(stmt)
            art = res.scalar_one_or_none()
            if art:
                art.embedding = vec
                await db.commit()
                logger.info("async_article_embedding_saved", article_id=article_id)
    except Exception as exc:
        logger.error("async_article_embedding_failed", article_id=article_id, error=str(exc))


@router.post("/articles", response_model=KnowledgeArticleOut, status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: KnowledgeArticleCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeArticle:
    """
    Create a new knowledge article (< 100ms response time).
    Vector embedding is computed and persisted asynchronously via BackgroundTasks.
    Requires Agent, Manager, or Admin role.
    """
    base_slug = slugify(payload.title)
    slug = base_slug
    
    # Ensure unique slug
    counter = 1
    while True:
        stmt = select(KnowledgeArticle).where(KnowledgeArticle.slug == slug)
        res = await db.execute(stmt)
        if not res.scalar_one_or_none():
            break
        slug = f"{base_slug}-{counter}"
        counter += 1

    article = KnowledgeArticle(
        title=payload.title,
        slug=slug,
        content=payload.content,
        category=payload.category,
        is_published=payload.is_published,
        embedding=None,
        organization_id=current_user.organization_id,
    )

    db.add(article)
    await db.flush()
    await db.refresh(article)

    # Dispatch embedding generation to non-blocking background queue
    full_text = f"{payload.title}\n\n{payload.content}"
    background_tasks.add_task(async_generate_article_embedding, article.id, full_text)

    logger.info(
        "knowledge_article_created_fast",
        article_id=article.id,
        slug=article.slug,
        author_id=current_user.id,
    )

    return article


@router.post("/ask", response_model=AskResponse)
async def ask_knowledge_base(
    payload: AskRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> AskResponse:
    """
    RAG endpoint for grounded self-service answers.
    Retrieves most relevant articles via pgvector and synthesizes an answer with citations.
    """
    org_id = current_user.organization_id if current_user else 1

    logger.info("rag_query_received", question=payload.question, org_id=org_id)
    response = await answer_question_with_rag(
        db=db,
        organization_id=org_id,
        question=payload.question,
    )

    return response
