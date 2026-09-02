"""
ResolveAI — Ticket Domain Service

Contains the formal finite state machine governing ticket lifecycle
transitions, ticket number generation, and core ticket business logic.
"""

from __future__ import annotations

import datetime
import hashlib
import secrets
from typing import Final

from fastapi import HTTPException, status

from app.core.logging import get_logger
from app.models.enums import TicketStatus

logger = get_logger(__name__)


# ── Finite State Machine ─────────────────────────────────────────────────────
#
# Adjacency map encoding every legal status transition.  The state
# machine is intentionally kept as pure data so it can be unit-tested,
# serialised for documentation, and enforced without touching the
# database.
#
#  ┌──────────┐     ┌──────────┐     ┌──────────────┐
#  │   OPEN   │────▶│ ASSIGNED │────▶│ IN_PROGRESS  │
#  └──────────┘     └──────────┘     └──────────────┘
#       │                │  │              │  │
#       │                │  │              │  ▼
#       │                │  │         ┌────────────────────┐
#       │                │  └────────▶│ WAITING_FOR_CUST.  │
#       │                │            └────────────────────┘
#       │                │  ┌──────────────┘  │
#       │                ▼  ▼                 │
#       │           ┌──────────┐              │
#       │           │ RESOLVED │◀─────────────┘
#       │           └──────────┘
#       │                │
#       ▼                ▼
#  ┌──────────────────────────┐
#  │         CLOSED           │  ◀── terminal (no exits)
#  └──────────────────────────┘
#

ALLOWED_TRANSITIONS: Final[dict[TicketStatus, set[TicketStatus]]] = {
    TicketStatus.OPEN: {
        TicketStatus.ASSIGNED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.CLOSED,
    },
    TicketStatus.ASSIGNED: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.IN_PROGRESS: {
        TicketStatus.WAITING_FOR_CUSTOMER,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.WAITING_FOR_CUSTOMER: {
        TicketStatus.IN_PROGRESS,
        TicketStatus.RESOLVED,
        TicketStatus.CLOSED,
    },
    TicketStatus.RESOLVED: {
        TicketStatus.CLOSED,
        TicketStatus.IN_PROGRESS,  # reopening path
    },
    TicketStatus.CLOSED: set(),  # terminal state — no exits
}

# Human-readable labels for error messages
_STATUS_LABEL: Final[dict[TicketStatus, str]] = {
    TicketStatus.OPEN: "Open",
    TicketStatus.ASSIGNED: "Assigned",
    TicketStatus.IN_PROGRESS: "In Progress",
    TicketStatus.WAITING_FOR_CUSTOMER: "Waiting for Customer",
    TicketStatus.RESOLVED: "Resolved",
    TicketStatus.CLOSED: "Closed",
}


def validate_transition(
    current_status: TicketStatus,
    new_status: TicketStatus,
) -> None:
    """
    Assert that moving from *current_status* → *new_status* is legal.

    Raises:
        HTTPException(400):  If the transition is not in
            ``ALLOWED_TRANSITIONS``.

    The error payload includes the current state, the rejected target
    state, and the list of states that *are* reachable — making it
    straightforward for frontend consumers to render contextual UI.
    """
    if current_status == new_status:
        return  # no-op transition is always allowed

    allowed: set[TicketStatus] = ALLOWED_TRANSITIONS.get(current_status, set())

    if new_status not in allowed:
        current_label: str = _STATUS_LABEL.get(current_status, current_status.value)
        target_label: str = _STATUS_LABEL.get(new_status, new_status.value)
        allowed_labels: list[str] = sorted(
            _STATUS_LABEL.get(s, s.value) for s in allowed
        )

        if not allowed_labels:
            detail = (
                f"Ticket is in terminal state '{current_label}' and cannot "
                f"be transitioned to any other state."
            )
        else:
            detail = (
                f"Invalid status transition: '{current_label}' -> '{target_label}'. "
                f"Allowed transitions from '{current_label}': "
                f"{', '.join(allowed_labels)}."
            )

        logger.warning(
            "invalid_ticket_transition",
            current=current_status.value,
            target=new_status.value,
            allowed=[s.value for s in allowed],
        )

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
        )


# ── Ticket Number Generation ────────────────────────────────────────────────
#
# Format:  RSV-{YEAR}-{HASH}
#   • RSV    — project prefix
#   • YEAR   — 4-digit year for chronological bucketing
#   • HASH   — 8-char uppercase hex from SHA-256 of 32 random bytes
#
# Collision probability at 8 hex chars (32 bits):
#   ~0.01 % at 10 000 tickets/year (birthday paradox: n²/2H).
#   The UNIQUE constraint on ``ticket_number`` acts as a safety net.

_TICKET_PREFIX: Final[str] = "RSV"
_HASH_LENGTH: Final[int] = 8  # characters of hex digest to use


def generate_ticket_number() -> str:
    """
    Generate a cryptographically collision-resistant ticket identifier.

    Returns:
        A string like ``RSV-2026-A3F7B1C9``.
    """
    year: int = datetime.datetime.now(datetime.timezone.utc).year
    entropy: bytes = secrets.token_bytes(32)
    digest: str = hashlib.sha256(entropy).hexdigest()[:_HASH_LENGTH].upper()
    return f"{_TICKET_PREFIX}-{year}-{digest}"
