"""
ResolveAI — Event-Condition-Action (ECA) Automation Rule Model

Allows managers to define automated workflow rules:
WHEN [Event] AND [Conditions] THEN [Actions].
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class AutomationRule(Base, TimestampMixin):
    """
    Stores ECA automation rules configured by support managers.
    """

    __tablename__ = "automation_rule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Rule Metadata
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true", nullable=False)

    # Event Trigger: TICKET_CREATED, TICKET_STATUS_CHANGED, SLA_BREACHED
    event_trigger: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    # JSON condition tree: e.g. {"category": "billing", "priority": "low", "keyword": "refund"}
    conditions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # JSON action list / dict: e.g. {"set_priority": "high", "assign_agent_id": 2, "add_internal_note": "..."}
    actions: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )

    # Tenant scoping
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    organization: Mapped[Organization] = relationship("Organization", lazy="select")

    def __repr__(self) -> str:
        return f"<AutomationRule id={self.id} name={self.name!r} trigger={self.event_trigger} active={self.is_active}>"
