"""
ResolveAI — SLA Tracking & Breach Service

Calculates SLA deadlines, records response/resolution milestones, and evaluates breaches.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from app.models.enums import TicketPriority, TicketStatus
from app.models.sla import get_sla_policy

if TYPE_CHECKING:
    from app.models.ticket import Ticket


def calculate_sla_due_dates(
    priority: TicketPriority,
    created_at: datetime.datetime | None = None,
) -> tuple[datetime.datetime, datetime.datetime]:
    """
    Computes (first_response_due_at, resolution_due_at) in UTC for a ticket.
    """
    base_time = created_at or datetime.datetime.now(datetime.timezone.utc)
    if base_time.tzinfo is None:
        base_time = base_time.replace(tzinfo=datetime.timezone.utc)

    policy = get_sla_policy(priority)
    first_response_due = base_time + policy.first_response_delta
    resolution_due = base_time + policy.resolution_delta

    return first_response_due, resolution_due


def record_first_response(
    ticket: Ticket,
    responded_at: datetime.datetime | None = None,
) -> bool:
    """
    Records the first agent response timestamp and checks if it breached the SLA.
    Returns True if this was the first response recorded.
    """
    if ticket.first_responded_at is not None:
        return False  # Already responded previously

    now = responded_at or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    ticket.first_responded_at = now

    if ticket.first_response_due_at is not None:
        due = ticket.first_response_due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        if now > due:
            ticket.sla_first_response_breached = True

    return True


def record_resolution(
    ticket: Ticket,
    resolved_at: datetime.datetime | None = None,
) -> None:
    """
    Records resolution timestamp and determines if the resolution SLA was breached.
    """
    now = resolved_at or datetime.datetime.now(datetime.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=datetime.timezone.utc)

    ticket.resolved_at = now

    if ticket.resolution_due_at is not None:
        due = ticket.resolution_due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        if now > due:
            ticket.sla_resolution_breached = True


def evaluate_active_ticket_sla(ticket: Ticket) -> None:
    """
    Checks if an unresolved or un-responded ticket has currently exceeded its SLA deadlines.
    """
    now = datetime.datetime.now(datetime.timezone.utc)

    # Check first response breach for un-responded tickets
    if ticket.first_responded_at is None and ticket.first_response_due_at is not None:
        due = ticket.first_response_due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        if now > due:
            ticket.sla_first_response_breached = True

    # Check resolution breach for open tickets
    if ticket.status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED) and ticket.resolution_due_at is not None:
        due = ticket.resolution_due_at
        if due.tzinfo is None:
            due = due.replace(tzinfo=datetime.timezone.utc)
        if now > due:
            ticket.sla_resolution_breached = True
