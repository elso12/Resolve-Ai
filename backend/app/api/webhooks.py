"""
ResolveAI — Webhook Management API

Enables Support Managers and Administrators to register, inspect, test,
and delete external webhook integrations for outbound event notifications.
"""

from __future__ import annotations

import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User
from app.models.webhook import WebhookSubscription
from app.schemas.webhook import WebhookCreate, WebhookOut, WebhookTestResponse
from app.services.webhook_service import generate_secret_key, send_test_ping

logger = get_logger(__name__)

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post("", response_model=WebhookOut, status_code=status.HTTP_201_CREATED)
async def create_webhook(
    payload: WebhookCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookSubscription:
    """
    Register a new outbound webhook endpoint for the manager's organization.
    """
    secret = payload.secret_key or generate_secret_key()

    subscription = WebhookSubscription(
        organization_id=current_user.organization_id,
        target_url=payload.target_url,
        secret_key=secret,
        events=payload.events,
        is_active=payload.is_active,
    )
    db.add(subscription)
    await db.commit()
    await db.refresh(subscription)

    logger.info(
        "webhook_subscription_created",
        subscription_id=subscription.id,
        org_id=current_user.organization_id,
        target_url=subscription.target_url,
        events=subscription.events,
    )
    return subscription


@router.get("", response_model=list[WebhookOut])
async def list_webhooks(
    current_user: Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[WebhookSubscription]:
    """
    List all active and inactive webhook subscriptions for the manager's organization.
    """
    stmt = (
        select(WebhookSubscription)
        .where(WebhookSubscription.organization_id == current_user.organization_id)
        .order_by(WebhookSubscription.created_at.desc())
    )
    res = await db.execute(stmt)
    return list(res.scalars().all())


@router.get("/{id}", response_model=WebhookOut)
async def get_webhook(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookSubscription:
    """
    Retrieve a specific webhook subscription by ID for the manager's organization.
    """
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == id,
        WebhookSubscription.organization_id == current_user.organization_id,
    )
    res = await db.execute(stmt)
    subscription = res.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook subscription not found.",
        )
    return subscription


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_webhook(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """
    Delete a webhook subscription. Enforces strict organization isolation.
    """
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == id,
        WebhookSubscription.organization_id == current_user.organization_id,
    )
    res = await db.execute(stmt)
    subscription = res.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook subscription not found.",
        )

    await db.delete(subscription)
    await db.commit()
    logger.info("webhook_subscription_deleted", subscription_id=id)


@router.post("/{id}/test", response_model=WebhookTestResponse)
async def test_webhook_endpoint(
    id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WebhookTestResponse:
    """
    Dispatches a mock ping event to verify that the destination endpoint responds with 2xx.
    """
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.id == id,
        WebhookSubscription.organization_id == current_user.organization_id,
    )
    res = await db.execute(stmt)
    subscription = res.scalar_one_or_none()

    if not subscription:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook subscription not found.",
        )

    delivered, status_code, attempts, error = await send_test_ping(subscription)

    return WebhookTestResponse(
        delivered=delivered,
        status_code=status_code,
        attempts=attempts,
        error=error,
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )

