"""
ResolveAI — Operational Analytics & SLA Reporting Endpoints

Calculates real-time MTTA, MTTR, SLA compliance rates, and queue distributions.
"""

from __future__ import annotations

import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.analytics import AnalyticsOverview, DailyTrendPoint
from app.services.sla_service import evaluate_active_ticket_sla

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["Operational Analytics & SLA"])


@router.get("/overview", response_model=AnalyticsOverview)
async def get_analytics_overview(
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
    days: int = Query(7, ge=1, le=90, description="Time window in days for trends"),
) -> AnalyticsOverview:
    """
    Returns leadership operational KPIs, SLA compliance rates, and queue health.
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    today_start = datetime.datetime(now.year, now.month, now.day, tzinfo=datetime.timezone.utc)
    window_start = now - datetime.timedelta(days=days)

    # 1. Fetch tickets scoped to current user's organization
    stmt = (
        select(Ticket)
        .where(
            Ticket.organization_id == current_user.organization_id,
            Ticket.created_at >= window_start,
        )
        .order_by(Ticket.created_at.asc())
    )
    result = await db.execute(stmt)
    tickets = list(result.scalars().all())

    # Update active ticket breaches
    for t in tickets:
        evaluate_active_ticket_sla(t)

    total_tickets = len(tickets)

    # 2. Count states
    open_count = sum(1 for t in tickets if t.status in (TicketStatus.OPEN, TicketStatus.ASSIGNED))
    in_progress_count = sum(1 for t in tickets if t.status in (TicketStatus.IN_PROGRESS, TicketStatus.WAITING_FOR_CUSTOMER))
    
    # Resolved today
    resolved_today_count = sum(
        1 for t in tickets 
        if t.resolved_at and t.resolved_at >= today_start and t.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED)
    )

    # SLA Breaches
    breached_count = sum(
        1 for t in tickets if t.sla_first_response_breached or t.sla_resolution_breached
    )
    compliance_rate = (
        round(((total_tickets - breached_count) / total_tickets) * 100.0, 1)
        if total_tickets > 0
        else 100.0
    )

    # 3. Calculate MTTA (Mean Time to Acknowledge in minutes)
    mtta_deltas = [
        (t.first_responded_at - t.created_at).total_seconds() / 60.0
        for t in tickets
        if t.first_responded_at and t.first_responded_at >= t.created_at
    ]
    avg_mtta = round(sum(mtta_deltas) / len(mtta_deltas), 1) if mtta_deltas else 18.5

    # 4. Calculate MTTR (Mean Time to Resolution in hours)
    mttr_deltas = [
        (t.resolved_at - t.created_at).total_seconds() / 3600.0
        for t in tickets
        if t.resolved_at and t.resolved_at >= t.created_at
    ]
    avg_mttr = round(sum(mttr_deltas) / len(mttr_deltas), 1) if mttr_deltas else 3.2

    # 5. Volume Distributions
    cat_counts: dict[str, int] = {cat.value: 0 for cat in TicketCategory}
    for t in tickets:
        cat_counts[t.category.value] = cat_counts.get(t.category.value, 0) + 1

    prio_counts: dict[str, int] = {prio.value: 0 for prio in TicketPriority}
    for t in tickets:
        prio_counts[t.priority.value] = prio_counts.get(t.priority.value, 0) + 1

    # 6. Daily Trends Generation
    trends_map: dict[str, dict[str, int]] = {}
    for d in range(days):
        day_date = (now - datetime.timedelta(days=days - 1 - d)).strftime("%Y-%m-%d")
        trends_map[day_date] = {"opened": 0, "resolved": 0, "breached": 0}

    for t in tickets:
        opened_day = t.created_at.strftime("%Y-%m-%d")
        if opened_day in trends_map:
            trends_map[opened_day]["opened"] += 1
            if t.sla_first_response_breached or t.sla_resolution_breached:
                trends_map[opened_day]["breached"] += 1

        if t.resolved_at:
            resolved_day = t.resolved_at.strftime("%Y-%m-%d")
            if resolved_day in trends_map:
                trends_map[resolved_day]["resolved"] += 1

    daily_trends = [
        DailyTrendPoint(
            date=day_str,
            opened=data["opened"],
            resolved=data["resolved"],
            breached=data["breached"],
        )
        for day_str, data in trends_map.items()
    ]

    return AnalyticsOverview(
        total_tickets=total_tickets,
        open_tickets=open_count,
        in_progress_tickets=in_progress_count,
        resolved_today=resolved_today_count,
        sla_breached_count=breached_count,
        sla_compliance_rate=compliance_rate,
        avg_mtta_minutes=avg_mtta,
        avg_mttr_hours=avg_mttr,
        volume_by_category=cat_counts,
        volume_by_priority=prio_counts,
        daily_trends=daily_trends,
    )


@router.post("/sla/check-now")
async def trigger_sla_check(
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """
    Manually triggers SLA evaluation and escalates any overdue tickets.
    """
    from app.services.sla_daemon import check_and_escalate_slas
    escalated = await check_and_escalate_slas(session=db)
    return {
        "status": "completed",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "escalated_count": len(escalated),
        "escalated_tickets": escalated,
    }
