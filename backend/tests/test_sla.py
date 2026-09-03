"""
ResolveAI — SLA Policy & Breach Calculation Test Suite
"""

import datetime
from app.models.enums import TicketPriority
from app.models.sla import get_sla_policy
from app.models.ticket import Ticket
from app.services.sla_service import (
    calculate_sla_due_dates,
    record_first_response,
    record_resolution,
)


def test_sla_policy_tier_targets():
    """Verify SLA policy targets match specifications across all priority tiers."""
    crit = get_sla_policy(TicketPriority.CRITICAL)
    assert crit.first_response_max_minutes == 30
    assert crit.resolution_max_hours == 4

    high = get_sla_policy(TicketPriority.HIGH)
    assert high.first_response_max_minutes == 120  # 2 hours
    assert high.resolution_max_hours == 8

    med = get_sla_policy(TicketPriority.MEDIUM)
    assert med.first_response_max_minutes == 480  # 8 hours
    assert med.resolution_max_hours == 24

    low = get_sla_policy(TicketPriority.LOW)
    assert low.first_response_max_minutes == 1440  # 24 hours
    assert low.resolution_max_hours == 72


def test_calculate_sla_due_dates():
    """Verify calculated due dates align with base time."""
    base = datetime.datetime(2026, 9, 1, 12, 0, 0, tzinfo=datetime.timezone.utc)
    first_due, res_due = calculate_sla_due_dates(TicketPriority.CRITICAL, created_at=base)

    assert first_due == base + datetime.timedelta(minutes=30)
    assert res_due == base + datetime.timedelta(hours=4)


def test_record_first_response_on_time_and_breach():
    """Verify first response milestone flags breach correctly when overdue."""
    base = datetime.datetime(2026, 9, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    first_due = base + datetime.timedelta(minutes=30)

    # 1. On time response
    t_on_time = Ticket(
        ticket_number="RSV-TEST-1",
        subject="Test",
        description="Test",
        priority=TicketPriority.CRITICAL,
        first_response_due_at=first_due,
        organization_id=1,
        customer_id=1,
        sla_first_response_breached=False,
        sla_resolution_breached=False,
    )
    record_first_response(t_on_time, responded_at=base + datetime.timedelta(minutes=15))
    assert t_on_time.first_responded_at is not None
    assert t_on_time.sla_first_response_breached is False

    # 2. Breached response
    t_breached = Ticket(
        ticket_number="RSV-TEST-2",
        subject="Test",
        description="Test",
        priority=TicketPriority.CRITICAL,
        first_response_due_at=first_due,
        organization_id=1,
        customer_id=1,
        sla_first_response_breached=False,
        sla_resolution_breached=False,
    )
    record_first_response(t_breached, responded_at=base + datetime.timedelta(minutes=45))
    assert t_breached.sla_first_response_breached is True


def test_record_resolution_breach():
    """Verify resolution SLA breach detection."""
    base = datetime.datetime(2026, 9, 1, 10, 0, 0, tzinfo=datetime.timezone.utc)
    res_due = base + datetime.timedelta(hours=4)

    ticket = Ticket(
        ticket_number="RSV-TEST-3",
        subject="Test",
        description="Test",
        priority=TicketPriority.CRITICAL,
        resolution_due_at=res_due,
        organization_id=1,
        customer_id=1,
        sla_first_response_breached=False,
        sla_resolution_breached=False,
    )
    # Resolved after 5 hours -> Breached
    record_resolution(ticket, resolved_at=base + datetime.timedelta(hours=5))
    assert ticket.resolved_at is not None
    assert ticket.sla_resolution_breached is True
