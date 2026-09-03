"""
ResolveAI — Idempotency Keys & Rate Limiting Test Suite

Validates:
  • HTTP Idempotency-Key header on mutating operations prevents duplicate execution
  • Cached response replay with matching payload and telemetry headers
  • Sliding-window rate limiting on standard routes (60 req/min) and AI routes (10 req/min)
  • HTTP 429 Too Many Requests with standard Retry-After header
  • User-level rate quota isolation
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.idempotency import clear_idempotency_cache
from app.core.rate_limiter import reset_rate_limiter
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage


@pytest.fixture(autouse=True)
async def reset_caches_before_each_test():
    """Ensure idempotency and rate limiting stores are clean before each test."""
    await clear_idempotency_cache()
    await reset_rate_limiter()
    yield
    await clear_idempotency_cache()
    await reset_rate_limiter()


# ── Idempotency Tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_idempotency_ticket_creation_executes_only_once(
    customer_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Assert that sending two identical POST /tickets requests with the same
    Idempotency-Key creates only ONE ticket in the database.
    """
    idempotency_key = f"key-{uuid.uuid4()}"
    payload = {
        "subject": "Payment Gateway Timeout",
        "description": "Received a timeout when submitting payment for invoice #9812.",
        "category": "billing",
        "priority": "high",
    }
    headers = {"Idempotency-Key": idempotency_key}

    # First request: Creates the ticket
    resp1 = await customer_client.post("/api/v1/tickets", json=payload, headers=headers)
    assert resp1.status_code == 201, resp1.text
    data1 = resp1.json()
    ticket_id = data1["id"]
    assert resp1.headers.get("X-Cache-Lookup") == "MISS"

    # Verify database has exactly 1 ticket
    stmt = select(func.count(Ticket.id))
    count1 = (await db_session.execute(stmt)).scalar_one()
    assert count1 == 1

    # Second request: Replays cached response
    resp2 = await customer_client.post("/api/v1/tickets", json=payload, headers=headers)
    assert resp2.status_code == 201
    data2 = resp2.json()
    assert data2["id"] == ticket_id
    assert data2["ticket_number"] == data1["ticket_number"]
    assert data2["subject"] == data1["subject"]
    assert resp2.headers.get("Idempotency-Replayed") == "true"
    assert resp2.headers.get("X-Cache-Lookup") == "HIT"

    # Crucial assertion: Database STILL has exactly 1 ticket
    # Expire session cache to ensure we read fresh database state
    db_session.expire_all()
    count2 = (await db_session.execute(stmt)).scalar_one()
    assert count2 == 1, "Duplicate ticket was created despite using the same Idempotency-Key!"


