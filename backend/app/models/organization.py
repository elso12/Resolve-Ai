"""
ResolveAI — Organization Model

Multi-tenant root entity.  Every User, Customer, and Ticket is scoped
to exactly one Organization, enabling data isolation at the query level.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ticket import Ticket


class Organization(TimestampMixin, Base):
    """
    A tenant entity representing a company or team using the platform.

    Attributes:
        name:  Display name (e.g. "Acme Corp").
        slug:  URL-safe identifier, unique across the system.
    """

    __tablename__ = "organization"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # ── Relationships ────────────────────────────────────────────────────
    users: Mapped[list["User"]] = relationship(
        "User",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="organization",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Organization id={self.id} slug={self.slug!r}>"
