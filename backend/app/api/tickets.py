"""
ResolveAI — Ticket Endpoints

REST API endpoints for ticket management, threaded messages, and internal notes.
Implements strict IDOR protections and RBAC data isolation.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.permissions import get_current_user, require_roles
from app.db.session import get_db
from app.models.enums import TicketCategory, TicketPriority, TicketStatus, UserRole
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage
from app.models.user import User
from app.schemas.ticket import (
    MessageCreate,
    MessageOut,
    TicketAssign,
    TicketCreate,
    TicketDetailOut,
    TicketOut,
    TicketStatusUpdate,
)
from app.services.ticket_service import generate_ticket_number, validate_transition
from app.services.ai_service import classify_and_triage
from app.services.sla_service import (
    calculate_sla_due_dates,
    evaluate_active_ticket_sla,
    record_first_response,
    record_resolution,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/tickets", tags=["Tickets"])


# ── Dependency Helpers ───────────────────────────────────────────────────────

async def get_ticket_or_404(
    ticket_id: int | str,
    db: AsyncSession,
) -> Ticket:
    """Fetch ticket by numeric ID or ticket_number or return 404."""
    if isinstance(ticket_id, int) or (isinstance(ticket_id, str) and ticket_id.isdigit()):
        stmt = select(Ticket).where(Ticket.id == int(ticket_id))
    else:
        stmt = select(Ticket).where(Ticket.ticket_number == str(ticket_id))
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()
    
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ticket not found",
        )
    return ticket


def verify_ticket_access(ticket: Ticket, user: User) -> None:
    """
    Enforce IDOR protection: ensure the user has clearance to access this ticket.
    """
    # 1. Organization boundary check (hard tenant boundary)
    if ticket.organization_id != user.organization_id:
        logger.warning(
            "idor_attempt_cross_org",
            user_id=user.id,
            ticket_id=ticket.id,
            user_org=user.organization_id,
            ticket_org=ticket.organization_id,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    # 2. Customer IDOR check (Customer can only see their own tickets)
    if user.role == UserRole.CUSTOMER:
        # A customer must have a customer profile
        if not user.customer_profile or ticket.customer_id != user.customer_profile.id:
            logger.warning(
                "idor_attempt_cross_customer",
                user_id=user.id,
                ticket_id=ticket.id,
            )
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")


# ── Ticket Endpoints ─────────────────────────────────────────────────────────

@router.post("", response_model=TicketOut, status_code=status.HTTP_201_CREATED)
async def create_ticket(
    payload: TicketCreate,
    current_user: Annotated[User, Depends(require_roles(UserRole.CUSTOMER))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Ticket:
    """
    Create a new support ticket.
    
    Only Customers can open tickets. The ticket is bound to their organization
    and customer profile, starting in the OPEN state.
    """
    if not current_user.customer_profile:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active customer profile.",
        )

    ticket_number = generate_ticket_number()

    # 1. AI Classification & Triage
    ai_classification = await classify_and_triage(payload.subject, payload.description)
    
    # 2. Extract classified attributes or fallback to user input
    category = TicketCategory(ai_classification["predicted_category"])
    priority = TicketPriority(ai_classification["predicted_priority"])

    if ai_classification["urgency_score"] >= 4 or ai_classification["sentiment"] == "urgent":
        priority = TicketPriority.HIGH
        
    if ai_classification["urgency_score"] == 5:
        priority = TicketPriority.CRITICAL

    # 3. Compute SLA Due Dates
    first_resp_due, res_due = calculate_sla_due_dates(priority)

    ticket = Ticket(
        ticket_number=ticket_number,
        subject=payload.subject,
        description=payload.description,
        priority=priority,
        category=category,
        customer_id=current_user.customer_profile.id,
        organization_id=current_user.organization_id,
        ai_metadata=ai_classification,
        first_response_due_at=first_resp_due,
        resolution_due_at=res_due,
        # status defaults to OPEN per SQLAlchemy model definition
    )
    
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)
    
    logger.info(
        "ticket_created",
        ticket_number=ticket_number,
        user_id=current_user.id,
        ai_category=ai_classification["predicted_category"],
        ai_priority=ai_classification["predicted_priority"],
    )
    
    return ticket


@router.get("", response_model=list[TicketOut])
async def list_tickets(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: TicketStatus | None = Query(None, alias="status"),
    priority_filter: TicketPriority | None = Query(None, alias="priority"),
    category_filter: TicketCategory | None = Query(None, alias="category"),
) -> list[Ticket]:
    """
    List tickets with strict role-based data isolation.
    """
    stmt = select(Ticket)

    # 1. Organization boundary (ALL queries scoped to org)
    stmt = stmt.where(Ticket.organization_id == current_user.organization_id)

    # 2. Role-based data isolation
    if current_user.role == UserRole.CUSTOMER:
        if not current_user.customer_profile:
            return [] # Safety net
        # Customer: Only their own tickets
        stmt = stmt.where(Ticket.customer_id == current_user.customer_profile.id)
    
    elif current_user.role == UserRole.AGENT:
        # Agent: Assigned to them OR (Unassigned AND Open)
        stmt = stmt.where(
            or_(
                Ticket.assigned_agent_id == current_user.id,
                and_(
                    Ticket.assigned_agent_id.is_(None),
                    Ticket.status == TicketStatus.OPEN
                )
            )
        )
    
    # Manager/Admin see all within the org scope applied above

    # 3. Optional filters
    if status_filter:
        stmt = stmt.where(Ticket.status == status_filter)
    if priority_filter:
        stmt = stmt.where(Ticket.priority == priority_filter)
    if category_filter:
        stmt = stmt.where(Ticket.category == category_filter)

    # 4. Pagination & ordering
    stmt = stmt.order_by(Ticket.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(stmt)
    tickets = list(result.scalars().all())
    for t in tickets:
        evaluate_active_ticket_sla(t)
    return tickets


@router.get("/{ticket_id}", response_model=TicketDetailOut)
async def get_ticket(
    ticket_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Ticket:
    """
    Get ticket details including message thread.
    Enforces strict IDOR checks.
    """
    # Fetch ticket and eager load messages (with sender for UI convenience)
    query = (
        select(Ticket)
        .options(
            selectinload(Ticket.messages).selectinload(TicketMessage.sender)
        )
    )
    if ticket_id.isdigit():
        stmt = query.where(Ticket.id == int(ticket_id))
    else:
        stmt = query.where(Ticket.ticket_number == ticket_id)
    result = await db.execute(stmt)
    ticket = result.scalar_one_or_none()

    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")

    verify_ticket_access(ticket, current_user)
    evaluate_active_ticket_sla(ticket)

    # Filter out internal notes if caller is a customer
    if current_user.role == UserRole.CUSTOMER:
        ticket.messages = [m for m in ticket.messages if not m.is_internal]

    return ticket


@router.patch("/{ticket_id}/status", response_model=TicketOut)
async def update_ticket_status(
    ticket_id: str,
    payload: TicketStatusUpdate,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Ticket:
    """
    Update a ticket's status using the strict Finite State Machine.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    # State Machine validation
    validate_transition(ticket.status, payload.status)

    ticket.status = payload.status
    
    # SLA Resolution Tracking
    if payload.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        record_resolution(ticket)
    
    logger.info(
        "ticket_status_updated",
        ticket_id=ticket.id,
        new_status=payload.status.value,
        user_id=current_user.id,
    )
    
    return ticket


