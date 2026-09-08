from typing import Any
"""
ResolveAI — Outbound Webhooks Test Suite

Validates:
  • Webhook subscription CRUD operations and Manager/Admin RBAC enforcement
  • Cryptographic HMAC SHA-256 signature generation (X-Signature-SHA256)
  • End-to-end outbound event dispatching on ticket creation
  • Exponential backoff retry logic (3 attempts on failure)
  • Webhook connectivity test probe endpoint (POST /api/v1/webhooks/{id}/test)
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
from typing import Any
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import AsyncClient, MockTransport, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.webhook import WebhookSubscription
from app.services.webhook_service import (
    compute_signature,
    deliver_webhook_payload,
    generate_secret_key,
)


# ── 1. Unit Tests for Cryptographic Signatures ──────────────────────────────

def test_hmac_sha256_signature_calculation():
    """
    Assert that compute_signature produces the exact HMAC SHA-256 hex digest.
    """
    secret = "super-secret-webhook-key-12345"
    payload = {"event": "TICKET_CREATED", "data": {"ticket_id": 42}}
    payload_bytes = json.dumps(payload, default=str).encode("utf-8")

    expected_sig = hmac.new(
        secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    actual_sig = compute_signature(secret, payload_bytes)
    assert actual_sig == expected_sig
    assert len(actual_sig) == 64  # SHA-256 produces 64 hex characters


# ── 2. Webhook Delivery & Header Validation ──────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_delivery_attaches_signature_and_event_headers():
    """
    Assert that outbound delivery sets X-Signature-SHA256 and X-ResolveAI-Event headers.
    """
    captured_requests: list[httpx.Request] = []

    def mock_handler(request: httpx.Request) -> Response:
        captured_requests.append(request)
        return Response(200, json={"received": True})

    mock_transport = MockTransport(mock_handler)
    async with httpx.AsyncClient(transport=mock_transport) as mock_client:
        secret = "test-secret-key-999"
        payload = {
            "event": "TICKET_CREATED",
            "event_id": "evt_test123",
            "organization_id": 1,
            "data": {"subject": "Urgent outage"},
        }
        target_url = "https://hooks.slack.com/services/test"

        delivered, status_code, attempts, error = await deliver_webhook_payload(
            target_url=target_url,
            secret_key=secret,
            payload_dict=payload,
            client=mock_client,
        )

        assert delivered is True
        assert status_code == 200
        assert attempts == 1
        assert error is None
        assert len(captured_requests) == 1

        req = captured_requests[0]
        assert req.headers["Content-Type"] == "application/json"
        assert req.headers["X-ResolveAI-Event"] == "TICKET_CREATED"
        assert req.headers["X-ResolveAI-Delivery"] == "evt_test123"

        # Verify signature header matches exact HMAC over request body
        body_bytes = req.content
        expected_sig = hmac.new(secret.encode("utf-8"), body_bytes, hashlib.sha256).hexdigest()
        assert req.headers["X-Signature-SHA256"] == expected_sig


# ── 3. Exponential Backoff Retry Tests ───────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_delivery_retries_three_times_on_failure():
    """
    Assert that failing delivery retries up to 3 times before returning failure.
    """
    call_count = 0

    def fail_handler(request: httpx.Request) -> Response:
        nonlocal call_count
        call_count += 1
        return Response(500, text="Internal Server Error")

    mock_transport = MockTransport(fail_handler)
    async with httpx.AsyncClient(transport=mock_transport) as mock_client:
        delivered, status_code, attempts, error = await deliver_webhook_payload(
            target_url="https://api.crm.com/webhooks",
            secret_key="secret-key",
            payload_dict={"event": "SLA_BREACHED", "data": {}},
            max_attempts=3,
            initial_backoff_seconds=0.01,  # Fast backoff for test speed
            client=mock_client,
        )

        assert delivered is False
        assert status_code == 500
        assert attempts == 3
        assert call_count == 3
        assert "500" in (error or "")


# ── 4. Webhook Management API (CRUD & RBAC) ──────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_crud_and_rbac(
    manager_client: AsyncClient,
    customer_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Assert that:
      • Support Managers can register, view, and delete webhook subscriptions.
      • Customers receive HTTP 403 Forbidden.
    """
    create_payload = {
        "target_url": "https://events.pagerduty.com/v2/enqueue",
        "events": ["TICKET_CREATED", "SLA_BREACHED"],
        "secret_key": "custom-pagerduty-secret",
    }

    # 1. Customer cannot create a webhook
    forbidden_resp = await customer_client.post("/api/v1/webhooks", json=create_payload)
    assert forbidden_resp.status_code == 403

    # 2. Manager creates webhook
    create_resp = await manager_client.post("/api/v1/webhooks", json=create_payload)
    assert create_resp.status_code == 201
    created_data = create_resp.json()
    webhook_id = created_data["id"]
    assert created_data["target_url"] == create_payload["target_url"]
    assert created_data["secret_key"] == "custom-pagerduty-secret"
    assert created_data["events"] == ["TICKET_CREATED", "SLA_BREACHED"]
    assert created_data["is_active"] is True

    # 3. Manager lists webhooks
    list_resp = await manager_client.get("/api/v1/webhooks")
    assert list_resp.status_code == 200
    all_subs = list_resp.json()
    assert any(s["id"] == webhook_id for s in all_subs)

    # 4. Customer cannot list webhooks
    assert (await customer_client.get("/api/v1/webhooks")).status_code == 403

    # 5. Manager deletes webhook
    del_resp = await manager_client.delete(f"/api/v1/webhooks/{webhook_id}")
    assert del_resp.status_code == 204

    # 6. Verify deleted from DB
    stmt = select(WebhookSubscription).where(WebhookSubscription.id == webhook_id)
    res = await db_session.execute(stmt)
    assert res.scalar_one_or_none() is None


# ── 5. End-to-End Event Trigger on Ticket Creation ───────────────────────────

@pytest.mark.asyncio
async def test_ticket_creation_triggers_webhook_dispatch_e2e(
    manager_client: AsyncClient,
    customer_client: AsyncClient,
):
    """
    VERIFICATION TEST:
    Create a test webhook subscription, trigger a ticket creation event,
    and assert that the outbound payload is formatted with the proper
    cryptographic signature header (X-Signature-SHA256) and ticket data.
    """
    secret = "whsec_super_secret_crm_key_abcdef123456"
    target_url = "https://crm.external-system.com/webhook/tickets"

    # 1. Register a test webhook for TICKET_CREATED events
    sub_resp = await manager_client.post(
        "/api/v1/webhooks",
        json={
            "target_url": target_url,
            "events": ["TICKET_CREATED"],
            "secret_key": secret,
        },
    )
    assert sub_resp.status_code == 201
    created_sub = sub_resp.json()
    assert created_sub["target_url"] == target_url
    assert created_sub["secret_key"] == secret

    # 2. Intercept outbound HTTP POST from deliver_webhook_payload for external target_url
    captured_requests: list[dict[str, Any]] = []
    orig_post = httpx.AsyncClient.post

    async def selective_mock_post(self, url, *args, **kwargs):
        url_str = str(url)
        if "crm.external-system.com" in url_str:
            captured_requests.append({
                "url": url_str,
                "content": kwargs.get("content", b""),
                "headers": kwargs.get("headers", {}),
            })
            return Response(200, json={"received": True})
        return await orig_post(self, url, *args, **kwargs)

    with patch.object(httpx.AsyncClient, "post", new=selective_mock_post):
        ticket_payload = {
            "subject": "End-to-End Cryptographic Webhook Test",
            "description": "Validating outbound HMAC-SHA256 signature on real ticket submission.",
            "category": "technical",
            "priority": "high",
        }
        create_ticket_resp = await customer_client.post("/api/v1/tickets", json=ticket_payload)
        assert create_ticket_resp.status_code == 201
        created_ticket_data = create_ticket_resp.json()

        # Allow background dispatch tasks to complete
        await asyncio.sleep(0.2)


    # 3. Assert outbound delivery was captured
    assert len(captured_requests) >= 1, "Expected outbound webhook POST request to be dispatched"
    captured = captured_requests[0]

    # Verify target endpoint
    assert captured["url"] == target_url

    # Verify headers
    headers = captured["headers"]
    assert headers.get("Content-Type") == "application/json"
    assert headers.get("X-ResolveAI-Event") == "TICKET_CREATED"
    assert "X-ResolveAI-Delivery" in headers
    assert "X-Signature-SHA256" in headers

    # Verify payload contents
    payload_dict = json.loads(captured["content"].decode("utf-8"))
    assert payload_dict["event"] == "TICKET_CREATED"
    assert payload_dict["data"]["ticket_id"] == created_ticket_data["id"]
    assert payload_dict["data"]["subject"] == ticket_payload["subject"]
    assert payload_dict["data"]["priority"] == "high"

    # 4. Cryptographically assert that X-Signature-SHA256 matches HMAC-SHA256 of raw bytes
    raw_bytes = captured["content"]
    computed_hmac = hmac.new(secret.encode("utf-8"), raw_bytes, hashlib.sha256).hexdigest()
    assert headers["X-Signature-SHA256"] == computed_hmac
    assert len(headers["X-Signature-SHA256"]) == 64


# ── 6. Test Ping Endpoint & Get Webhook By ID ─────────────────────────────────

@pytest.mark.asyncio
async def test_get_webhook_by_id(
    manager_client: AsyncClient,
):
    """
    Assert that GET /api/v1/webhooks/{id} returns the specific webhook subscription.
    """
    sub_resp = await manager_client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://slack.com/api/test",
            "events": ["ACTION_APPROVED"],
        },
    )
    assert sub_resp.status_code == 201
    webhook_id = sub_resp.json()["id"]

    get_resp = await manager_client.get(f"/api/v1/webhooks/{webhook_id}")
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == webhook_id
    assert data["target_url"] == "https://slack.com/api/test"
    assert data["events"] == ["ACTION_APPROVED"]

    # 404 for non-existent webhook
    not_found = await manager_client.get("/api/v1/webhooks/999999")
    assert not_found.status_code == 404


@pytest.mark.asyncio
async def test_webhook_test_ping_endpoint(
    manager_client: AsyncClient,
):
    """
    Assert that POST /api/v1/webhooks/{id}/test executes a ping probe.
    """
    sub_resp = await manager_client.post(
        "/api/v1/webhooks",
        json={
            "target_url": "https://httpbin.org/post",
            "events": ["TICKET_CREATED"],
        },
    )
    assert sub_resp.status_code == 201
    webhook_id = sub_resp.json()["id"]

    with patch(
        "app.api.webhooks.send_test_ping",
        return_value=(True, 200, 1, None),
    ) as mock_ping:
        test_resp = await manager_client.post(f"/api/v1/webhooks/{webhook_id}/test")
        assert test_resp.status_code == 200
        data = test_resp.json()
        assert data["delivered"] is True
        assert data["status_code"] == 200
        assert data["attempts"] == 1
        assert "timestamp" in data
        mock_ping.assert_called_once()

