"""
ResolveAI — Prometheus Metrics & Health Readiness Test Suite

Validates:
  • GET /metrics endpoint returns valid Prometheus scrape representation
  • http_requests_total partitioned by method, endpoint, status_code
  • http_request_duration_seconds histogram latency measurements
  • tickets_created_total increments upon ticket submission
  • active_websocket_connections gauge with role labels
  • GET /health readiness probe returning sub-system status (database, cache, uptime_seconds)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.metrics import (
    record_sla_breach,
    record_ws_connect,
    record_ws_disconnect,
)


@pytest.mark.asyncio
async def test_get_metrics_endpoint_format(client: AsyncClient):
    """
    Assert that GET /metrics responds with HTTP 200 and standard Prometheus text content type.
    """
    # Make a dummy request first to ensure http_requests_total has samples
    await client.get("/api/v1/docs")

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    assert "text/plain" in resp.headers.get("content-type", "")

    body = resp.text
    # Verify core metric headers exist in output
    assert "# TYPE http_requests_total counter" in body
    assert "# TYPE http_request_duration_seconds histogram" in body
    assert "# TYPE tickets_created_total counter" in body
    assert "# TYPE sla_breaches_total counter" in body
    assert "# TYPE active_websocket_connections gauge" in body


@pytest.mark.asyncio
async def test_http_requests_latency_and_counters_tracked(client: AsyncClient):
    """
    Assert that processing requests updates http_requests_total and http_request_duration_seconds.
    """
    # Perform requests to a known endpoint
    await client.get("/api/v1/docs")
    await client.get("/api/v1/docs")

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text

    # Assert http_requests_total recorded /api/v1/docs
    assert 'http_requests_total{endpoint="/api/v1/docs",method="GET",status_code="200"}' in body
    # Assert histogram duration recorded counts and sums
    assert 'http_request_duration_seconds_count{endpoint="/api/v1/docs",method="GET"}' in body
    assert 'http_request_duration_seconds_bucket{' in body


@pytest.mark.asyncio
async def test_tickets_created_metric_incremented(customer_client: AsyncClient):
    """
    Assert that creating a ticket increments the tickets_created_total Prometheus counter.
    """
    payload = {
        "subject": "Metrics Ingestion Verification",
        "description": "Checking Prometheus counter increment on ticket creation.",
        "category": "billing",
        "priority": "high",
    }
    create_resp = await customer_client.post("/api/v1/tickets", json=payload)
    assert create_resp.status_code == 201

    metrics_resp = await customer_client.get("/metrics")
    assert metrics_resp.status_code == 200
    body = metrics_resp.text

    # Assert category and priority labels match
    assert 'tickets_created_total{category="billing",priority="high"}' in body


@pytest.mark.asyncio
async def test_sla_breach_and_websocket_metrics(client: AsyncClient):
    """
    Assert that SLA breach counter and websocket gauges update correctly.
    """
    # Test SLA breach recording
    record_sla_breach("first_response", "critical")
    record_sla_breach("resolution", "high")

    # Test WebSocket gauge recording
    record_ws_connect("agent")
    record_ws_connect("customer")
    record_ws_disconnect("customer")

    resp = await client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text

    assert 'sla_breaches_total{breach_type="first_response",priority="critical"}' in body
    assert 'sla_breaches_total{breach_type="resolution",priority="high"}' in body
    assert 'active_websocket_connections{role="agent"} 1.0' in body
    assert 'active_websocket_connections{role="customer"} 0.0' in body


@pytest.mark.asyncio
async def test_health_readiness_probe(client: AsyncClient):
    """
    Assert that GET /health returns sub-system readiness indicators:
      • database: ok
      • cache: ok
      • uptime_seconds: float
    """
    resp = await client.get("/health")
    # In test environment, probe passes and returns 200
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "healthy"
    assert data["database"] == "ok"
    assert data["cache"] == "ok"
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0

    assert "checks" in data
    assert data["checks"]["database"] == "ok"
    assert data["checks"]["cache"] == "ok"
