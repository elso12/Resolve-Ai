"""
ResolveAI — Prometheus Observability & Metrics Service

Defines core Prometheus telemetry:
  • http_requests_total (Counter partitioned by method, endpoint, and status_code)
  • http_request_duration_seconds (Histogram measuring p50, p95, and p99 response latencies)
  • tickets_created_total (Counter tracking inbound volume by category and priority)
  • sla_breaches_total (Counter tracking SLA response and resolution violations)
  • active_websocket_connections (Gauge tracking online agents and customers)
"""

from __future__ import annotations

import re
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Application startup timestamp
START_TIME: float = time.time()

# ── Metric Definitions ────────────────────────────────────────────────────────

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total count of HTTP requests processed by method, endpoint, and status code.",
    ["method", "endpoint", "status_code"],
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency histogram in seconds measuring p50, p95, and p99 response times.",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 10.0),
)

TICKETS_CREATED_TOTAL = Counter(
    "tickets_created_total",
    "Total inbound customer support tickets created, partitioned by category and priority.",
    ["category", "priority"],
)

SLA_BREACHES_TOTAL = Counter(
    "sla_breaches_total",
    "Total SLA response and resolution breaches detected by the SLA daemon.",
    ["breach_type", "priority"],
)

ACTIVE_WEBSOCKET_CONNECTIONS = Gauge(
    "active_websocket_connections",
    "Number of active WebSocket client connections partitioned by user role.",
    ["role"],
)

# Initialize websocket gauge labels to zero
for role in ("customer", "agent", "manager", "admin"):
    ACTIVE_WEBSOCKET_CONNECTIONS.labels(role=role).set(0)


# ── URL Normalization (High-Cardinality Prevention) ──────────────────────────

_UUID_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.IGNORECASE)
_NUMERIC_ID_PATTERN = re.compile(r"/\d+(?=/|$)")
_TICKET_NUM_PATTERN = re.compile(r"/RSV-[0-9]{4}-[A-Z0-9]+", re.IGNORECASE)


def normalize_endpoint(path: str) -> str:
    """
    Normalize route paths by parameterizing identifiers to prevent
    high-cardinality explosions in Prometheus metrics.

    Examples:
      /api/v1/tickets/42/messages -> /api/v1/tickets/{id}/messages
      /api/v1/tickets/RSV-2026-A1B2C -> /api/v1/tickets/{id}
    """
    p = _UUID_PATTERN.sub("{id}", path)
    p = _TICKET_NUM_PATTERN.sub("/{id}", p)
    p = _NUMERIC_ID_PATTERN.sub("/{id}", p)
    return p


# ── Instrumentation Functions ─────────────────────────────────────────────────

def get_uptime_seconds() -> float:
    """Return application uptime in seconds."""
    return round(time.time() - START_TIME, 2)


def record_http_request(method: str, path: str, status_code: int, duration: float) -> None:
    """Record HTTP request latency and increment the total requests counter."""
    endpoint = normalize_endpoint(path)
    HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status_code=str(status_code)).inc()
    HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)


def record_ticket_created(category: str, priority: str) -> None:
    """Increment tickets_created_total counter."""
    TICKETS_CREATED_TOTAL.labels(category=str(category).lower(), priority=str(priority).lower()).inc()


def record_sla_breach(breach_type: str, priority: str) -> None:
    """Increment sla_breaches_total counter."""
    SLA_BREACHES_TOTAL.labels(breach_type=str(breach_type).lower(), priority=str(priority).lower()).inc()


def record_ws_connect(role: str) -> None:
    """Increment active_websocket_connections gauge for role."""
    ACTIVE_WEBSOCKET_CONNECTIONS.labels(role=str(role).lower()).inc()


def record_ws_disconnect(role: str) -> None:
    """Decrement active_websocket_connections gauge for role."""
    ACTIVE_WEBSOCKET_CONNECTIONS.labels(role=str(role).lower()).dec()


def get_metrics_output() -> bytes:
    """Generate scrape text in standard Prometheus representation."""
    return generate_latest(REGISTRY)
