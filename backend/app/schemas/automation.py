"""
ResolveAI — Automation Rule Schemas
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, Field


class AutomationRuleBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Descriptive rule name")
    is_active: bool = Field(default=True, description="Whether this rule is evaluated")
    event_trigger: str = Field(
        ...,
        description="Trigger event: TICKET_CREATED, TICKET_STATUS_CHANGED, SLA_BREACHED",
    )
    conditions: dict[str, Any] = Field(
        default_factory=dict,
        description="Matching criteria (category, priority, status, subject_contains, etc.)",
    )
    actions: dict[str, Any] = Field(
        default_factory=dict,
        description="Actions to execute (set_priority, set_status, assign_agent_id, add_internal_note)",
    )


class AutomationRuleCreate(AutomationRuleBase):
    pass


class AutomationRuleUpdate(BaseModel):
    name: str | None = None
    is_active: bool | None = None
    event_trigger: str | None = None
    conditions: dict[str, Any] | None = None
    actions: dict[str, Any] | None = None


class AutomationRuleOut(AutomationRuleBase):
    id: int
    organization_id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}
