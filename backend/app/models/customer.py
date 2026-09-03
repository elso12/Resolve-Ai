"""
ResolveAI — Customer Model

Extended profile for users with the ``CUSTOMER`` role.  Linked
one-to-one with ``User`` to keep the core identity table lean while
still capturing customer-specific attributes (plan tier, company).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.ticket import Ticket


class Customer(TimestampMixin, Base):
    """
    Customer-specific profile (1-to-1 extension of ``User``).

    Attributes:
        user_id:       FK to the owning User record.
        plan:          Subscription tier (Free / Pro / Enterprise).
        company_name:  Optional company the customer represents.
    """

    __tablename__ = "customer"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    plan: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="Free",
        server_default="Free",
    )
    company_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    user: Mapped["User"] = relationship(
        "User",
        back_populates="customer_profile",
    )
    tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="customer",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    def __repr__(self) -> str:
        return f"<Customer id={self.id} user_id={self.user_id} plan={self.plan!r}>"
