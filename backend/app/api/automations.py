"""
ResolveAI — Automation Rules Management API

Provides CRUD endpoints for ECA (Event-Condition-Action) workflow automations.
Restricted to Support Agents, Managers, and Admins.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.automation import AutomationRule
from app.models.enums import UserRole
from app.models.user import User
from app.schemas.automation import (
    AutomationRuleCreate,
    AutomationRuleOut,
    AutomationRuleUpdate,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/automations", tags=["Workflow Automations"])


@router.get("", response_model=list[AutomationRuleOut])
async def list_automation_rules(
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[AutomationRule]:
    """List all automation rules for the user's organization."""
    stmt = (
        select(AutomationRule)
        .where(AutomationRule.organization_id == current_user.organization_id)
        .order_by(desc(AutomationRule.created_at))
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("", response_model=AutomationRuleOut, status_code=status.HTTP_201_CREATED)
async def create_automation_rule(
    payload: AutomationRuleCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutomationRule:
    """Create a new ECA workflow automation rule."""
    rule = AutomationRule(
        name=payload.name,
        is_active=payload.is_active,
        event_trigger=payload.event_trigger.upper().strip(),
        conditions=payload.conditions,
        actions=payload.actions,
        organization_id=current_user.organization_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)

    logger.info(
        "automation_rule_created",
        rule_id=rule.id,
        name=rule.name,
        trigger=rule.event_trigger,
        user_id=current_user.id,
    )
    return rule


@router.get("/{rule_id}", response_model=AutomationRuleOut)
async def get_automation_rule(
    rule_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutomationRule:
    """Fetch details of a specific automation rule."""
    stmt = select(AutomationRule).where(
        AutomationRule.id == rule_id,
        AutomationRule.organization_id == current_user.organization_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )
    return rule


@router.patch("/{rule_id}", response_model=AutomationRuleOut)
async def update_automation_rule(
    rule_id: int,
    payload: AutomationRuleUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AutomationRule:
    """Update or toggle an automation rule."""
    stmt = select(AutomationRule).where(
        AutomationRule.id == rule_id,
        AutomationRule.organization_id == current_user.organization_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )

    if payload.name is not None:
        rule.name = payload.name
    if payload.is_active is not None:
        rule.is_active = payload.is_active
    if payload.event_trigger is not None:
        rule.event_trigger = payload.event_trigger.upper().strip()
    if payload.conditions is not None:
        rule.conditions = payload.conditions
    if payload.actions is not None:
        rule.actions = payload.actions

    await db.commit()
    await db.refresh(rule)

    logger.info("automation_rule_updated", rule_id=rule.id, active=rule.is_active)
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_automation_rule(
    rule_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    """Delete an automation rule."""
    stmt = select(AutomationRule).where(
        AutomationRule.id == rule_id,
        AutomationRule.organization_id == current_user.organization_id,
    )
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Automation rule not found",
        )

    await db.delete(rule)
    await db.commit()

    logger.info("automation_rule_deleted", rule_id=rule_id, user_id=current_user.id)
