"""
ResolveAI — Role-Based Access Control (RBAC) Test Suite

Verifies strict HTTP 403 Forbidden enforcement for unauthorized roles.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_customer_cannot_access_analytics(customer_client: AsyncClient):
    """Assert customers cannot access manager analytics."""
    res = await customer_client.get("/api/v1/analytics/overview")
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_customer_cannot_update_ticket_status(
    customer_client: AsyncClient,
):
    """Assert customers cannot update ticket status via agent endpoint."""
    res = await customer_client.patch(
        "/api/v1/tickets/1/status",
        json={"status": "CLOSED"},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_customer_cannot_assign_tickets(customer_client: AsyncClient):
    """Assert customers cannot assign tickets to agents."""
    res = await customer_client.post(
        "/api/v1/tickets/1/assign",
        json={"agent_id": 3},
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_customer_cannot_publish_knowledge_articles(
    customer_client: AsyncClient,
):
    """Assert customers cannot publish new knowledge base articles."""
    payload = {
        "title": "Unauthorized Article",
        "content": "This should not be allowed.",
        "category": "General",
        "is_published": True,
    }
    res = await customer_client.post("/api/v1/knowledge/articles", json=payload)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_agent_can_access_analytics_and_articles(
    agent_client: AsyncClient,
):
    """Assert support agents and managers have access to analytics and knowledge management."""
    res_analytics = await agent_client.get("/api/v1/analytics/overview")
    assert res_analytics.status_code == 200

    res_article = await agent_client.post(
        "/api/v1/knowledge/articles",
        json={
            "title": "Agent Knowledge Test Guide",
            "content": "Step-by-step resolution guide for agents.",
            "category": "Technical",
            "is_published": True,
        },
    )
    assert res_article.status_code == 201
