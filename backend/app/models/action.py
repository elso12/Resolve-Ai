"""
ResolveAI — Action Proposal ORM Model

Represents a pending or executed tool invocation proposed by the AI
Agentic decision service, subject to Human-In-The-Loop (HITL) approval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
import datetime

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    String,
    func,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ActionRiskLevel, ActionStatus

if TYPE_CHECKING:
    from app.models.ticket import Ticket


class ActionProposal(Base):
    """
    Action Proposal record for agentic tool execution with HITL safety.
    """

    __tablename__ = "action_proposal"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)

    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    estimated_cost: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    status: Mapped[ActionStatus] = mapped_column(
        SAEnum(ActionStatus, name="action_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        index=True,
        default=ActionStatus.PENDING_APPROVAL,
        server_default=ActionStatus.PENDING_APPROVAL.value,
    )

    risk_level: Mapped[ActionRiskLevel] = mapped_column(
        SAEnum(ActionRiskLevel, name="action_risk_level", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ActionRiskLevel.HIGH,
        server_default=ActionRiskLevel.HIGH.value,
    )

    result: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
        nullable=False,
    )

    # Relationship to parent Ticket
    ticket: Mapped[Ticket] = relationship("Ticket", back_populates="actions")

    def __repr__(self) -> str:
        return (
            f"<ActionProposal(id={self.id}, tool={self.tool_name!r}, "
            f"status={self.status.value!r}, risk={self.risk_level.value!r})>"
        )
