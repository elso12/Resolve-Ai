"""
ResolveAI — Knowledge Article Model

Represents published knowledge base articles with pgvector embeddings and
PostgreSQL tsvector columns for enterprise hybrid search (pgvector + FTS + RRF).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, Index, String, Text, event, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class KnowledgeArticle(Base, TimestampMixin):
    """
    Knowledge base article with pre-computed vector embedding and full-text search vector.
    """

    __tablename__ = "knowledge_article"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(100), default="General", index=True, nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)

    # 1536-dimensional vector for OpenAI text-embedding-3-small
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536), nullable=True)

    # PostgreSQL Full-Text Search tsvector (GIN indexed)
    search_vector: Mapped[Any | None] = mapped_column(TSVECTOR, nullable=True)

    # ── Foreign keys ─────────────────────────────────────────────────────
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped[Organization] = relationship(
        "Organization",
        lazy="select",
    )

    __table_args__ = (
        Index(
            "ix_knowledge_article_search_vector",
            "search_vector",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeArticle id={self.id} title={self.title!r} category={self.category!r}>"


@event.listens_for(KnowledgeArticle, "before_insert")
@event.listens_for(KnowledgeArticle, "before_update")
def update_article_search_vector(mapper: Any, connection: Any, target: KnowledgeArticle) -> None:
    """Synchronize search_vector on insert/update."""
    text_corpus = f"{target.title or ''} {target.content or ''}".strip()
    if connection.dialect.name == "postgresql":
        target.search_vector = func.to_tsvector("english", text_corpus)
    else:
        target.search_vector = text_corpus