@router.post("/{ticket_id}/assign", response_model=TicketOut)
async def assign_ticket(
    ticket_id: str,
    payload: TicketAssign,
    current_user: Annotated[User, Depends(require_roles(UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN))],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Ticket:
    """
    Assign a ticket to an agent within the same organization.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    # Validate target agent exists and belongs to the same org
    stmt = select(User).where(User.id == payload.agent_id)
    result = await db.execute(stmt)
    target_agent = result.scalar_one_or_none()

    if not target_agent or target_agent.organization_id != ticket.organization_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid agent assignment",
        )
        
    if target_agent.role not in (UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Target user is not an agent",
        )

    # Policy: Agents can self-assign unassigned open tickets, but cannot assign to others
    if current_user.role == UserRole.AGENT:
        if payload.agent_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Agents can only self-assign tickets",
            )
        if ticket.assigned_agent_id is not None:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot steal an already assigned ticket",
            )

    ticket.assigned_agent_id = payload.agent_id
    
    # Auto-transition to ASSIGNED if currently OPEN
    if ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.ASSIGNED

    logger.info(
        "ticket_assigned",
        ticket_id=ticket.id,
        agent_id=payload.agent_id,
        user_id=current_user.id,
    )
    
    return ticket


# ── Message Endpoints ────────────────────────────────────────────────────────

@router.post("/{ticket_id}/messages", response_model=MessageOut, status_code=status.HTTP_201_CREATED)
async def add_message(
    ticket_id: str,
    payload: MessageCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TicketMessage:
    """
    Add a message or internal note to a ticket thread.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    # Prevent customers from posting internal notes
    if payload.is_internal and current_user.role == UserRole.CUSTOMER:
        logger.warning("customer_attempted_internal_note", user_id=current_user.id)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Customers cannot post internal notes.",
        )
        
    # Prevent replying to closed tickets
    if ticket.status == TicketStatus.CLOSED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot reply to a closed ticket.",
        )

    message = TicketMessage(
        ticket_id=ticket.id,
        sender_id=current_user.id,
        body=payload.body,
        is_internal=payload.is_internal,
    )
    db.add(message)
    await db.flush() # Needed to fetch sender data if returning it
    
    # Eager load the sender for the response model
    await db.refresh(message, ["sender"])
    
    # SLA First Response Milestone Tracking (by agent on non-internal messages)
    if not payload.is_internal and current_user.role in (UserRole.AGENT, UserRole.MANAGER, UserRole.ADMIN):
        record_first_response(ticket)

    # Auto-state transitions based on who is replying
    if not payload.is_internal:
        if current_user.role == UserRole.CUSTOMER:
            if ticket.status in (TicketStatus.WAITING_FOR_CUSTOMER, TicketStatus.RESOLVED):
                ticket.status = TicketStatus.IN_PROGRESS
        else:
            if ticket.status in (TicketStatus.OPEN, TicketStatus.ASSIGNED, TicketStatus.IN_PROGRESS):
                 ticket.status = TicketStatus.WAITING_FOR_CUSTOMER

    logger.info(
        "message_added",
        ticket_id=ticket.id,
        message_id=message.id,
        is_internal=payload.is_internal,
        user_id=current_user.id,
    )

    return message


@router.get("/{ticket_id}/messages", response_model=list[MessageOut])
async def list_messages(
    ticket_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[TicketMessage]:
    """
    List messages for a ticket thread.
    """
    ticket = await get_ticket_or_404(ticket_id, db)
    verify_ticket_access(ticket, current_user)

    stmt = (
        select(TicketMessage)
        .options(selectinload(TicketMessage.sender))
        .where(TicketMessage.ticket_id == ticket.id)
        .order_by(TicketMessage.created_at.asc())
    )
    
    # Filter out internal notes for customers at the query level
    if current_user.role == UserRole.CUSTOMER:
        stmt = stmt.where(TicketMessage.is_internal == False)

    result = await db.execute(stmt)
    return list(result.scalars().all())
