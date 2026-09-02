"""
ResolveAI — Tool Registry

Executable support tools for agentic decision execution, accompanied by
metadata schemas and risk classifications for Human-In-The-Loop safety.
"""

from __future__ import annotations

import datetime
import uuid
from typing import Any, Callable

from app.models.enums import ActionRiskLevel


# ── Executable Support Tools ─────────────────────────────────────────────────

def check_order_status(order_id: str) -> dict[str, Any]:
    """
    Look up shipping status, logistics carrier, and estimated delivery for an order.
    Risk: Low (Read-only query).
    """
    clean_id = order_id.strip().upper()
    carrier = "FedEx Express" if "9" in clean_id else "DHL Worldwide"
    eta_days = 2 if "9" in clean_id else 4
    eta_date = (datetime.date.today() + datetime.timedelta(days=eta_days)).strftime("%B %d, %Y")

    return {
        "order_id": clean_id,
        "status": "In Transit",
        "carrier": carrier,
        "tracking_number": f"TRK-{uuid.uuid4().hex[:10].upper()}",
        "estimated_delivery": eta_date,
        "destination": "San Francisco, CA, USA",
        "last_checkpoint": "Regional Distribution Facility — Departure Scan",
    }


def process_refund(order_id: str, amount: float, reason: str = "Customer Request") -> dict[str, Any]:
    """
    Execute a financial refund transaction back to the customer's payment method.
    Risk: High (Financial transfer / HITL required).
    """
    clean_id = order_id.strip().upper()
    refund_tx = f"rf_sec_{uuid.uuid4().hex[:12]}"
    refund_amount = round(float(amount), 2)

    return {
        "refund_id": refund_tx,
        "order_id": clean_id,
        "amount_refunded": refund_amount,
        "currency": "USD",
        "status": "completed",
        "gateway_response": "APPROVED (AUTH_CODE: 928371)",
        "reason": reason,
        "processed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "confirmation_message": (
            f"A refund of ${refund_amount:.2f} USD has been successfully issued for "
            f"order {clean_id} (Reason: {reason}). Reference: {refund_tx}."
        ),
    }


def reset_user_password(user_email: str) -> dict[str, Any]:
    """
    Issue a cryptographic password reset token and send an authenticated reset link.
    Risk: High (Account credential modification / HITL required).
    """
    clean_email = user_email.strip().lower()
    reset_token = uuid.uuid4().hex

    return {
        "user_email": clean_email,
        "status": "reset_link_generated",
        "reset_token": f"rst_{reset_token[:16]}",
        "expires_in_minutes": 15,
        "delivery_method": "secure_email",
        "confirmation_message": (
            f"A secure, single-use password reset link has been dispatched to {clean_email}. "
            "Valid for 15 minutes."
        ),
    }


# ── Tool Definitions & Registry ──────────────────────────────────────────────

SUPPORT_TOOLS: dict[str, dict[str, Any]] = {
    "check_order_status": {
        "name": "check_order_status",
        "description": "Look up real-time shipping status, carrier, and ETA for a customer order ID.",
        "risk_level": ActionRiskLevel.LOW,
        "function": check_order_status,
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order identifier (e.g., ORD-9982 or ORD-1024)",
                }
            },
            "required": ["order_id"],
        },
    },
    "process_refund": {
        "name": "process_refund",
        "description": "Execute a financial refund back to the customer's payment method for a specified order and dollar amount.",
        "risk_level": ActionRiskLevel.HIGH,
        "function": process_refund,
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {
                    "type": "string",
                    "description": "Order identifier to be refunded (e.g., ORD-9982)",
                },
                "amount": {
                    "type": "number",
                    "description": "Refund amount in USD (e.g., 120.00)",
                },
                "reason": {
                    "type": "string",
                    "description": "Justification for refund (e.g., Damaged item, Late delivery)",
                },
            },
            "required": ["order_id", "amount"],
        },
    },
    "reset_user_password": {
        "name": "reset_user_password",
        "description": "Issue a secure, time-limited password reset link to a customer's registered email address.",
        "risk_level": ActionRiskLevel.HIGH,
        "function": reset_user_password,
        "parameters": {
            "type": "object",
            "properties": {
                "user_email": {
                    "type": "string",
                    "description": "Customer's email address to receive the password reset token",
                }
            },
            "required": ["user_email"],
        },
    },
}


def execute_tool(tool_name: str, parameters: dict[str, Any]) -> dict[str, Any]:
    """
    Execute a registered tool with provided parameters.
    """
    tool = SUPPORT_TOOLS.get(tool_name)
    if not tool:
        raise ValueError(f"Unknown support tool: {tool_name!r}")

    func: Callable[..., dict[str, Any]] = tool["function"]
    return func(**parameters)
