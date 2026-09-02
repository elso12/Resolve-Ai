"""
ResolveAI — Domain Enumerations

Canonical enum types shared across models, services, and API schemas.
Backed by native PostgreSQL ENUM types via SQLAlchemy for type safety
at the database level.
"""

from __future__ import annotations

import enum


class UserRole(str, enum.Enum):
    """Roles governing RBAC permissions across the platform."""

    CUSTOMER = "customer"
    AGENT = "agent"
    MANAGER = "manager"
    ADMIN = "admin"


class TicketStatus(str, enum.Enum):
    """
    Ticket lifecycle states.

    Transitions are enforced by the state machine in
    ``app.services.ticket_service``.  See ``ALLOWED_TRANSITIONS`` for
    the complete adjacency map.
    """

    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_CUSTOMER = "waiting_for_customer"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(str, enum.Enum):
    """SLA-driven priority tiers."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TicketCategory(str, enum.Enum):
    """Top-level ticket classification buckets."""

    BILLING = "billing"
    TECHNICAL = "technical"
    ACCOUNT = "account"
    GENERAL = "general"
