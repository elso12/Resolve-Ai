"""
ResolveAI — AI Endpoints

Exposes AI Copilot endpoints for summarization and reply suggestion.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.permissions import require_roles
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.ticket import Ticket
from app.models.user import User
from app.schemas.ai import SuggestedReplyOut, ThreadSummaryOut
from app.services.ai_service import suggest_reply, summarize_thread

logger = get_logger(__name__)

router = APIRouter(prefix="/ai/tickets", tags=["AI Copilot"])


async def get_ticket_messages_for_ai(ticket_id: int | str, user: User, db: AsyncSession) -> list[dict]:
    """Helper to fetch a ticket and its messages, enforcing access control."""
    query = (
        select(Ticket)
        .options(selectinload(Ticket.messages))
    )
    if isinstance(ticket_id, int) or (isinstance(ticket_id, str) and ticket_id.isdigit()):
        stmt = query.where(Ticket.id == int(ticket_id))
    else:
        stmt = query.where(Ticket.ticket_number == str(ticket_id))
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    if ticket.organization_id != user.organization_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # Format conversation history for AI
    conversation = []
    # Include the initial ticket description
    conversation.append({
        "sender": "CUSTOMER",
        "message": ticket.description
    })
    
    # Sort messages chronologically and format
    sorted_messages = sorted(ticket.messages, key=lambda m: m.created_at)
    for msg in sorted_messages:
        # For simplicity, we just label by whether it's an internal note or agent/customer reply.
        # Ideally, we'd load the sender to accurately label Agent vs Customer.
        role = "SYSTEM_INTERNAL" if msg.is_internal else "USER"
        # Since we didn't eager load sender, we'll just differentiate internal vs public
        # In a real app we'd load `msg.sender.role`
        conversation.append({
            "sender": role,
            "message": msg.body
        })

    return conversation, ticket


@router.post("/{ticket_id}/summarize", response_model=ThreadSummaryOut)
async def summarize_ticket_thread(
    ticket_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Summarize the entire conversation history of a ticket."""
    conversation, ticket = await get_ticket_messages_for_ai(ticket_id, current_user, db)
    
    logger.info("ai_summarize_request", ticket_id=ticket_id, user_id=current_user.id)
    summary = await summarize_thread(
        conversation,
        organization_id=current_user.organization_id,
        ticket_id=ticket.id,
    )
    
    return summary


@router.post("/{ticket_id}/suggest-reply", response_model=SuggestedReplyOut)
async def suggest_ticket_reply(
    ticket_id: str,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Generate a context-aware suggested reply based on the ticket history."""
    conversation, ticket = await get_ticket_messages_for_ai(ticket_id, current_user, db)
    
    logger.info("ai_suggest_reply_request", ticket_id=ticket_id, user_id=current_user.id)
    reply_data = await suggest_reply(
        conversation,
        organization_id=current_user.organization_id,
        ticket_id=ticket.id,
    )
    
    return reply_data
