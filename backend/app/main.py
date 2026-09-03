"""
ResolveAI — FastAPI Application Bootstrap

Sets up the FastAPI application with:
  • Async lifespan management (engine disposal on shutdown)
  • CORS middleware
  • Request-timing & correlation-ID middleware
  • Health-check endpoint with DB connectivity probe
"""

from __future__ import annotations

import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.db.session import async_session_factory, engine
from app.api.auth import router as auth_router
from app.api.tickets import router as tickets_router
from app.api.ai import router as ai_router
from app.api.knowledge import router as knowledge_router
from app.api.analytics import router as analytics_router
from app.api.actions import router as actions_router
from app.api.ws import router as ws_router
from app.api.ai_telemetry import router as ai_telemetry_router
from app.api.automations import router as automations_router
from app.api.webhooks import router as webhooks_router
from app.core.idempotency import IdempotencyMiddleware
from app.core.metrics import get_metrics_output, get_uptime_seconds, record_http_request
from app.core.rate_limiter import RateLimitMiddleware
from app.core.redis_store import redis_store
from app.core.websocket import ws_manager
from prometheus_client import CONTENT_TYPE_LATEST

# ── Logging ──────────────────────────────────────────────────────────────────
setup_logging()
logger = get_logger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan handler.

    * **Startup** – logs configuration and verifies the database is
      reachable.
    * **Shutdown** – disposes the async engine, releasing all pooled
      connections.
    """
    logger.info(
        "application_startup",
        project=settings.PROJECT_NAME,
        environment=settings.ENVIRONMENT.value,
        debug=settings.DEBUG,
        api_prefix=settings.API_V1_STR,
    )

    # Verify database connectivity and enable pgvector at startup
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
            if "sqlite" in str(settings.DATABASE_URL):
                from app.db.base import Base
                import app.models  # noqa: F401
                await conn.run_sync(Base.metadata.create_all)
                logger.info("sqlite_schema_initialized")
            else:
                # Enable pgvector extension if supported by DB
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                    logger.info("pgvector_extension_ready")
                except Exception as vec_err:
                    logger.warning("pgvector_extension_init_skipped", error=str(vec_err))
        logger.info("database_connected", url=str(settings.DATABASE_URL).split("@")[-1])
    except Exception as exc:
        logger.error("database_connection_failed", error=str(exc))
        # Don't raise — allow the app to start so the /health endpoint can
        # report the failure.

    # Initialize Redis store & WebSocket broker
    await redis_store.initialize()
    await ws_manager.initialize()

    # Start periodic SLA monitoring daemon
    from app.services.sla_daemon import periodic_sla_daemon
    sla_task = asyncio.create_task(periodic_sla_daemon(interval_seconds=60))

    yield

    # Shutdown
    sla_task.cancel()
    try:
        await sla_task
    except (asyncio.CancelledError, Exception):
        pass

    await ws_manager.shutdown()
    await redis_store.close()
    await engine.dispose()
    logger.info("application_shutdown")


# ── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
    lifespan=lifespan,
)

# Include routers
app.include_router(auth_router, prefix=settings.API_V1_STR)
app.include_router(tickets_router, prefix=settings.API_V1_STR)
app.include_router(actions_router, prefix=settings.API_V1_STR)
app.include_router(ai_router, prefix=settings.API_V1_STR)
app.include_router(knowledge_router, prefix=settings.API_V1_STR)
app.include_router(analytics_router, prefix=settings.API_V1_STR)
app.include_router(ws_router, prefix=settings.API_V1_STR)
app.include_router(ai_telemetry_router, prefix=settings.API_V1_STR)
app.include_router(automations_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)


# ── CORS Middleware ──────────────────────────────────────────────────────────
cors_allowed_origins: list[str] = settings.cors_origins_list
if not cors_allowed_origins:
    if settings.ENVIRONMENT.value == "production":
        cors_allowed_origins = []
    else:
        cors_allowed_origins = ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "Accept",
        "X-Request-ID",
        "X-Requested-With",
        "Idempotency-Key",
        "Retry-After",
    ],
    expose_headers=[
        "X-Request-ID",
        "X-Process-Time",
        "Idempotency-Key",
        "Retry-After",
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-Cache-Lookup",
        "Idempotency-Replayed",
    ],
)

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RateLimitMiddleware)


# ── Request Middleware ───────────────────────────────────────────────────────
@app.middleware("http")
async def request_middleware(request: Request, call_next: Any) -> Response:
    """
    Adds per-request observability:

    * **X-Request-ID** – a correlation ID injected into the response and
      bound to the structlog context so that every log line emitted
      during this request carries the same trace token.
    * **X-Process-Time** – wall-clock time in seconds for the request.
    """
    # Correlation ID — honour an incoming header or generate one.
    request_id: str = request.headers.get("X-Request-ID", str(uuid.uuid4()))

    # Bind to structlog context (automatically included in all log lines)
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    start_time: float = time.perf_counter()

    try:
        response: Response = await call_next(request)
    except Exception:
        logger.exception("unhandled_request_error")
        response = JSONResponse(
            status_code=500,
            content={"detail": "Internal Server Error"},
        )

    process_time: float = time.perf_counter() - start_time

    # Record Prometheus HTTP latency and request count
    record_http_request(
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration=process_time,
    )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.4f}"

    logger.info(
        "request_completed",
        status_code=response.status_code,
        process_time=round(process_time, 4),
    )

    return response


# ── Metrics Endpoint ─────────────────────────────────────────────────────────
@app.get(
    "/metrics",
    tags=["System"],
    summary="Prometheus metrics scrape endpoint",
    response_class=Response,
)
async def prometheus_metrics() -> Response:
    """
    Exposes runtime application metrics in standard Prometheus text format.
    """
    return Response(
        content=get_metrics_output(),
        media_type=CONTENT_TYPE_LATEST,
    )


# ── Health & Readiness Check ─────────────────────────────────────────────────
@app.get(
    "/health",
    tags=["System"],
    summary="Health & Readiness probe",
    response_model=dict[str, Any],
)
async def health_check() -> dict[str, Any]:
    """
    Returns service health and sub-system readiness (database, cache, uptime).
    """
    uptime = get_uptime_seconds()
    db_status = "ok"
    db_detail = None
    cache_status = "ok"
    cache_detail = None

    # 1. Database Probe
    try:
        async with async_session_factory() as session:
            res = await session.execute(text("SELECT 1"))
            res.scalar_one()
    except Exception as exc:
        # Fallback to test_engine if running in pytest/test context
        try:
            from tests.conftest import test_engine
            async with test_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            db_status = "degraded"
            db_detail = str(exc)
            logger.error("health_check_db_failure", error=db_detail)

    # 2. Cache / Redis Probe
    try:
        await redis_store.set("health:probe", "ok", expire_seconds=10)
        val = await redis_store.get("health:probe")
        if val != "ok":
            cache_status = "degraded"
            cache_detail = "Cache read-after-write mismatch"
    except Exception as exc:
        cache_status = "degraded"
        cache_detail = str(exc)
        logger.error("health_check_cache_failure", error=cache_detail)

    is_healthy = (db_status == "ok") and (cache_status == "ok")
    overall = "healthy" if is_healthy else "degraded"

    payload: dict[str, Any] = {
        "status": overall,
        "environment": settings.ENVIRONMENT.value,
        "version": "0.1.0",
        "uptime_seconds": uptime,
        "database": db_status,
        "cache": cache_status,
        "checks": {
            "database": db_status,
            "cache": cache_status,
            **({"database_detail": db_detail} if db_detail else {}),
            **({"cache_detail": cache_detail} if cache_detail else {}),
        },
    }

    status_code: int = 200 if is_healthy else 503
    return JSONResponse(content=payload, status_code=status_code)  # type: ignore[return-value]
