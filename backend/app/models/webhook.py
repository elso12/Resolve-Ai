"""
ResolveAI — Webhook Subscription Model

Stores external outbound webhook integrations (e.g. Slack, PagerDuty, custom CRMs)
with HMAC SHA-256 secret keys and subscribed event filters.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization


class WebhookSubscription(Base, TimestampMixin):
    """
    Stores webhook subscription registrations per organization.
    """

    __tablename__ = "webhook_subscription"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    target_url: Mapped[str] = mapped_column(String(1024), nullable=False)

    secret_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Subscribed event types, e.g. ["TICKET_CREATED", "SLA_BREACHED", "ACTION_APPROVED"]
    events: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )

    # Relationship
    organization: Mapped[Organization] = relationship("Organization", lazy="raise")
