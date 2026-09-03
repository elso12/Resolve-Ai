"""
ResolveAI — Action Proposal & HITL Approval Endpoints

Provides REST API routes for listing, approving, and rejecting agentic
tool action proposals associated with support tickets.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.tickets import get_ticket_or_404, verify_ticket_access
from app.core.logging import get_logger
from app.core.permissions import get_current_user, require_roles
from app.db.session import get_db
from app.models.action import ActionProposal
from app.models.enums import ActionStatus, UserRole
from app.models.ticket_message import TicketMessage
from app.models.user import User
from app.schemas.action import ActionApprovalResponse, ActionProposalOut
from app.services.tools.tool_registry import execute_tool
from app.services.webhook_service import dispatch_webhook_event

logger = get_logger(__name__)

router = APIRouter(prefix="/tickets/{ticket_id}/actions", tags=["Agentic Actions"])


@router.get("", response_model=list[ActionProposalOut])
async def list_ticket_actions(
    ticket_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[ActionProposal]:
    """
    List all automated action proposals for a given ticket.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    stmt = (
        select(ActionProposal)
        .where(ActionProposal.ticket_id == ticket.id)
        .order_by(ActionProposal.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/{action_id}/approve", response_model=ActionApprovalResponse)
async def approve_action_proposal(
    ticket_id: str,
    action_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionApprovalResponse:
    """
    Human-In-The-Loop approval: An authorized agent approves and executes
    a pending tool action proposal.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    stmt = select(ActionProposal).where(
        ActionProposal.id == action_id,
        ActionProposal.ticket_id == ticket.id,
    )
    result = await db.execute(stmt)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal not found for this ticket.",
        )

    if proposal.status != ActionStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve action with current status: {proposal.status.value}",
        )

    # 1. Execute the tool
    try:
        execution_result = execute_tool(proposal.tool_name, proposal.parameters)
    except Exception as exc:
        logger.exception("tool_execution_failed", tool=proposal.tool_name, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tool execution failed: {str(exc)}",
        )

    # 2. Update proposal record
    proposal.status = ActionStatus.EXECUTED
    proposal.result = execution_result

    # 3. Post public confirmation reply to ticket thread
    confirmation_text = execution_result.get(
        "confirmation_message",
        f"The requested action '{proposal.tool_name}' has been executed successfully."
    )
    thread_reply = (
        f"✅ **Action Executed by Support:**\n\n"
        f"{confirmation_text}\n\n"
        f"Authorized by Support Specialist {current_user.full_name}."
    )
    bot_message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        body=thread_reply,
        is_internal=False,
    )
    db.add(bot_message)

    await db.flush()
    await db.refresh(proposal)

    logger.info(
        "hitl_action_approved_and_executed",
        action_id=proposal.id,
        ticket_id=ticket.id,
        tool=proposal.tool_name,
        agent_id=current_user.id,
    )

    # Dispatch outbound webhook to external integrations
    try:
        await dispatch_webhook_event(
            event_type="ACTION_APPROVED",
            data={
                "action_id": proposal.id,
                "ticket_id": ticket.id,
                "ticket_number": ticket.ticket_number,
                "tool_name": proposal.tool_name,
                "parameters": proposal.parameters,
                "execution_result": execution_result,
                "approved_by_id": current_user.id,
                "approved_by_name": current_user.full_name,
            },
            organization_id=ticket.organization_id,
            session=db,
        )
    except Exception as hook_err:
        logger.warning("webhook_dispatch_error", error=str(hook_err))

    return ActionApprovalResponse(
        proposal=ActionProposalOut.model_validate(proposal),
        execution_result=execution_result,
        confirmation_message=confirmation_text,
    )


@router.post("/{action_id}/reject", response_model=ActionApprovalResponse)
async def reject_action_proposal(
    ticket_id: str,
    action_id: int,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ActionApprovalResponse:
    """
    Human-In-The-Loop rejection: An authorized agent rejects and dismisses
    a pending tool action proposal.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    stmt = select(ActionProposal).where(
        ActionProposal.id == action_id,
        ActionProposal.ticket_id == ticket.id,
    )
    result = await db.execute(stmt)
    proposal = result.scalar_one_or_none()

    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal not found for this ticket.",
        )

    if proposal.status != ActionStatus.PENDING_APPROVAL:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot reject action with status: {proposal.status.value}",
        )

    # 1. Update proposal record
    proposal.status = ActionStatus.REJECTED

    # 2. Add an internal note documenting the rejection
    rejection_note = (
        f"❌ **Action Proposal Dismissed:**\n"
        f"Proposal for '{proposal.tool_name}' was reviewed and rejected by {current_user.full_name}."
    )
    internal_note = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        body=rejection_note,
        is_internal=True,
    )
    db.add(internal_note)

    await db.flush()
    await db.refresh(proposal)

    logger.info(
        "hitl_action_rejected",
        action_id=proposal.id,
        ticket_id=ticket.id,
        tool=proposal.tool_name,
        agent_id=current_user.id,
    )

    return ActionApprovalResponse(
        proposal=ActionProposalOut.model_validate(proposal),
        execution_result=None,
        confirmation_message="Action proposal rejected and dismissed.",
    )
