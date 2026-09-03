"""
ResolveAI — Real-Time WebSocket API

Provides WebSocket endpoints for ticket rooms, enabling instant message streaming,
typing indicators, and agent collision detection.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.tickets import get_ticket_or_404, verify_ticket_access
from app.core.config import settings
from app.core.logging import get_logger
from app.core.websocket import ws_manager
from app.db.session import async_session_factory
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(tags=["WebSockets"])


async def authenticate_ws_user(token: str | None) -> User | None:
    """Validate JWT token passed in WebSocket query params and fetch user."""
    if not token:
        return None

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id_str = payload.get("sub")
        if user_id_str is None:
            return None
        user_id = int(user_id_str)
    except (JWTError, ValueError):
        return None

    async with async_session_factory() as db:
        stmt = (
            select(User)
            .options(
                selectinload(User.organization),
                selectinload(User.customer_profile),
            )
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user

    return None


@router.websocket("/ws/tickets/{ticket_id}")
async def ticket_websocket_endpoint(websocket: WebSocket, ticket_id: str) -> None:
    """
    WebSocket endpoint for real-time ticket room communication.

    Authenticates via `?token=<JWT>` query parameter.
    Clients receive:
      - `NEW_MESSAGE`
      - `TICKET_STATUS_UPDATED`
      - `AGENT_TYPING`
      - `AGENT_VIEWING` (Collision detection)
    Clients emit:
      - `{"type": "heartbeat"}`
      - `{"type": "typing", "is_typing": bool}`
    """
    token = websocket.query_params.get("token")
    user = await authenticate_ws_user(token)

    if not user:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication failed")
        return

    # Verify ticket access
    try:
        async with async_session_factory() as db:
            ticket = await get_ticket_or_404(ticket_id, db)
            verify_ticket_access(ticket, user)
            ticket_key = str(ticket.id)
    except Exception as exc:
        logger.warning("websocket_access_denied", ticket_id=ticket_id, user_id=user.id, error=str(exc))
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Access denied to ticket")
        return

    # Accept connection and register in manager
    await ws_manager.connect(websocket, ticket_key, user)

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except json.JSONDecodeError:
                continue

            msg_type = msg.get("type")

            if msg_type == "heartbeat":
                ws_manager.record_heartbeat(ticket_key, user)

            elif msg_type == "typing":
                is_typing = bool(msg.get("is_typing", False))
                await ws_manager.broadcast_to_ticket(
                    ticket_key,
                    event_type="AGENT_TYPING",
                    data={
                        "ticket_id": ticket_key,
                        "user_id": user.id,
                        "full_name": user.full_name,
                        "role": user.role.value,
                        "is_typing": is_typing,
                    },
                    exclude_ws=websocket,
                )

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        logger.debug("websocket_loop_exception", error=str(exc))
    finally:
        await ws_manager.disconnect(websocket, ticket_key, user)