@pytest.mark.asyncio
async def test_idempotency_different_keys_creates_distinct_tickets(
    customer_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Assert that requests with distinct Idempotency-Keys result in separate mutations.
    """
    payload = {
        "subject": "Distinct Ticket Test",
        "description": "Verifying distinct keys generate independent tickets.",
        "category": "technical",
        "priority": "low",
    }

    key_a = f"key-a-{uuid.uuid4()}"
    key_b = f"key-b-{uuid.uuid4()}"

    resp_a = await customer_client.post("/api/v1/tickets", json=payload, headers={"Idempotency-Key": key_a})
    resp_b = await customer_client.post("/api/v1/tickets", json=payload, headers={"Idempotency-Key": key_b})

    assert resp_a.status_code == 201
    assert resp_b.status_code == 201

    id_a = resp_a.json()["id"]
    id_b = resp_b.json()["id"]
    assert id_a != id_b

    db_session.expire_all()
    stmt = select(func.count(Ticket.id))
    total = (await db_session.execute(stmt)).scalar_one()
    assert total == 2


@pytest.mark.asyncio
async def test_idempotency_message_creation_executes_only_once(
    customer_client: AsyncClient,
    agent_client: AsyncClient,
    db_session: AsyncSession,
):
    """
    Assert that posting a message with an Idempotency-Key only appends one message to the ticket.
    """
    # 1. Create a ticket first
    create_resp = await customer_client.post(
        "/api/v1/tickets",
        json={
            "subject": "Message Thread Test",
            "description": "Testing message idempotency.",
            "category": "general",
            "priority": "medium",
        },
    )
    assert create_resp.status_code == 201
    ticket_id = create_resp.json()["id"]

    # 2. Post a message with an Idempotency-Key
    idempotency_key = f"msg-key-{uuid.uuid4()}"
    msg_payload = {"body": "Here is the log file you requested.", "is_internal": False}
    headers = {"Idempotency-Key": idempotency_key}

    res1 = await agent_client.post(f"/api/v1/tickets/{ticket_id}/messages", json=msg_payload, headers=headers)
    assert res1.status_code == 201
    msg_id = res1.json()["id"]

    # 3. Repeat with the same key
    res2 = await agent_client.post(f"/api/v1/tickets/{ticket_id}/messages", json=msg_payload, headers=headers)
    assert res2.status_code == 201
    assert res2.json()["id"] == msg_id
    assert res2.headers.get("Idempotency-Replayed") == "true"

    # 4. Verify only one message exists in database for this ticket
    db_session.expire_all()
    stmt = select(func.count(TicketMessage.id)).where(TicketMessage.ticket_id == ticket_id)
    msg_count = (await db_session.execute(stmt)).scalar_one()
    assert msg_count == 1


# ── Rate Limiting Tests ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_rate_limit_expensive_ai_tier_exceeded(customer_client: AsyncClient):
    """
    Assert that expensive AI routes enforce the strict 10 requests/minute tier limit,
    returning HTTP 429 and Retry-After on the 11th request.
    """
    classify_payload = {
        "subject": "System crash",
        "description": "Database connection pool exhausted.",
    }

    # First 10 requests must succeed
    for i in range(10):
        resp = await customer_client.post("/api/v1/ai/classify", json=classify_payload)
        assert resp.status_code == 200, f"Request #{i+1} failed with status {resp.status_code}"
        assert resp.headers.get("X-RateLimit-Limit") == "10"

    # 11th request must be rate-limited (HTTP 429)
    blocked_resp = await customer_client.post("/api/v1/ai/classify", json=classify_payload)
    assert blocked_resp.status_code == 429
    assert "Retry-After" in blocked_resp.headers
    retry_after = int(blocked_resp.headers["Retry-After"])
    assert retry_after >= 1
    assert blocked_resp.headers.get("X-RateLimit-Remaining") == "0"
    data = blocked_resp.json()
    assert "rate limit exceeded" in data["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limit_standard_tier_exceeded(customer_client: AsyncClient):
    """
    Assert that standard API endpoints enforce the 60 requests/minute tier limit,
    returning HTTP 429 when exceeded.
    """
    # Send 60 requests to a standard endpoint
    for i in range(60):
        resp = await customer_client.get("/api/v1/tickets")
        assert resp.status_code == 200, f"Request #{i+1} failed with status {resp.status_code}"
        assert resp.headers.get("X-RateLimit-Limit") == "60"

    # 61st request must trigger HTTP 429
    blocked_resp = await customer_client.get("/api/v1/tickets")
    assert blocked_resp.status_code == 429
    assert "Retry-After" in blocked_resp.headers
    retry_after = int(blocked_resp.headers["Retry-After"])
    assert retry_after >= 1
    assert "rate limit exceeded" in blocked_resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_rate_limit_distinct_users_isolated(
    customer_client: AsyncClient,
    agent_client: AsyncClient,
):
    """
    Assert that rate limiting is enforced per-user and one user's exhausted
    quota does not affect another authenticated user.
    """
    classify_payload = {
        "subject": "Billing issue",
        "description": "Incorrect line item on recent receipt.",
    }

    # Customer exhausts their 10 req/min quota
    for _ in range(10):
        resp = await customer_client.post("/api/v1/ai/classify", json=classify_payload)
        assert resp.status_code == 200

    # Customer is blocked on 11th
    customer_blocked = await customer_client.post("/api/v1/ai/classify", json=classify_payload)
    assert customer_blocked.status_code == 429

    # Agent has their own separate quota and should succeed
    agent_resp = await agent_client.post("/api/v1/ai/classify", json=classify_payload)
    assert agent_resp.status_code == 200, "Agent was improperly throttled by Customer's quota!"


@pytest.mark.asyncio
async def test_exempt_paths_not_rate_limited(client: AsyncClient):
    """
    Assert that system endpoints like /api/v1/docs and /api/v1/openapi.json are exempt from rate limits
    and never return HTTP 429 even after many requests.
    """
    for _ in range(70):
        resp = await client.get("/api/v1/docs")
        assert resp.status_code == 200
        assert resp.status_code != 429
