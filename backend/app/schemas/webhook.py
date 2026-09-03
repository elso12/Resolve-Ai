"""
ResolveAI — Webhook Schemas

Pydantic schemas for WebhookSubscription registration, inspection, and delivery testing.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class WebhookCreate(BaseModel):
    """Payload to register a new webhook endpoint."""

    target_url: str = Field(..., max_length=1024, description="Destination HTTP/HTTPS webhook URL.")
    events: list[str] = Field(
        default_factory=lambda: ["TICKET_CREATED", "SLA_BREACHED", "ACTION_APPROVED"],
        description="List of event topics to subscribe to.",
    )
    secret_key: str | None = Field(
        default=None,
        max_length=255,
        description="Optional shared secret for HMAC-SHA256 signature computation. Auto-generated if omitted.",
    )
    is_active: bool = Field(default=True, description="Whether the webhook subscription is immediately active.")


class WebhookUpdate(BaseModel):
    """Payload to update an existing webhook subscription."""

    target_url: str | None = Field(default=None, max_length=1024)
    events: list[str] | None = None
    secret_key: str | None = Field(default=None, max_length=255)
    is_active: bool | None = None


class WebhookOut(BaseModel):
    """Full webhook subscription response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    organization_id: int
    target_url: str
    secret_key: str
    events: list[str]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime


class WebhookTestResponse(BaseModel):
    """Result of dispatching a test ping webhook event."""

    delivered: bool
    status_code: int | None = None
    attempts: int
    error: str | None = None
    timestamp: str
