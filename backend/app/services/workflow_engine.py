"""
ResolveAI — Event-Condition-Action (ECA) Workflow Engine

Evaluates dynamic business rules and automations across ticket lifecycle events:
- TICKET_CREATED
- TICKET_STATUS_CHANGED
- SLA_BREACHED
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.automation import AutomationRule
from app.models.enums import TicketCategory, TicketPriority, TicketStatus
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage

logger = get_logger(__name__)


def evaluate_conditions(conditions: dict[str, Any], ticket: Ticket) -> bool:
    """
    Evaluates condition dictionary against ticket attributes.
    Returns True if ALL specified conditions evaluate to True.
    """
    if not conditions:
        return True

    # 1. Category check
    if "category" in conditions:
        expected_cat = str(conditions["category"]).strip().lower()
        current_cat = (
            ticket.category.value.lower()
            if isinstance(ticket.category, TicketCategory)
            else str(ticket.category).lower()
        )
        if expected_cat != current_cat:
            return False

    # 2. Priority check
    if "priority" in conditions:
        expected_prio = str(conditions["priority"]).strip().lower()
        current_prio = (
            ticket.priority.value.lower()
            if isinstance(ticket.priority, TicketPriority)
            else str(ticket.priority).lower()
        )
        if expected_prio != current_prio:
            return False

    # 3. Status check
    if "status" in conditions:
        expected_status = str(conditions["status"]).strip().lower()
        current_status = (
            ticket.status.value.lower()
            if isinstance(ticket.status, TicketStatus)
            else str(ticket.status).lower()
        )
        if expected_status != current_status:
            return False

    # 4. Subject contains keyword
    if "subject_contains" in conditions:
        keyword = str(conditions["subject_contains"]).strip().lower()
        if keyword not in (ticket.subject or "").lower():
            return False

    # 5. Description contains keyword
    if "description_contains" in conditions:
        keyword = str(conditions["description_contains"]).strip().lower()
        if keyword not in (ticket.description or "").lower():
            return False

    # 6. Customer plan check (VIP / Enterprise routing)
    if "customer_plan" in conditions:
        expected_plan = str(conditions["customer_plan"]).strip().lower()
        # If customer relationship loaded
        customer = getattr(ticket, "customer", None)
        cust_plan = getattr(customer, "plan", "").lower() if customer else ""
        if expected_plan not in cust_plan:
            return False

    return True


async def execute_actions(
    actions: dict[str, Any],
    ticket: Ticket,
    rule_name: str,
    db: AsyncSession,
) -> list[str]:
    """
    Executes automation actions sequentially on a ticket.
    Returns list of human-readable executed actions.
    """
    executed: list[str] = []

    # Action 1: Set Priority
    if "set_priority" in actions:
        target_prio = str(actions["set_priority"]).strip().upper()
        if target_prio in TicketPriority.__members__:
            ticket.priority = TicketPriority[target_prio]
            executed.append(f"set_priority({target_prio})")

    # Action 2: Set Status
    if "set_status" in actions:
        target_status = str(actions["set_status"]).strip().upper()
        if target_status in TicketStatus.__members__:
            ticket.status = TicketStatus[target_status]
            executed.append(f"set_status({target_status})")

    # Action 3: Assign Agent ID
    if "assign_agent_id" in actions:
        try:
            agent_id = int(actions["assign_agent_id"])
            ticket.assigned_agent_id = agent_id
            if ticket.status == TicketStatus.OPEN:
                ticket.status = TicketStatus.ASSIGNED
            executed.append(f"assign_agent_id({agent_id})")
        except (ValueError, TypeError):
            logger.warning("invalid_assign_agent_id_action", val=actions["assign_agent_id"])

    # Action 4: Add Internal Audit Note
    if "add_internal_note" in actions:
        note_body = str(actions["add_internal_note"]).strip()
        internal_note = TicketMessage(
            ticket_id=ticket.id,
            sender_id=ticket.assigned_agent_id or ticket.customer_id,
            body=f"⚡ Automation Rule [{rule_name}]: {note_body}",
            is_internal=True,
        )
        db.add(internal_note)
        executed.append(f"add_internal_note('{note_body}')")

    return executed


async def evaluate_rules(
    event: str,
    ticket: Ticket,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """
    Finds and triggers all active rules for the given event and ticket.
    Persists changes to the provided database session.
    """
    stmt = (
        select(AutomationRule)
        .where(
            AutomationRule.organization_id == ticket.organization_id,
            AutomationRule.event_trigger == event,
            AutomationRule.is_active.is_(True),
        )
        .order_by(AutomationRule.id.asc())
    )
    result = await db.execute(stmt)
    rules = list(result.scalars().all())

    execution_trail: list[dict[str, Any]] = []

    for rule in rules:
        try:
            matches = evaluate_conditions(rule.conditions, ticket)
            if not matches:
                continue

            actions_taken = await execute_actions(rule.actions, ticket, rule.name, db)
            if actions_taken:
                await db.flush()
                execution_trail.append({
                    "rule_id": rule.id,
                    "rule_name": rule.name,
                    "actions": actions_taken,
                })
                logger.info(
                    "automation_rule_executed",
                    rule_id=rule.id,
                    rule_name=rule.name,
                    event=event,
                    ticket_id=ticket.id,
                    actions=actions_taken,
                )
        except Exception as e:
            logger.error(
                "automation_rule_execution_error",
                rule_id=rule.id,
                rule_name=rule.name,
                error=str(e),
            )

    return execution_trail
