"""
ResolveAI — Knowledge Article Model

Represents published knowledge base articles with pgvector embeddings
for grounded semantic search and RAG operations.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class KnowledgeArticle(Base, TimestampMixin):
    """
    Knowledge base article with pre-computed vector embedding.
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

    def __repr__(self) -> str:
        return f"<KnowledgeArticle id={self.id} title={self.title!r} category={self.category!r}>"
