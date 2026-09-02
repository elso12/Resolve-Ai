"""
ResolveAI — Ticket Lifecycle, IDOR Isolation & State Machine Test Suite
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_ticket_success(customer_client: AsyncClient):
    """Test customer successfully opening a new support ticket."""
    payload = {
        "subject": "Cannot connect to REST API",
        "description": "I am getting 401 unauthorized errors when sending valid API tokens.",
        "category": "technical",
        "priority": "high",
    }
    response = await customer_client.post("/api/v1/tickets", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["subject"] == payload["subject"]
    assert data["status"] == "open"
    assert data["ticket_number"].startswith("RSV-")
    assert data["first_response_due_at"] is not None
    assert data["resolution_due_at"] is not None


@pytest.mark.asyncio
async def test_idor_protection_cross_customer(
    customer_client: AsyncClient,
    customer_b_client: AsyncClient,
):
    """
    IDOR Security Test: Assert Customer B cannot view Customer A's ticket.
    """
    # Customer A creates a ticket
    create_res = await customer_client.post(
        "/api/v1/tickets",
        json={
            "subject": "Confidential Security Inquiry",
            "description": "Sensitive customer account details here.",
            "category": "account",
            "priority": "medium",
        },
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Customer A can access their own ticket
    res_a = await customer_client.get(f"/api/v1/tickets/{ticket_id}")
    assert res_a.status_code == 200

    # Customer B attempts to access Customer A's ticket -> Must be 403 Forbidden
    res_b = await customer_b_client.get(f"/api/v1/tickets/{ticket_id}")
    assert res_b.status_code == 403
    assert "access denied" in res_b.json()["detail"].lower()


@pytest.mark.asyncio
async def test_fsm_valid_state_transitions(
    customer_client: AsyncClient,
    agent_client: AsyncClient,
):
    """
    State Machine Test: Validate transitions open -> in_progress -> resolved -> closed.
    """
    create_res = await customer_client.post(
        "/api/v1/tickets",
        json={
            "subject": "Billing issue on monthly invoice",
            "description": "Please check charge on my card.",
            "category": "billing",
            "priority": "low",
        },
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # 1. open -> in_progress
    res1 = await agent_client.patch(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "in_progress"},
    )
    assert res1.status_code == 200
    assert res1.json()["status"] == "in_progress"

    # 2. in_progress -> resolved
    res2 = await agent_client.patch(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "resolved"},
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "resolved"
    assert res2.json()["resolved_at"] is not None

    # 3. resolved -> closed
    res3 = await agent_client.patch(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "closed"},
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "closed"


@pytest.mark.asyncio
async def test_fsm_invalid_state_transition_fails(
    customer_client: AsyncClient,
    agent_client: AsyncClient,
):
    """
    State Machine Violation Test: Assert closed -> in_progress raises HTTP 400.
    """
    create_res = await customer_client.post(
        "/api/v1/tickets",
        json={
            "subject": "General question",
            "description": "How do I update user profiles?",
            "category": "general",
            "priority": "low",
        },
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    # Fast forward to closed
    await agent_client.patch(f"/api/v1/tickets/{ticket_id}/status", json={"status": "resolved"})
    await agent_client.patch(f"/api/v1/tickets/{ticket_id}/status", json={"status": "closed"})

    # Attempt illegal transition: closed -> in_progress
    res = await agent_client.patch(
        f"/api/v1/tickets/{ticket_id}/status",
        json={"status": "in_progress"},
    )
    assert res.status_code == 400
    assert "terminal state" in res.json()["detail"].lower() or "cannot" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_customer_cannot_post_internal_notes(
    customer_client: AsyncClient,
):
    """
    Security Test: Assert customer attempting to post an internal note gets HTTP 403.
    """
    create_res = await customer_client.post(
        "/api/v1/tickets",
        json={
            "subject": "Password reset inquiry",
            "description": "Need assistance resetting 2FA.",
            "category": "account",
            "priority": "medium",
        },
    )
    assert create_res.status_code == 201
    ticket_id = create_res.json()["id"]

    res = await customer_client.post(
        f"/api/v1/tickets/{ticket_id}/messages",
        json={"body": "Customer secret note attempt", "is_internal": True},
    )
    assert res.status_code == 403
    assert "cannot post internal notes" in res.json()["detail"].lower()
