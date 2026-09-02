"""
ResolveAI — Real-Time WebSocket Connection Manager & Agent Collision Engine

Manages live WebSocket connections per ticket and per organization. Supports
Redis Pub/Sub for distributed multi-pod fanout with automatic in-memory fallback
for local development resilience.

Tracks agent presence with a 30-second heartbeat to detect collisions (Zendesk /
Intercom style), alerting agents when multiple specialists are viewing the same ticket.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import UserRole
from app.models.user import User

logger = get_logger(__name__)

VIEWER_HEARTBEAT_TTL_SECONDS = 30.0


@dataclass
class ViewerInfo:
    """Active viewer metadata for agent collision tracking."""

    user_id: int
    full_name: str
    email: str
    role: str
    last_heartbeat: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_id": self.user_id,
            "full_name": self.full_name,
            "email": self.email,
            "role": self.role,
            "last_heartbeat": self.last_heartbeat,
        }


class ConnectionManager:
    """
    Manages active WebSocket connections, message routing, and agent collision state.
    """

    def __init__(self) -> None:
        # ticket_id (str) -> set of (WebSocket, User)
        self._ticket_connections: dict[str, set[tuple[WebSocket, User]]] = {}
        # org_id (int) -> set of (WebSocket, User)
        self._org_connections: dict[int, set[tuple[WebSocket, User]]] = {}
        # ticket_id (str) -> user_id (int) -> ViewerInfo
        self._active_viewers: dict[str, dict[int, ViewerInfo]] = {}

        # Redis connection state
        self._redis_client: Any = None
        self._pubsub_task: asyncio.Task[None] | None = None
        self._redis_available: bool = False

    async def initialize(self) -> None:
        """Initialize Redis Pub/Sub if configured and reachable."""
        try:
            import redis.asyncio as aioredis  # type: ignore

            redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
            client = aioredis.from_url(redis_url, encoding="utf-8", decode_responses=True)
            # Test ping with a 1-second timeout
            await asyncio.wait_for(client.ping(), timeout=1.0)
            self._redis_client = client
            self._redis_available = True
            logger.info("websocket_redis_pubsub_connected", url=redis_url)

            # Start listener task for distributed cluster events
            self._pubsub_task = asyncio.create_task(self._listen_redis())
        except Exception as exc:
            self._redis_available = False
            self._redis_client = None
            logger.info(
                "websocket_redis_not_available_using_inmemory",
                reason=str(exc),
            )

    async def shutdown(self) -> None:
        """Close connections and cleanup."""
        if self._pubsub_task:
            self._pubsub_task.cancel()
        if self._redis_client:
            try:
                await self._redis_client.close()
            except Exception:
                pass

    async def _listen_redis(self) -> None:
        """Listen to Redis Pub/Sub channels for cross-pod event broadcasting."""
        try:
            pubsub = self._redis_client.pubsub()
            await pubsub.psubscribe("resolveai:ticket:*", "resolveai:org:*")
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    payload = json.loads(message["data"])
                    event_type = payload.get("type")
                    data = payload.get("data", {})

                    if channel.startswith("resolveai:ticket:"):
                        ticket_id = channel.split(":")[-1]
                        await self._local_broadcast_ticket(ticket_id, event_type, data)
                    elif channel.startswith("resolveai:org:"):
                        org_id = int(channel.split(":")[-1])
                        await self._local_broadcast_org(org_id, event_type, data)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.warning("redis_pubsub_listener_error", error=str(exc))

    # ── Connection Lifecycle ─────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, ticket_id: str, user: User) -> None:
        """Register a new active WebSocket connection."""
        await websocket.accept()

        ticket_key = str(ticket_id)
        if ticket_key not in self._ticket_connections:
            self._ticket_connections[ticket_key] = set()
        self._ticket_connections[ticket_key].add((websocket, user))

        org_id = user.organization_id
        if org_id not in self._org_connections:
            self._org_connections[org_id] = set()
        self._org_connections[org_id].add((websocket, user))

        logger.info(
            "websocket_client_connected",
            ticket_id=ticket_key,
            user_id=user.id,
            user_name=user.full_name,
            role=user.role.value,
        )

        # If user is a support specialist / agent, track viewer collision
        if user.role in (UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN):
            self.record_heartbeat(ticket_key, user)
            await self.broadcast_viewers(ticket_key)

    async def disconnect(self, websocket: WebSocket, ticket_id: str, user: User) -> None:
        """Unregister a disconnected WebSocket client."""
        ticket_key = str(ticket_id)
        if ticket_key in self._ticket_connections:
            self._ticket_connections[ticket_key].discard((websocket, user))
            if not self._ticket_connections[ticket_key]:
                del self._ticket_connections[ticket_key]

        org_id = user.organization_id
        if org_id in self._org_connections:
            self._org_connections[org_id].discard((websocket, user))
            if not self._org_connections[org_id]:
                del self._org_connections[org_id]

        logger.info("websocket_client_disconnected", ticket_id=ticket_key, user_id=user.id)

        # If agent, check if any remaining connections for this user exist on the ticket
        if user.role in (UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN):
            has_other_connection = False
            for ws, u in self._ticket_connections.get(ticket_key, set()):
                if u.id == user.id:
                    has_other_connection = True
                    break

            if not has_other_connection:
                if ticket_key in self._active_viewers:
                    self._active_viewers[ticket_key].pop(user.id, None)
                    if not self._active_viewers[ticket_key]:
                        del self._active_viewers[ticket_key]
                await self.broadcast_viewers(ticket_key)

    # ── Collision Engine: Active Viewers & Heartbeats ────────────────────────

    def record_heartbeat(self, ticket_id: str, user: User) -> None:
        """Record or refresh an agent's viewing lease on a ticket."""
        ticket_key = str(ticket_id)
        if ticket_key not in self._active_viewers:
            self._active_viewers[ticket_key] = {}

        self._active_viewers[ticket_key][user.id] = ViewerInfo(
            user_id=user.id,
            full_name=user.full_name,
            email=user.email,
            role=user.role.value,
            last_heartbeat=time.time(),
        )

    def get_active_viewers(self, ticket_id: str) -> list[dict[str, Any]]:
        """Return non-expired viewers currently inspecting the ticket."""
        ticket_key = str(ticket_id)
        now = time.time()
        viewers_map = self._active_viewers.get(ticket_key, {})

        # Clean expired heartbeats
        expired = [uid for uid, v in viewers_map.items() if now - v.last_heartbeat > VIEWER_HEARTBEAT_TTL_SECONDS]
        for uid in expired:
            del viewers_map[uid]

        return [v.to_dict() for v in viewers_map.values()]

    async def broadcast_viewers(self, ticket_id: str) -> None:
        """Broadcast the current list of viewing agents to all users in the ticket room."""
        ticket_key = str(ticket_id)
        viewers = self.get_active_viewers(ticket_key)
        await self.broadcast_to_ticket(
            ticket_key,
            event_type="AGENT_VIEWING",
            data={"ticket_id": ticket_key, "viewers": viewers},
        )

    # ── Broadcasting ─────────────────────────────────────────────────────────

    async def broadcast_to_ticket(
        self,
        ticket_id: str,
        event_type: str,
        data: dict[str, Any],
        exclude_ws: WebSocket | None = None,
    ) -> None:
        """Broadcast an event to all clients viewing a specific ticket."""
        ticket_key = str(ticket_id)

        # 1. Publish to Redis if available for horizontal scaling
        if self._redis_available and self._redis_client:
            try:
                channel = f"resolveai:ticket:{ticket_key}"
                payload = json.dumps({"type": event_type, "data": data})
                await self._redis_client.publish(channel, payload)
            except Exception as exc:
                logger.warning("redis_publish_failed_fallback_local", error=str(exc))

        # 2. Broadcast to local connected WebSockets on this node
        await self._local_broadcast_ticket(ticket_key, event_type, data, exclude_ws=exclude_ws)

    async def _local_broadcast_ticket(
        self,
        ticket_key: str,
        event_type: str,
        data: dict[str, Any],
        exclude_ws: WebSocket | None = None,
    ) -> None:
        """Dispatch JSON message directly to all local WebSockets for this ticket."""
        connections = self._ticket_connections.get(ticket_key, set())
        if not connections:
            return

        message_str = json.dumps({"type": event_type, "data": data})
        stale_connections = []

        for ws, user in connections:
            if exclude_ws and ws == exclude_ws:
                continue
            if ws.client_state != WebSocketState.CONNECTED:
                stale_connections.append((ws, user))
                continue
            try:
                await ws.send_text(message_str)
            except Exception as exc:
                logger.debug("websocket_send_failed", user_id=user.id, error=str(exc))
                stale_connections.append((ws, user))

        for stale_ws, stale_user in stale_connections:
            connections.discard((stale_ws, stale_user))

    async def broadcast_to_org(
        self,
        org_id: int,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Broadcast an event across all active users in an entire organization."""
        if self._redis_available and self._redis_client:
            try:
                channel = f"resolveai:org:{org_id}"
                payload = json.dumps({"type": event_type, "data": data})
                await self._redis_client.publish(channel, payload)
            except Exception:
                pass

        await self._local_broadcast_org(org_id, event_type, data)

    async def _local_broadcast_org(
        self,
        org_id: int,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        connections = self._org_connections.get(org_id, set())
        if not connections:
            return

        message_str = json.dumps({"type": event_type, "data": data})
        for ws, _ in list(connections):
            if ws.client_state == WebSocketState.CONNECTED:
                try:
                    await ws.send_text(message_str)
                except Exception:
                    pass


# Singleton ConnectionManager
ws_manager = ConnectionManager()
