"""
ResolveAI — AI Service & Fallback Heuristic Test Suite
"""

import pytest
from app.models.enums import TicketCategory, TicketPriority
from app.services.ai_service import (
    classify_and_triage,
    fallback_classify,
    fallback_suggest_reply,
    fallback_summarize,
)


def test_fallback_classify_billing():
    """Verify billing keyword classification."""
    res = fallback_classify("Invoice payment issue", "My credit card was charged twice on the bill.")
    assert res["predicted_category"] == TicketCategory.BILLING.value
    assert res["predicted_priority"] in (TicketPriority.MEDIUM.value, TicketPriority.HIGH.value)


def test_fallback_classify_technical():
    """Verify technical error classification."""
    res = fallback_classify("500 Server Error", "The app is crashing when calling webhook endpoint.")
    assert res["predicted_category"] == TicketCategory.TECHNICAL.value


def test_fallback_classify_urgent_escalation():
    """Verify urgent sentiment and priority escalation."""
    res = fallback_classify("Urgent server downtime", "Production is down ASAP emergency!!")
    assert res["sentiment"] == "urgent"
    assert res["urgency_score"] == 5
    assert res["predicted_priority"] == TicketPriority.HIGH.value


def test_fallback_summarize_structure():
    """Verify fallback summary contains required keys."""
    summary = fallback_summarize()
    assert "core_issue" in summary
    assert "actions_taken" in summary
    assert "pending_action" in summary
    assert isinstance(summary["actions_taken"], list)


def test_fallback_suggest_reply():
    """Verify fallback reply text is present and courteous."""
    reply = fallback_suggest_reply()
    assert len(reply) > 20
    assert "reaching out" in reply.lower() or "support team" in reply.lower()


@pytest.mark.asyncio
async def test_classify_and_triage_resilience():
    """Verify classify_and_triage executes safely without throwing exceptions."""
    res = await classify_and_triage("Password reset", "Cannot login to account.")
    assert "predicted_category" in res
    assert "predicted_priority" in res
    assert "urgency_score" in res
