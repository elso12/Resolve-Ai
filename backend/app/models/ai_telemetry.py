"""
ResolveAI — AI Interaction & Telemetry Model

Tracks token usage, execution latency, USD cost, and human-in-the-loop
evaluations across all AI operations (Triage, Summary, Copilot, RAG).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.ticket import Ticket


class AIInteraction(Base, TimestampMixin):
    """
    Records telemetry and cost metrics for a single LLM operation.
    """

    __tablename__ = "ai_interaction"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Scoping
    ticket_id: Mapped[int | None] = mapped_column(
        ForeignKey("ticket.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_id: Mapped[int] = mapped_column(
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Classification & Model
    interaction_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="gpt-3.5-turbo",
    )

    # Metrics
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Agent Evaluation / Feedback
    user_feedback: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
    )

    # Relationships
    organization: Mapped[Organization] = relationship("Organization", lazy="select")
    ticket: Mapped[Ticket | None] = relationship("Ticket", lazy="select")

    def __repr__(self) -> str:
        return (
            f"<AIInteraction id={self.id} type={self.interaction_type!r} "
            f"model={self.model_name!r} tokens={self.total_tokens} "
            f"cost=${self.estimated_cost_usd:.6f} latency={self.latency_ms:.1f}ms>"
        )
