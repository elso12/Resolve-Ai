"""
ResolveAI — AI Observability & Performance Telemetry Endpoints

Provides metrics on AI spend (USD), token consumption, latency benchmarks,
and Copilot acceptance / edit rates.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.ai_telemetry import AIInteraction
from app.models.enums import UserRole
from app.models.user import User
from app.services.ai_telemetry_service import record_ai_feedback

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics/ai", tags=["AI Observability & Telemetry"])


class AIFeedbackPayload(BaseModel):
    feedback: str = Field(
        ...,
        description="Agent evaluation action: ACCEPTED, EDITED, THUMBS_UP, THUMBS_DOWN",
    )


class AIInteractionOut(BaseModel):
    id: int
    ticket_id: int | None
    interaction_type: str
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float
    latency_ms: float
    user_feedback: str | None
    created_at: str

    model_config = {"from_attributes": True}


class AIObservabilitySummary(BaseModel):
    total_cost_usd: float
    avg_latency_ms: float
    total_tokens: int
    total_interactions: int
    copilot_acceptance_rate: float
    breakdown_by_type: dict[str, dict[str, Any]]
    recent_interactions: list[dict[str, Any]]


@router.get("", response_model=AIObservabilitySummary)
async def get_ai_observability_metrics(
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """
    Returns enterprise AI spend, token consumption, latency, and Copilot acceptance evaluations.
    """
    org_id = current_user.organization_id

    # 1. Aggregates for organization
    stmt = (
        select(
            func.count(AIInteraction.id).label("total_count"),
            func.coalesce(func.sum(AIInteraction.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AIInteraction.estimated_cost_usd), 0.0).label("total_cost"),
            func.coalesce(func.avg(AIInteraction.latency_ms), 0.0).label("avg_latency"),
        )
        .where(AIInteraction.organization_id == org_id)
    )
    result = await db.execute(stmt)
    total_count, total_tokens, total_cost, avg_latency = result.one()

    # 2. Copilot acceptance rate calculation
    suggest_stmt = select(AIInteraction).where(
        AIInteraction.organization_id == org_id,
        AIInteraction.interaction_type == "SUGGESTED_REPLY",
        AIInteraction.user_feedback.is_not(None),
    )
    suggest_res = await db.execute(suggest_stmt)
    feedback_interactions = list(suggest_res.scalars().all())

    accepted_count = sum(1 for i in feedback_interactions if i.user_feedback == "ACCEPTED")
    total_feedback = len(feedback_interactions)
    acceptance_rate = (accepted_count / total_feedback * 100.0) if total_feedback > 0 else 100.0

    # 3. Breakdown by interaction type
    type_stmt = (
        select(
            AIInteraction.interaction_type,
            func.count(AIInteraction.id),
            func.sum(AIInteraction.total_tokens),
            func.sum(AIInteraction.estimated_cost_usd),
            func.avg(AIInteraction.latency_ms),
        )
        .where(AIInteraction.organization_id == org_id)
        .group_by(AIInteraction.interaction_type)
    )
    type_res = await db.execute(type_stmt)
    breakdown: dict[str, dict[str, Any]] = {}
    for itype, count, tokens, cost, latency in type_res.all():
        breakdown[itype] = {
            "count": count,
            "total_tokens": tokens or 0,
            "total_cost_usd": round(float(cost or 0.0), 6),
            "avg_latency_ms": round(float(latency or 0.0), 1),
        }

    # 4. Recent interactions
    recent_stmt = (
        select(AIInteraction)
        .where(AIInteraction.organization_id == org_id)
        .order_by(desc(AIInteraction.created_at))
        .limit(limit)
    )
    recent_res = await db.execute(recent_stmt)
    recent = [
        {
            "id": i.id,
            "ticket_id": i.ticket_id,
            "interaction_type": i.interaction_type,
            "model_name": i.model_name,
            "total_tokens": i.total_tokens,
            "estimated_cost_usd": round(i.estimated_cost_usd, 6),
            "latency_ms": round(i.latency_ms, 1),
            "user_feedback": i.user_feedback,
            "created_at": i.created_at.isoformat() if i.created_at else None,
        }
        for i in recent_res.scalars().all()
    ]

    return {
        "total_cost_usd": round(float(total_cost), 6),
        "avg_latency_ms": round(float(avg_latency), 1),
        "total_tokens": int(total_tokens),
        "total_interactions": int(total_count),
        "copilot_acceptance_rate": round(acceptance_rate, 1),
        "breakdown_by_type": breakdown,
        "recent_interactions": recent,
    }


@router.post("/interactions/{interaction_id}/feedback")
async def submit_ai_feedback(
    interaction_id: int,
    payload: AIFeedbackPayload,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Records agent feedback (ACCEPTED, EDITED, THUMBS_UP, THUMBS_DOWN) for an AI output.
    """
    success = await record_ai_feedback(
        interaction_id=interaction_id,
        feedback=payload.feedback,
        organization_id=current_user.organization_id,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI interaction not found",
        )

    return {"status": "recorded", "interaction_id": interaction_id, "feedback": payload.feedback.upper()}
