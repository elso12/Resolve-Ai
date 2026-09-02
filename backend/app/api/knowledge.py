"""
ResolveAI — Knowledge Base & RAG Endpoints

Handles article listing, management, and grounded Q&A generation via pgvector.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
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
    KnowledgeArticleCreate,
    KnowledgeArticleOut,
)
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


@router.post("/articles", response_model=KnowledgeArticleOut, status_code=status.HTTP_201_CREATED)
async def create_article(
    payload: KnowledgeArticleCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KnowledgeArticle:
    """
    Create a new knowledge article with automatic vector embedding generation.
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

    # Generate 1536-dim embedding for Title + Content
    full_text = f"{payload.title}\n\n{payload.content}"
    embedding_vector = await generate_embedding(full_text)

    article = KnowledgeArticle(
        title=payload.title,
        slug=slug,
        content=payload.content,
        category=payload.category,
        is_published=payload.is_published,
        embedding=embedding_vector,
        organization_id=current_user.organization_id,
    )

    db.add(article)
    await db.flush()
    await db.refresh(article)

    logger.info(
        "knowledge_article_created",
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
