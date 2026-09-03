"""
ResolveAI — Redis & Cache Storage Abstraction

Provides unified caching, key-value storage, and sliding-window rate limiting
with automatic transparent in-memory fallback for local development and offline test environments.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class RedisStore:
    """
    High-performance async cache and rate-limiting storage engine.
    
    Supports real Redis clusters/instances via redis.asyncio, and automatically
    falls back to an in-memory TTL store when Redis is unavailable.
    """

    def __init__(self) -> None:
        self._redis_client: Any = None
        self._redis_available: bool = False
        self._initialized: bool = False
        self._init_lock: asyncio.Lock = asyncio.Lock()

        # In-memory storage fallback
        # key -> (value, expire_timestamp_float | None)
        self._memory_cache: dict[str, tuple[str, float | None]] = {}
        # key -> list of float timestamps
        self._memory_windows: dict[str, list[float]] = {}
        self._mem_lock: asyncio.Lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize Redis connection and verify reachable status."""
        async with self._init_lock:
            if self._initialized:
                return

            try:
                import redis.asyncio as aioredis

                redis_url = str(getattr(settings, "REDIS_URL", "redis://localhost:6379/0"))
                client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
                
                # Test ping with a short timeout to prevent blocking during startup
                await asyncio.wait_for(client.ping(), timeout=1.0)
                self._redis_client = client
                self._redis_available = True
                logger.info("redis_store_connected", url=redis_url)
            except Exception as exc:
                self._redis_available = False
                self._redis_client = None
                logger.info(
                    "redis_store_not_available_using_inmemory",
                    reason=str(exc),
                )

            self._initialized = True

    async def close(self) -> None:
        """Dispose Redis client connections on shutdown."""
        if self._redis_client:
            try:
                await self._redis_client.close()
            except Exception:
                pass
            self._redis_client = None
            self._redis_available = False
            self._initialized = False

    async def get(self, key: str) -> str | None:
        """Retrieve string value for a key."""
        if not self._initialized:
            await self.initialize()

        if self._redis_available and self._redis_client:
            try:
                return await self._redis_client.get(key)
            except Exception as exc:
                logger.warning("redis_get_error_falling_back_to_memory", key=key, error=str(exc))

        # In-memory fallback
        async with self._mem_lock:
            entry = self._memory_cache.get(key)
            if not entry:
                return None
            val, expires_at = entry
            if expires_at is not None and time.time() > expires_at:
                del self._memory_cache[key]
                return None
            return val

    async def set(self, key: str, value: str, expire_seconds: int | None = None) -> None:
        """Store string value for a key with optional TTL in seconds."""
        if not self._initialized:
            await self.initialize()

        if self._redis_available and self._redis_client:
            try:
                if expire_seconds:
                    await self._redis_client.set(key, value, ex=expire_seconds)
                else:
                    await self._redis_client.set(key, value)
                return
            except Exception as exc:
                logger.warning("redis_set_error_falling_back_to_memory", key=key, error=str(exc))

        # In-memory fallback
        async with self._mem_lock:
            expires_at = (time.time() + expire_seconds) if expire_seconds else None
            self._memory_cache[key] = (value, expires_at)

    async def delete(self, key: str) -> None:
        """Delete a key from storage."""
        if not self._initialized:
            await self.initialize()

        if self._redis_available and self._redis_client:
            try:
                await self._redis_client.delete(key)
                return
            except Exception as exc:
                logger.warning("redis_delete_error", key=key, error=str(exc))

        async with self._mem_lock:
            self._memory_cache.pop(key, None)
            self._memory_windows.pop(key, None)

    async def check_sliding_window(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60,
    ) -> tuple[bool, int]:
        """
        Evaluate sliding-window rate limit for a key.

        Args:
            key: Rate limit identifier (e.g. ``ratelimit:ai:user_123``).
            limit: Maximum requests allowed in the rolling window.
            window_seconds: Rolling window duration in seconds (default 60).

        Returns:
            Tuple of ``(is_allowed, retry_after_seconds)``.
        """
        if not self._initialized:
            await self.initialize()

        now = time.time()
        cutoff = now - window_seconds

        if self._redis_available and self._redis_client:
            try:
                pipe = self._redis_client.pipeline(transaction=True)
                pipe.zremrangebyscore(key, 0, cutoff)
                pipe.zcard(key)
                pipe.zrange(key, 0, 0, withscores=True)
                results = await pipe.execute()

                current_count = results[1]
                oldest_items = results[2]

                if current_count >= limit:
                    if oldest_items:
                        oldest_score = oldest_items[0][1]
                        retry_after = max(1, int(oldest_score + window_seconds - now + 1))
                    else:
                        retry_after = window_seconds
                    return False, retry_after

                # Within limit: record this request
                member = f"{now}:{uuid.uuid4().hex[:6]}"
                pipe = self._redis_client.pipeline(transaction=True)
                pipe.zadd(key, {member: now})
                pipe.expire(key, window_seconds * 2)
                await pipe.execute()
                return True, 0

            except Exception as exc:
                logger.warning("redis_rate_limit_error_falling_back_to_memory", error=str(exc))

        # In-memory sliding window fallback
        async with self._mem_lock:
            timestamps = [t for t in self._memory_windows.get(key, []) if t > cutoff]

            if len(timestamps) >= limit:
                oldest_ts = timestamps[0]
                retry_after = max(1, int(oldest_ts + window_seconds - now + 1))
                self._memory_windows[key] = timestamps
                return False, retry_after

            timestamps.append(now)
            self._memory_windows[key] = timestamps
            return True, 0

    async def flush_all(self) -> None:
        """Clear cached data (useful between test runs)."""
        async with self._mem_lock:
            self._memory_cache.clear()
            self._memory_windows.clear()

        if self._redis_available and self._redis_client:
            try:
                # Only delete application keys prefixed with idempotency: or ratelimit:
                keys = await self._redis_client.keys("idempotency:*")
                if keys:
                    await self._redis_client.delete(*keys)
                rl_keys = await self._redis_client.keys("ratelimit:*")
                if rl_keys:
                    await self._redis_client.delete(*rl_keys)
            except Exception:
                pass


# Global singleton instance
redis_store = RedisStore()
