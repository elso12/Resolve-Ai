"""
ResolveAI — TicketMessage Model

Conversation thread entries attached to a ticket.  Both customer-facing
replies and internal agent notes live here, distinguished by the
``is_internal`` flag.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ticket import Ticket
    from app.models.user import User


class TicketMessage(TimestampMixin, Base):
    """
    A single message in a ticket's conversation thread.

    Attributes:
        ticket_id:    The parent ticket.
        sender_id:    The user who authored this message.
        body:         Message content (plain text or markdown).
        is_internal:  If ``True``, visible only to agents / managers.
    """

    __tablename__ = "ticket_message"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default="false",
    )

    # ── Relationships ────────────────────────────────────────────────────
    ticket: Mapped["Ticket"] = relationship(
        "Ticket",
        back_populates="messages",
    )
    sender: Mapped["User"] = relationship(
        "User",
        back_populates="sent_messages",
    )

    def __repr__(self) -> str:
        kind: str = "internal" if self.is_internal else "reply"
        return f"<TicketMessage id={self.id} ticket_id={self.ticket_id} type={kind}>"
