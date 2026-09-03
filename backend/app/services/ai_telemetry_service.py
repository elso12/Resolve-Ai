"""
ResolveAI — Enterprise AI Observability & Telemetry Service

Provides:
- Token usage tracking & latency benchmarking
- USD cost calculations based on live model pricing
- Evaluation feedback recording (ACCEPTED, EDITED, THUMBS_UP, THUMBS_DOWN)
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.ai_telemetry import AIInteraction

logger = get_logger(__name__)

# Model pricing rates per 1,000,000 tokens (USD)
# (Prompt / Input Price, Completion / Output Price)
MODEL_PRICING_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "text-embedding-3-small": (0.02, 0.0),
    "claude-3-haiku": (0.25, 1.25),
    "mock-heuristic": (0.15, 0.60),
}


def calculate_cost_usd(model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Computes estimated cost in USD based on token counts."""
    rates = MODEL_PRICING_PER_1M.get(model_name, (0.15, 0.60))
    prompt_rate, completion_rate = rates
    cost = (prompt_tokens * (prompt_rate / 1_000_000.0)) + (completion_tokens * (completion_rate / 1_000_000.0))
    return round(cost, 6)


async def log_ai_interaction(
    organization_id: int,
    interaction_type: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    ticket_id: int | None = None,
    user_feedback: str | None = None,
    session: AsyncSession | None = None,
) -> AIInteraction:
    """
    Records an AI operation to the observability telemetry table.
    """
    total_tokens = prompt_tokens + completion_tokens
    cost_usd = calculate_cost_usd(model_name, prompt_tokens, completion_tokens)

    interaction = AIInteraction(
        organization_id=organization_id,
        ticket_id=ticket_id,
        interaction_type=interaction_type,
        model_name=model_name,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost_usd,
        latency_ms=round(latency_ms, 2),
        user_feedback=user_feedback,
    )

    if session is not None:
        session.add(interaction)
        await session.flush()
        await session.refresh(interaction)
        return interaction

    async with async_session_factory() as db:
        db.add(interaction)
        await db.commit()
        await db.refresh(interaction)

    logger.info(
        "ai_telemetry_logged",
        interaction_id=interaction.id,
        type=interaction_type,
        model=model_name,
        tokens=total_tokens,
        cost=f"${cost_usd:.6f}",
        latency=f"{latency_ms:.1f}ms",
    )

    return interaction


async def record_ai_feedback(
    interaction_id: int,
    feedback: str,
    organization_id: int | None = None,
) -> bool:
    """
    Updates the evaluation rating/action (ACCEPTED, EDITED, THUMBS_UP, THUMBS_DOWN)
    for a logged AI interaction.
    """
    clean_feedback = feedback.upper().strip()

    async with async_session_factory() as db:
        stmt = select(AIInteraction).where(AIInteraction.id == interaction_id)
        if organization_id is not None:
            stmt = stmt.where(AIInteraction.organization_id == organization_id)

        result = await db.execute(stmt)
        interaction = result.scalar_one_or_none()
        if not interaction:
            return False

        interaction.user_feedback = clean_feedback
        await db.commit()

        logger.info(
            "ai_feedback_recorded",
            interaction_id=interaction_id,
            feedback=clean_feedback,
        )
        return True
