"""
ResolveAI — API Idempotency Key Middleware

Implements standard HTTP Idempotency-Key header support for mutating endpoints
(POST, PUT, PATCH, DELETE) with 24-hour TTL response caching backed by Redis / in-memory store.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse

from app.core.logging import get_logger
from app.core.redis_store import redis_store

logger = get_logger(__name__)

# Mutating HTTP methods requiring idempotency enforcement
MUTATING_METHODS: set[str] = {"POST", "PUT", "PATCH", "DELETE"}

# Standard 24-hour cache TTL
IDEMPOTENCY_TTL_SECONDS: int = 24 * 60 * 60

# Headers that must not be copied from cached response
EXCLUDED_HEADERS: set[str] = {
    "content-length",
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}


class IdempotencyMiddleware(BaseHTTPMiddleware):
    """
    ASGI middleware that checks for the ``Idempotency-Key`` header on mutating requests.

    When present:
      1. Checks if a cached response exists in the key-value store.
      2. If cached: Returns the saved response immediately, preventing duplicate mutation.
      3. If new: Proceeds with execution, captures the response payload, saves it with a 24h TTL, and returns.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> StarletteResponse:
        # Only inspect mutating HTTP methods
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        idempotency_key = request.headers.get("Idempotency-Key") or request.headers.get("idempotency-key")
        if not idempotency_key:
            return await call_next(request)

        idempotency_key = idempotency_key.strip()
        cache_key = f"idempotency:{idempotency_key}"

        # 1. Check if cached response exists
        cached_data_str = await redis_store.get(cache_key)
        if cached_data_str:
            try:
                cached_data = json.loads(cached_data_str)
                status_code: int = cached_data["status_code"]
                raw_body: str = cached_data["body"]
                is_base64: bool = cached_data.get("is_base64", False)
                body_bytes = base64.b64decode(raw_body.encode("utf-8")) if is_base64 else raw_body.encode("utf-8")
                headers: dict[str, str] = cached_data.get("headers", {})

                # Set idempotency telemetry headers
                headers["Idempotency-Replayed"] = "true"
                headers["X-Cache-Lookup"] = "HIT"

                logger.info(
                    "idempotency_cache_hit",
                    idempotency_key=idempotency_key,
                    status_code=status_code,
                    path=request.url.path,
                )

                return StarletteResponse(
                    content=body_bytes,
                    status_code=status_code,
                    headers=headers,
                    media_type=headers.get("content-type", "application/json"),
                )
            except Exception as exc:
                logger.warning(
                    "idempotency_cache_deserialization_error",
                    idempotency_key=idempotency_key,
                    error=str(exc),
                )

        # 2. Key is new: Process the request
        response = await call_next(request)

        # Consume and buffer the response body
        body_chunks: list[bytes] = []
        async for chunk in response.body_iterator:
            if isinstance(chunk, bytes):
                body_chunks.append(chunk)
            elif isinstance(chunk, str):
                body_chunks.append(chunk.encode("utf-8"))
        body_bytes = b"".join(body_chunks)

        # 3. Only cache non-5xx responses (do not persist unexpected server failures)
        if response.status_code < 500:
            try:
                # Filter safe headers to store
                saved_headers = {
                    k.lower(): v
                    for k, v in response.headers.items()
                    if k.lower() not in EXCLUDED_HEADERS
                }

                # Encode body to UTF-8 text if valid JSON/text, else base64
                try:
                    body_text = body_bytes.decode("utf-8")
                    is_base64 = False
                except UnicodeDecodeError:
                    body_text = base64.b64encode(body_bytes).decode("utf-8")
                    is_base64 = True

                cache_payload = {
                    "status_code": response.status_code,
                    "headers": saved_headers,
                    "body": body_text,
                    "is_base64": is_base64,
                }

                await redis_store.set(
                    cache_key,
                    json.dumps(cache_payload),
                    expire_seconds=IDEMPOTENCY_TTL_SECONDS,
                )

                logger.info(
                    "idempotency_response_cached",
                    idempotency_key=idempotency_key,
                    status_code=response.status_code,
                    ttl_seconds=IDEMPOTENCY_TTL_SECONDS,
                )
            except Exception as cache_err:
                logger.warning(
                    "idempotency_caching_failed",
                    idempotency_key=idempotency_key,
                    error=str(cache_err),
                )

        # 4. Return new StarletteResponse with the consumed body and original metadata
        response_headers = dict(response.headers)
        response_headers["Idempotency-Key"] = idempotency_key
        response_headers["X-Cache-Lookup"] = "MISS"

        return StarletteResponse(
            content=body_bytes,
            status_code=response.status_code,
            headers=response_headers,
            media_type=response.media_type,
        )


async def clear_idempotency_cache() -> None:
    """Helper to wipe idempotency cache for test isolation."""
    await redis_store.flush_all()
