"""
ResolveAI — SLA Monitoring & Escalation Daemon

Continuously monitors active tickets for first-response and resolution SLA deadline breaches.
Auto-flags breached tickets, appends internal audit notes, escalates priority to CRITICAL,
and broadcasts alerts to managers and agents via WebSockets.
"""

from __future__ import annotations

import asyncio
import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.websocket import ws_manager
from app.db.session import async_session_factory
from app.models.enums import TicketPriority, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage
from app.models.user import User
from app.core.metrics import record_sla_breach

logger = get_logger(__name__)


async def check_and_escalate_slas(
    session: AsyncSession | None = None,
) -> list[dict[str, Any]]:
    """
    Evaluates all open, assigned, and in-progress tickets for SLA breaches.

    For any breached ticket:
      1. Sets sla_breached = True (and specific milestone breach flags).
      2. Upgrades priority to CRITICAL.
      3. Appends an automated internal audit note.
      4. Broadcasts an alert over WebSockets to online managers and ticket viewers.

    Returns:
        List of escalated ticket summary dicts.
    """
    escalated_tickets: list[dict[str, Any]] = []
    now = datetime.datetime.now(datetime.timezone.utc)

    # Manage session context
    if session is not None:
        return await _evaluate_tickets(session, now, escalated_tickets)

    async with async_session_factory() as db:
        res = await _evaluate_tickets(db, now, escalated_tickets)
        await db.commit()
        return res


async def _evaluate_tickets(
    db: AsyncSession,
    now: datetime.datetime,
    escalated_tickets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Internal evaluation logic on an active database session."""
    stmt = (
        select(Ticket)
        .options(selectinload(Ticket.messages))
        .where(
            Ticket.status.in_([
                TicketStatus.OPEN,
                TicketStatus.ASSIGNED,
                TicketStatus.IN_PROGRESS,
            ])
        )
    )

    result = await db.execute(stmt)
    tickets = result.scalars().all()

    for ticket in tickets:
        reasons: list[str] = []
        is_breached = False

        # 1. Check First Response SLA Breach
        first_resp_due = ticket.first_response_due_at
        if first_resp_due is not None and ticket.first_responded_at is None:
            if first_resp_due.tzinfo is None:
                first_resp_due = first_resp_due.replace(tzinfo=datetime.timezone.utc)
            if now > first_resp_due and not ticket.sla_first_response_breached:
                ticket.sla_first_response_breached = True
                is_breached = True
                reasons.append("First response deadline passed.")
                record_sla_breach("first_response", ticket.priority.value)

        # 2. Check Resolution SLA Breach
        res_due = ticket.resolution_due_at
        if res_due is not None and ticket.resolved_at is None:
            if res_due.tzinfo is None:
                res_due = res_due.replace(tzinfo=datetime.timezone.utc)
            if now > res_due and not ticket.sla_resolution_breached:
                ticket.sla_resolution_breached = True
                is_breached = True
                reasons.append("Resolution deadline passed.")
                record_sla_breach("resolution", ticket.priority.value)

        # If already flagged as general breach but milestone is new, or newly breached
        if is_breached or (
            (ticket.sla_first_response_breached or ticket.sla_resolution_breached)
            and not ticket.sla_breached
        ):
            ticket.sla_breached = True
            previous_priority = ticket.priority
            ticket.priority = TicketPriority.CRITICAL

            reason_str = " ".join(reasons) if reasons else "SLA deadline passed."
            audit_body = f"⚠️ SLA BREACH: {reason_str}"

            # Identify a sender for the automated internal note
            sender_id = ticket.assigned_agent_id
            if sender_id is None:
                # Query an admin or manager within the organization
                user_stmt = select(User.id).where(
                    User.organization_id == ticket.organization_id,
                    User.role.in_([UserRole.MANAGER, UserRole.ADMIN, UserRole.AGENT]),
                ).limit(1)
                user_res = await db.execute(user_stmt)
                sender_id = user_res.scalar_one_or_none()

            # Fallback to customer user id if no agent found
            if sender_id is None:
                sender_id = ticket.customer_id

            # Add internal note
            note = TicketMessage(
                ticket_id=ticket.id,
                sender_id=sender_id,
                body=audit_body,
                is_internal=True,
            )
            db.add(note)
            await db.flush()

            # Evaluate dynamic ECA workflow automations for SLA_BREACHED
            try:
                from app.services.workflow_engine import evaluate_rules
                await evaluate_rules("SLA_BREACHED", ticket, db)
            except Exception as auto_err:
                logger.warning("automation_rule_evaluation_error", error=str(auto_err))

            # Broadcast WebSocket alerts
            alert_payload = {
                "ticket_id": str(ticket.id),
                "ticket_number": ticket.ticket_number,
                "subject": ticket.subject,
                "priority": ticket.priority.value,
                "previous_priority": previous_priority.value,
                "reason": reason_str,
                "timestamp": now.isoformat(),
            }

            try:
                # Broadcast to the specific ticket room
                await ws_manager.broadcast_to_ticket(
                    str(ticket.id),
                    event_type="SLA_BREACH_ALERT",
                    data=alert_payload,
                )
                # Broadcast to the organization room for all listening managers/agents
                await ws_manager.broadcast_to_org(
                    ticket.organization_id,
                    event_type="SLA_BREACH_ALERT",
                    data=alert_payload,
                )
            except Exception as ws_err:
                logger.warning("sla_websocket_broadcast_failed", error=str(ws_err))

            # Dispatch outbound webhook to external integrations
            try:
                from app.services.webhook_service import dispatch_webhook_event
                await dispatch_webhook_event(
                    event_type="SLA_BREACHED",
                    data={
                        "ticket_id": ticket.id,
                        "ticket_number": ticket.ticket_number,
                        "subject": ticket.subject,
                        "priority": ticket.priority.value,
                        "previous_priority": previous_priority.value,
                        "reason": reason_str,
                        "sla_first_response_breached": ticket.sla_first_response_breached,
                        "sla_resolution_breached": ticket.sla_resolution_breached,
                    },
                    organization_id=ticket.organization_id,
                    session=db,
                )
            except Exception as hook_err:
                logger.warning("webhook_dispatch_error", error=str(hook_err))

            logger.warning(
                "sla_breach_escalated",
                ticket_id=ticket.id,
                ticket_number=ticket.ticket_number,
                reason=reason_str,
                new_priority=ticket.priority.value,
            )

            escalated_tickets.append({
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "subject": ticket.subject,
                "priority": ticket.priority.value,
                "previous_priority": previous_priority.value,
                "reason": reason_str,
            })

    return escalated_tickets


async def periodic_sla_daemon(interval_seconds: int = 60) -> None:
    """
    Background worker loop that runs check_and_escalate_slas at a fixed interval.
    """
    logger.info("sla_daemon_started", interval=interval_seconds)
    while True:
        try:
            escalated = await check_and_escalate_slas()
            if escalated:
                logger.info("sla_daemon_escalated_batch", count=len(escalated))
        except asyncio.CancelledError:
            logger.info("sla_daemon_cancelled")
            break
        except Exception as exc:
            logger.error("sla_daemon_cycle_failed", error=str(exc))

        await asyncio.sleep(interval_seconds)
