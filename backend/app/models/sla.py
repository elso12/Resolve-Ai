"""
ResolveAI — SLA Policy Models & Constants

Defines Service Level Agreement targets by ticket priority tier.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Final

from app.models.enums import TicketPriority


@dataclass(frozen=True)
class SLAPolicy:
    """SLA threshold targets for first response and resolution."""
    first_response_max_minutes: int
    resolution_max_hours: int

    @property
    def first_response_delta(self) -> datetime.timedelta:
        return datetime.timedelta(minutes=self.first_response_max_minutes)

    @property
    def resolution_delta(self) -> datetime.timedelta:
        return datetime.timedelta(hours=self.resolution_max_hours)


# SLA Target Definitions per specifications:
# CRITICAL: First response <= 30 mins | Resolution <= 4 hours
# HIGH:     First response <= 2 hours  | Resolution <= 8 hours
# MEDIUM:   First response <= 8 hours  | Resolution <= 24 hours
# LOW:      First response <= 24 hours | Resolution <= 72 hours
SLA_POLICIES: Final[dict[TicketPriority, SLAPolicy]] = {
    TicketPriority.CRITICAL: SLAPolicy(first_response_max_minutes=30, resolution_max_hours=4),
    TicketPriority.HIGH: SLAPolicy(first_response_max_minutes=120, resolution_max_hours=8),
    TicketPriority.MEDIUM: SLAPolicy(first_response_max_minutes=480, resolution_max_hours=24),
    TicketPriority.LOW: SLAPolicy(first_response_max_minutes=1440, resolution_max_hours=72),
}


def get_sla_policy(priority: TicketPriority) -> SLAPolicy:
    """Retrieve SLA policy for given priority, falling back to MEDIUM."""
    return SLA_POLICIES.get(priority, SLA_POLICIES[TicketPriority.MEDIUM])
