"""
ResolveAI — Ticket Model

Core domain entity representing a support request.  Status transitions
are governed by the finite state machine in
``app.services.ticket_service``.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.enums import TicketStatus, TicketPriority, TicketCategory

if TYPE_CHECKING:
    from app.models.customer import Customer
    from app.models.organization import Organization
    from app.models.user import User
    from app.models.ticket_message import TicketMessage


class Ticket(TimestampMixin, Base):
    """
    A customer support ticket with SLA monitoring capabilities.

    Attributes:
        ticket_number:      Human-readable identifier (e.g. ``RSV-2026-A3F7B``).
        subject:            One-line summary of the issue.
        description:        Full problem description (rich text / markdown).
        status:             Current lifecycle state (FSM-governed).
        priority:           SLA-tier priority.
        category:           Classification bucket for routing / analytics.
        customer_id:        The customer who opened the ticket.
        assigned_agent_id:  The agent currently working the ticket (nullable).
        organization_id:    Tenant scope.
        first_response_due_at: Computed SLA first response deadline.
        resolution_due_at:     Computed SLA resolution deadline.
        first_responded_at:    Timestamp when first public agent response was sent.
        resolved_at:           Timestamp when ticket reached resolved/closed state.
        sla_first_response_breached: Boolean indicating first response deadline violation.
        sla_resolution_breached:     Boolean indicating resolution deadline violation.
    """

    __tablename__ = "ticket"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_number: Mapped[str] = mapped_column(
        String(30),
        unique=True,
        index=True,
        nullable=False,
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=TicketStatus.OPEN,
        server_default=TicketStatus.OPEN.value,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=TicketPriority.MEDIUM,
        server_default=TicketPriority.MEDIUM.value,
    )
    category: Mapped[TicketCategory] = mapped_column(
        SAEnum(TicketCategory, name="ticket_category", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=TicketCategory.GENERAL,
        server_default=TicketCategory.GENERAL.value,
    )
    
    ai_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── SLA Tracking ─────────────────────────────────────────────────────
    first_response_due_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    resolution_due_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )
    first_responded_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    sla_first_response_breached: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        index=True,
    )
    sla_resolution_breached: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        server_default="false",
        nullable=False,
        index=True,
    )

    # ── Foreign keys ─────────────────────────────────────────────────────
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customer.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ── Relationships ────────────────────────────────────────────────────
    customer: Mapped["Customer"] = relationship(
        "Customer",
        back_populates="tickets",
    )
    assigned_agent: Mapped["User | None"] = relationship(
        "User",
        back_populates="assigned_tickets",
        foreign_keys=[assigned_agent_id],
    )
    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="tickets",
    )
    messages: Mapped[list["TicketMessage"]] = relationship(
        "TicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="TicketMessage.created_at",
    )

    def __repr__(self) -> str:
        status_val = self.status.value if self.status is not None else "None"
        prio_val = self.priority.value if self.priority is not None else "None"
        return (
            f"<Ticket id={self.id} number={self.ticket_number!r} "
            f"status={status_val} priority={prio_val}>"
        )
