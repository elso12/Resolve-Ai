"""
ResolveAI — Rate Limiting Engine

Implements sliding-window rate limiting with tiered limits:
  • Standard API endpoints: 60 requests/minute per user
  • Expensive AI endpoints (/ai/classify, /ai/suggest-reply, /knowledge/ask): 10 requests/minute per user
Returns HTTP 429 Too Many Requests with standard Retry-After header.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis_store import redis_store

logger = get_logger(__name__)

# Tier limits (requests per 60-second window)
AI_TIER_LIMIT: int = 10
STANDARD_TIER_LIMIT: int = 60
WINDOW_SECONDS: int = 60

# Regex patterns identifying expensive AI operations
EXPENSIVE_AI_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^/api/v1/ai/classify", re.IGNORECASE),
    re.compile(r"^/api/v1/ai/.*suggest-reply", re.IGNORECASE),
    re.compile(r"^/api/v1/ai/.*summarize", re.IGNORECASE),
    re.compile(r"^/api/v1/knowledge/ask", re.IGNORECASE),
]

# Paths completely exempt from rate limiting (system health, metrics, docs)
EXEMPT_PATHS: set[str] = {
    "/health",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    f"{settings.API_V1_STR}/openapi.json",
    f"{settings.API_V1_STR}/docs",
    f"{settings.API_V1_STR}/redoc",
}


def is_exempt_path(path: str) -> bool:
    """Check if request path is exempt from rate limits."""
    if path in EXEMPT_PATHS:
        return True
    if path.startswith("/static"):
        return True
    return False


def is_expensive_ai_path(path: str) -> bool:
    """Check if request targets an expensive LLM / RAG endpoint."""
    return any(pattern.search(path) for pattern in EXPENSIVE_AI_PATTERNS)


def extract_user_identifier(request: Request) -> str:
    """
    Extract a unique caller identifier.
    
    Prefers the authenticated JWT subject claim ('sub').
    Falls back to client IP address for unauthenticated requests.
    """
    auth_header = request.headers.get("Authorization") or ""
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        try:
            # Decode token claims
            claims = jwt.decode(
                token,
                settings.SECRET_KEY,
                algorithms=[settings.ALGORITHM],
                options={"verify_exp": False},  # Still attribute expired tokens to user
            )
            sub = claims.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            pass

    # Unauthenticated fallback: IP address
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    elif request.client and request.client.host:
        client_ip = request.client.host
    else:
        client_ip = "127.0.0.1"

    return f"ip:{client_ip}"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that enforces sliding-window rate limits per user/IP.

    Enforces:
      • 10 requests / min for expensive AI operations
      • 60 requests / min for standard API operations
    Returns HTTP 429 with standard Retry-After header on breach.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> StarletteResponse:
        # 1. Skip preflight CORS and exempt system endpoints
        if request.method == "OPTIONS" or is_exempt_path(request.url.path):
            return await call_next(request)

        # 2. Only rate limit API paths
        if not request.url.path.startswith(settings.API_V1_STR):
            return await call_next(request)

        # 3. Determine tier limit
        path = request.url.path
        if is_expensive_ai_path(path):
            limit = AI_TIER_LIMIT
            tier_name = "ai"
        else:
            limit = STANDARD_TIER_LIMIT
            tier_name = "standard"

        # 4. Identify caller
        user_id = extract_user_identifier(request)
        rate_key = f"ratelimit:{tier_name}:{user_id}"

        # 5. Check sliding window
        allowed, retry_after = await redis_store.check_sliding_window(
            key=rate_key,
            limit=limit,
            window_seconds=WINDOW_SECONDS,
        )

        if not allowed:
            logger.warning(
                "rate_limit_exceeded",
                caller=user_id,
                tier=tier_name,
                path=path,
                limit=limit,
                retry_after=retry_after,
            )

            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Rate limit exceeded for tier '{tier_name}'. Maximum {limit} requests per minute.",
                    "retry_after": retry_after,
                },
                headers={
                    "Retry-After": str(retry_after),
                    "X-RateLimit-Limit": str(limit),
                    "X-RateLimit-Remaining": "0",
                },
            )

        # 6. Proceed with request
        response: StarletteResponse = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(limit)

        return response


async def reset_rate_limiter() -> None:
    """Helper to reset rate limit quotas for test isolation."""
    await redis_store.flush_all()
