"""
ResolveAI — Action Proposal Schemas

Pydantic schemas for agentic tool proposals and HITL approval responses.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import ActionRiskLevel, ActionStatus


class ActionProposalOut(BaseModel):
    """Schema for action proposals."""

    id: int
    ticket_id: int
    tool_name: str
    parameters: dict[str, Any]
    estimated_cost: float
    status: ActionStatus
    risk_level: ActionRiskLevel
    result: Optional[dict[str, Any]] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = ConfigDict(from_attributes=True)


class ActionApprovalResponse(BaseModel):
    """Schema returned upon approving or rejecting an action."""

    proposal: ActionProposalOut
    execution_result: Optional[dict[str, Any]] = None
    confirmation_message: str
