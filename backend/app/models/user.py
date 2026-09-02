"""
ResolveAI — User Model

Represents every human identity in the system — customers, agents,
managers, and admins alike.  Role-based access control (RBAC) is
driven by the ``role`` column.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import UserRole

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.customer import Customer
    from app.models.ticket import Ticket
    from app.models.ticket_message import TicketMessage


class User(TimestampMixin, Base):
    """
    Core identity model.

    Attributes:
        email:            Unique login identifier.
        hashed_password:  Argon2 / bcrypt digest — never store plaintext.
        full_name:        Display name for UI and notifications.
        role:             RBAC role (customer, agent, manager, admin).
        is_active:        Soft-delete / suspension flag.
        organization_id:  Tenant scope.
    """

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(
        String(320),
        unique=True,
        index=True,
        nullable=False,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        SAEnum(UserRole, name="user_role", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=UserRole.CUSTOMER,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="true",
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="users",
    )
    customer_profile: Mapped["Customer | None"] = relationship(
        "Customer",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    assigned_tickets: Mapped[list["Ticket"]] = relationship(
        "Ticket",
        back_populates="assigned_agent",
        foreign_keys="Ticket.assigned_agent_id",
    )
    sent_messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="sender",
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email!r} role={self.role.value}>"
