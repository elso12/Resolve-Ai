"""
ResolveAI — Agentic Decision & Tool-Calling Service

Analyzes incoming tickets and messages, matches them against the support tool
registry, and enforces Human-In-The-Loop (HITL) safety controls:
- Low-risk read actions execute autonomously, posting a bot message and updating status.
- High-risk write actions (refunds, credential resets) generate an ActionProposal
  in PENDING_APPROVAL status for agent review.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.action import ActionProposal
from app.models.enums import ActionRiskLevel, ActionStatus, TicketStatus
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage
from app.services.tools.tool_registry import (
    SUPPORT_TOOLS,
    execute_tool,
)

logger = get_logger(__name__)


def detect_tool_intent(text: str, default_email: str = "customer@example.com") -> tuple[str, dict[str, Any], ActionRiskLevel] | None:
    """
    Parse text to determine if a support tool should be invoked.
    Extracts tool name, parameters, and risk classification.
    """
    clean_text = text.lower()

    # 1. Check for Refund Intent (High Risk)
    if "refund" in clean_text or "money back" in clean_text or "damaged" in clean_text:
        order_match = re.search(r"ORD-?\d+", text, re.IGNORECASE)
        order_id = order_match.group(0).upper() if order_match else "ORD-9982"

        # Look for explicit currency amount like $50 or $120.00, otherwise standard default
        dollar_match = re.search(r"\$\s*(\d+(?:\.\d{1,2})?)", text)
        if dollar_match:
            amount = float(dollar_match.group(1))
        else:
            amount = 120.00

        reason = "Item arrived damaged" if "damaged" in clean_text else "Customer request"

        return (
            "process_refund",
            {
                "order_id": order_id,
                "amount": amount,
                "reason": reason,
            },
            ActionRiskLevel.HIGH,
        )

    # 2. Check for Password Reset Intent (High Risk)
    if "password" in clean_text and ("reset" in clean_text or "forgot" in clean_text or "locked" in clean_text):
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        email = email_match.group(0) if email_match else default_email

        return (
            "reset_user_password",
            {
                "user_email": email,
            },
            ActionRiskLevel.HIGH,
        )

    # 3. Check for Order Status Lookup Intent (Low Risk / Read-Only)
    if "order" in clean_text or "tracking" in clean_text or "where is" in clean_text or "shipping" in clean_text:
        order_match = re.search(r"ORD-?\d+", text, re.IGNORECASE)
        if order_match:
            return (
                "check_order_status",
                {
                    "order_id": order_match.group(0).upper(),
                },
                ActionRiskLevel.LOW,
            )

    return None


async def evaluate_and_process_ticket_actions(
    ticket: Ticket,
    db: AsyncSession,
    customer_email: str = "customer@example.com",
) -> ActionProposal | None:
    """
    Evaluate ticket text for actionable tool executions.
    - Low-risk: Executes autonomously, adds public message, transitions to WAITING_FOR_CUSTOMER.
    - High-risk: Generates ActionProposal in PENDING_APPROVAL state for agent review.
    """
    combined_text = f"{ticket.subject} {ticket.description}"
    intent = detect_tool_intent(combined_text, default_email=customer_email)

    if not intent:
        return None

    tool_name, parameters, risk_level = intent
    tool_meta = SUPPORT_TOOLS.get(tool_name)
    if not tool_meta:
        return None

    estimated_cost = float(parameters.get("amount", 0.0))

    if risk_level == ActionRiskLevel.LOW:
        # Autonomous Execution for safe read-only queries
        logger.info(
            "autonomous_tool_executing",
            ticket_id=ticket.id,
            tool=tool_name,
            parameters=parameters,
        )
        result = execute_tool(tool_name, parameters)

        # Create executed ActionProposal record
        proposal = ActionProposal(
            ticket_id=ticket.id,
            tool_name=tool_name,
            parameters=parameters,
            estimated_cost=0.0,
            status=ActionStatus.EXECUTED,
            risk_level=ActionRiskLevel.LOW,
            result=result,
        )
        db.add(proposal)

        # Post autonomous resolution message to thread
        if tool_name == "check_order_status":
            reply_text = (
                f"Hello! Here is the live status for order **{result['order_id']}**:\n\n"
                f"• **Status:** {result['status']}\n"
                f"• **Carrier:** {result['carrier']}\n"
                f"• **Tracking Number:** `{result['tracking_number']}`\n"
                f"• **Estimated Delivery:** {result['estimated_delivery']}\n"
                f"• **Latest Scan:** {result['last_checkpoint']}\n\n"
                "Please let us know if you need any additional assistance!"
            )
        else:
            reply_text = f"Action completed: {result.get('confirmation_message', 'Success')}"

        bot_message = TicketMessage(
            ticket_id=ticket.id,
            sender_id=ticket.assigned_agent_id or ticket.customer_id,
            body=reply_text,
            is_internal=False,
        )
        db.add(bot_message)

        # Auto-transition to WAITING_FOR_CUSTOMER
        ticket.status = TicketStatus.WAITING_FOR_CUSTOMER
        await db.flush()
        return proposal

    else:
        # High Risk: Require Human-In-The-Loop (HITL) approval
        logger.info(
            "hitl_action_proposal_created",
            ticket_id=ticket.id,
            tool=tool_name,
            parameters=parameters,
            cost=estimated_cost,
        )
        proposal = ActionProposal(
            ticket_id=ticket.id,
            tool_name=tool_name,
            parameters=parameters,
            estimated_cost=estimated_cost,
            status=ActionStatus.PENDING_APPROVAL,
            risk_level=ActionRiskLevel.HIGH,
            result=None,
        )
        db.add(proposal)

        # Add internal note documenting the pending proposal
        tool_display = tool_name.replace("_", " ").title()
        note_body = (
            f"🤖 [AI Action Proposal Pending Review]\n"
            f"Tool: {tool_display}\n"
            f"Parameters: {parameters}\n"
            f"Estimated Value: ${estimated_cost:.2f}\n"
            f"Agent review is required before this action can execute."
        )
        internal_note = TicketMessage(
            ticket_id=ticket.id,
            sender_id=ticket.assigned_agent_id or ticket.customer_id,
            body=note_body,
            is_internal=True,
        )
        db.add(internal_note)

        await db.flush()
        return proposal
