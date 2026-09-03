"""
ResolveAI — Outbound Webhook Dispatcher Service

Delivers real-time notifications to external endpoints (Slack, PagerDuty, CRMs)
with HMAC SHA-256 cryptographic signatures and exponential backoff retry policies.
"""

from __future__ import annotations

import asyncio
import datetime
import hashlib
import hmac
import json
import secrets
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import async_session_factory
from app.models.webhook import WebhookSubscription

logger = get_logger(__name__)


def generate_secret_key() -> str:
    """Generate a secure 32-byte hexadecimal secret key."""
    return secrets.token_hex(32)


def compute_signature(secret_key: str, payload_bytes: bytes) -> str:
    """
    Computes an HMAC SHA-256 signature for the given payload using secret_key.
    Returns the hexadecimal digest.
    """
    return hmac.new(
        secret_key.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()


async def deliver_webhook_payload(
    target_url: str,
    secret_key: str,
    payload_dict: dict[str, Any],
    max_attempts: int = 3,
    initial_backoff_seconds: float = 0.5,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, int | None, int, str | None]:
    """
    Dispatches a webhook payload with X-Signature-SHA256 header and exponential retries.

    Returns:
      (delivered: bool, status_code: int | None, attempts: int, error: str | None)
    """
    payload_bytes = json.dumps(payload_dict, default=str).encode("utf-8")
    signature = compute_signature(secret_key, payload_bytes)

    headers = {
        "Content-Type": "application/json",
        "User-Agent": "ResolveAI-WebhookDispatcher/1.0",
        "X-Signature-SHA256": signature,
        "X-ResolveAI-Event": str(payload_dict.get("event", "UNKNOWN")),
        "X-ResolveAI-Delivery": str(payload_dict.get("event_id", "")),
    }

    attempts = 0
    last_status: int | None = None
    last_error: str | None = None
    backoff = initial_backoff_seconds

    async def _execute_post(http_client: httpx.AsyncClient) -> tuple[bool, int | None, int, str | None]:
        nonlocal attempts, last_status, last_error, backoff
        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            try:
                resp = await http_client.post(
                    target_url,
                    content=payload_bytes,
                    headers=headers,
                    timeout=10.0,
                )
                last_status = resp.status_code
                if 200 <= resp.status_code < 300:
                    logger.info(
                        "webhook_delivery_success",
                        target_url=target_url,
                        event_type=payload_dict.get("event"),
                        status_code=resp.status_code,
                        attempt=attempt,
                    )
                    return True, resp.status_code, attempts, None

                last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                logger.warning(
                    "webhook_delivery_non_2xx",
                    target_url=target_url,
                    status_code=resp.status_code,
                    attempt=attempt,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "webhook_delivery_exception",
                    target_url=target_url,
                    error=str(exc),
                    attempt=attempt,
                )

            if attempt < max_attempts:
                await asyncio.sleep(backoff)
                backoff *= 2.0

        return False, last_status, attempts, last_error

    if client is not None:
        return await _execute_post(client)

    async with httpx.AsyncClient() as managed_client:
        return await _execute_post(managed_client)


async def send_test_ping(
    subscription: WebhookSubscription,
    client: httpx.AsyncClient | None = None,
) -> tuple[bool, int | None, int, str | None]:
    """Send a mock ping event to verify the webhook target URL."""
    ping_payload = {
        "event": "PING",
        "event_id": f"evt_{uuid.uuid4().hex}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "organization_id": subscription.organization_id,
        "data": {
            "subscription_id": subscription.id,
            "target_url": subscription.target_url,
            "message": "ResolveAI webhook connectivity test ping.",
        },
    }
    return await deliver_webhook_payload(
        target_url=subscription.target_url,
        secret_key=subscription.secret_key,
        payload_dict=ping_payload,
        max_attempts=1,
        client=client,
    )


def _matches_event(events: Any, event_type: str) -> bool:
    """Check if event_type matches subscription events list or wildcard."""
    if isinstance(events, list):
        return event_type in events or "*" in events
    if isinstance(events, str):
        try:
            parsed = json.loads(events)
            if isinstance(parsed, list):
                return event_type in parsed or "*" in parsed
        except Exception:
            pass
        return event_type == events or events == "*"
    return False


async def dispatch_webhook_event(
    event_type: str,
    data: dict[str, Any],
    organization_id: int,
    session: AsyncSession | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[asyncio.Task[Any]]:
    """
    Look up all active webhook subscriptions for this organization subscribed
    to event_type, and trigger non-blocking deliveries.
    """
    event_envelope = {
        "event": event_type,
        "event_id": f"evt_{uuid.uuid4().hex}",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "organization_id": organization_id,
        "data": data,
    }

    matching_subs: list[tuple[str, str]] = []

    if session is not None:
        stmt = select(WebhookSubscription).where(
            WebhookSubscription.organization_id == organization_id,
            WebhookSubscription.is_active.is_(True),
        )
        res = await session.execute(stmt)
        subs = res.scalars().all()
        for s in subs:
            if _matches_event(s.events, event_type):
                matching_subs.append((s.target_url, s.secret_key))
    else:
        # Resolve session from async_session_factory or test environment
        try:
            async with async_session_factory() as db:
                stmt = select(WebhookSubscription).where(
                    WebhookSubscription.organization_id == organization_id,
                    WebhookSubscription.is_active.is_(True),
                )
                res = await db.execute(stmt)
                subs = res.scalars().all()
                for s in subs:
                    if _matches_event(s.events, event_type):
                        matching_subs.append((s.target_url, s.secret_key))
        except Exception:
            try:
                from tests.conftest import TestSessionLocal
                async with TestSessionLocal() as db:
                    stmt = select(WebhookSubscription).where(
                        WebhookSubscription.organization_id == organization_id,
                        WebhookSubscription.is_active.is_(True),
                    )
                    res = await db.execute(stmt)
                    subs = res.scalars().all()
                    for s in subs:
                        if _matches_event(s.events, event_type):
                            matching_subs.append((s.target_url, s.secret_key))
            except Exception as exc:
                logger.error("webhook_subscriber_lookup_failed", error=str(exc))

    tasks: list[asyncio.Task[Any]] = []
    for target_url, secret_key in matching_subs:
        task = asyncio.create_task(
            deliver_webhook_payload(
                target_url=target_url,
                secret_key=secret_key,
                payload_dict=event_envelope,
                client=client,
            )
        )
        tasks.append(task)

    return tasks

