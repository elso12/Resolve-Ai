"""
ResolveAI — Ticket Schemas

Pydantic models for ticket and message data transfer.
"""

from __future__ import annotations

import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.schemas.auth import UserOut


# ── Messages ─────────────────────────────────────────────────────────────────

class MessageCreate(BaseModel):
    """Payload for adding a message to a ticket thread."""
    body: str = Field(..., min_length=1, max_length=10000, description="Message content")
    is_internal: bool = Field(default=False, description="Whether this is an internal note (Agent/Manager/Admin only)")


class MessageOut(BaseModel):
    """Schema for returning message data."""
    id: int
    ticket_id: int
    sender_id: int
    body: str
    is_internal: bool
    created_at: datetime.datetime
    
    # Optionally include sender details for frontend convenience
    sender: Optional[UserOut] = None

    model_config = ConfigDict(from_attributes=True)


# ── Tickets ──────────────────────────────────────────────────────────────────

class TicketCreate(BaseModel):
    """Payload for opening a new ticket (typically by a Customer)."""
    subject: str = Field(..., min_length=5, max_length=500, description="Ticket subject line")
    description: str = Field(..., min_length=10, max_length=10000, description="Detailed description")
    priority: TicketPriority = Field(default=TicketPriority.MEDIUM, description="Initial priority")
    category: TicketCategory = Field(default=TicketCategory.GENERAL, description="Ticket category")


class TicketStatusUpdate(BaseModel):
    """Payload for changing ticket status."""
    status: TicketStatus = Field(..., description="New status, validated by FSM")


class TicketAssign(BaseModel):
    """Payload for assigning a ticket to an agent."""
    agent_id: int = Field(..., description="ID of the user to assign")


class TicketOut(BaseModel):
    """Schema for returning core ticket data."""
    id: int
    ticket_number: str
    subject: str
    description: str
    status: TicketStatus
    priority: TicketPriority
    category: TicketCategory
    customer_id: int
    assigned_agent_id: Optional[int] = None
    organization_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    # SLA Tracking
    first_response_due_at: Optional[datetime.datetime] = None
    resolution_due_at: Optional[datetime.datetime] = None
    first_responded_at: Optional[datetime.datetime] = None
    resolved_at: Optional[datetime.datetime] = None
    sla_first_response_breached: bool = False
    sla_resolution_breached: bool = False
    sla_breached: bool = False

    model_config = ConfigDict(from_attributes=True)


class TicketDetailOut(TicketOut):
    """Extended ticket schema that includes the full message thread."""
    messages: list[MessageOut] = Field(default_factory=list)
