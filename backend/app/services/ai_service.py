"""
ResolveAI — AI Service with Observability & Telemetry

Handles interaction with Large Language Models for automated classification,
thread summarization, and reply drafting, wrapped with token, latency, and cost telemetry.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Literal

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import TicketCategory, TicketPriority
from app.services.ai_telemetry_service import log_ai_interaction

logger = get_logger(__name__)


class TicketClassification(BaseModel):
    """Structured output expected from the LLM for ticket classification."""
    predicted_category: TicketCategory = Field(
        ..., description="The category the ticket belongs to."
    )
    predicted_priority: TicketPriority = Field(
        ..., description="The predicted SLA-driven priority."
    )
    sentiment: Literal["positive", "neutral", "negative", "urgent"] = Field(
        ..., description="The customer's sentiment detected in the text."
    )
    urgency_score: int = Field(
        ..., ge=1, le=5, description="Score from 1-5 indicating urgency (5 is highest)."
    )
    key_entities: list[str] = Field(
        default_factory=list,
        description="Extracted key entities like dates, transaction IDs, or error codes.",
    )


# Initialise the AsyncOpenAI client wrapped with Instructor if key exists
if settings.OPENAI_API_KEY:
    client = instructor.from_openai(
        AsyncOpenAI(api_key=settings.OPENAI_API_KEY),
        mode=instructor.Mode.TOOLS
    )
else:
    client = None


def fallback_classify(subject: str, description: str) -> dict:
    """Deterministic rule-based fallback heuristic."""
    text = f"{subject} {description}".lower()
    
    classification = {
        "predicted_category": TicketCategory.GENERAL.value,
        "predicted_priority": TicketPriority.MEDIUM.value,
        "sentiment": "neutral",
        "urgency_score": 2,
        "key_entities": [],
    }

    if "bill" in text or "invoice" in text or "payment" in text or "charge" in text:
        classification["predicted_category"] = TicketCategory.BILLING.value
    elif "error" in text or "bug" in text or "crash" in text or "500" in text:
        classification["predicted_category"] = TicketCategory.TECHNICAL.value
    elif "password" in text or "login" in text or "account" in text:
        classification["predicted_category"] = TicketCategory.ACCOUNT.value

    if "urgent" in text or "asap" in text or "emergency" in text:
        classification["sentiment"] = "urgent"
        classification["urgency_score"] = 5
        classification["predicted_priority"] = TicketPriority.HIGH.value

    return classification


async def classify_and_triage(
    subject: str,
    description: str,
    organization_id: int = 1,
    ticket_id: int | None = None,
) -> dict:
    """
    Classify a ticket using an LLM, logged to AI Observability.
    Enforces a strict 3-second timeout and falls back to heuristics on failure.
    """
    t0 = time.perf_counter()
    prompt = f"Please classify the following support ticket:\nSubject: {subject}\nDescription: {description}"
    model_name = "gpt-3.5-turbo"

    if not client:
        result = fallback_classify(subject, description)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = 45
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="TRIAGE",
                model_name="mock-heuristic",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            result["interaction_id"] = interaction.id
        except Exception as tel_err:
            logger.warning("telemetry_logging_failed", error=str(tel_err))
        return result

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                response_model=TicketClassification,
                messages=[
                    {"role": "system", "content": "You are a customer support triage AI."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.0,
            ),
            timeout=3.0
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = 60
        result = {
            "predicted_category": response.predicted_category.value,
            "predicted_priority": response.predicted_priority.value,
            "sentiment": response.sentiment,
            "urgency_score": response.urgency_score,
            "key_entities": response.key_entities,
        }
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="TRIAGE",
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            result["interaction_id"] = interaction.id
        except Exception as tel_err:
            logger.warning("telemetry_logging_failed", error=str(tel_err))
        return result
    except Exception as e:
        logger.warning("ai_classification_fallback_on_error", error=str(e))
        result = fallback_classify(subject, description)
        latency_ms = (time.perf_counter() - t0) * 1000.0
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="TRIAGE",
                model_name="mock-heuristic",
                prompt_tokens=max(1, len(prompt) // 4),
                completion_tokens=40,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            result["interaction_id"] = interaction.id
        except Exception:
            pass
        return result


class ThreadSummary(BaseModel):
    core_issue: str = Field(..., description="The main issue the customer is experiencing")
    actions_taken: list[str] = Field(..., description="A list of actions taken so far by the agent or customer")
    pending_action: str = Field(..., description="What needs to happen next")


def fallback_summarize() -> dict:
    return {
        "core_issue": "Customer reported an issue (Fallback Summary).",
        "actions_taken": ["Reviewed ticket history."],
        "pending_action": "Agent needs to investigate and respond.",
    }


def fallback_suggest_reply() -> str:
    return "Hi there,\n\nThanks for reaching out! I'm currently looking into this issue for you and will get back to you with an update shortly.\n\nBest regards,\nSupport Team"


async def summarize_thread(
    messages: list[dict],
    organization_id: int = 1,
    ticket_id: int | None = None,
) -> dict:
    """Summarizes a ticket thread using the LLM with telemetry tracking."""
    t0 = time.perf_counter()
    prompt = f"Please summarize the following ticket conversation:\n\n{messages}"
    model_name = "gpt-3.5-turbo"

    if not client:
        result = fallback_summarize()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = 65
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="SUMMARY",
                model_name="mock-heuristic",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            result["interaction_id"] = interaction.id
        except Exception as tel_err:
            logger.warning("telemetry_logging_failed", error=str(tel_err))
        return result

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                response_model=ThreadSummary,
                messages=[
                    {"role": "system", "content": "You are a customer support AI assistant. Provide a concise summary of the thread."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=250,
                temperature=0.0,
            ),
            timeout=5.0
        )
        latency_ms = (time.perf_counter() - t0) * 1000.0
        result = response.model_dump()
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="SUMMARY",
                model_name=model_name,
                prompt_tokens=max(1, len(prompt) // 4),
                completion_tokens=max(1, len(str(result)) // 4),
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            result["interaction_id"] = interaction.id
        except Exception as tel_err:
            logger.warning("telemetry_logging_failed", error=str(tel_err))
        return result
    except Exception as e:
        logger.error("ai_summary_error", error=str(e))
        result = fallback_summarize()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="SUMMARY",
                model_name="mock-heuristic",
                prompt_tokens=max(1, len(prompt) // 4),
                completion_tokens=50,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            result["interaction_id"] = interaction.id
        except Exception:
            pass
        return result


class SuggestedReply(BaseModel):
    reply: str = Field(..., description="The AI-generated suggested reply")


async def suggest_reply(
    messages: list[dict],
    organization_id: int = 1,
    ticket_id: int | None = None,
) -> dict[str, Any]:
    """Generates a draft reply and logs token/cost metrics."""
    t0 = time.perf_counter()
    prompt = f"Draft a courteous, solution-oriented reply from the support agent to the customer based on this conversation:\n\n{messages}"
    model_name = "gpt-3.5-turbo"

    if not client:
        reply_text = fallback_suggest_reply()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(reply_text) // 4)
        interaction_id = None
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="SUGGESTED_REPLY",
                model_name="mock-heuristic",
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            interaction_id = interaction.id
        except Exception as tel_err:
            logger.warning("telemetry_logging_failed", error=str(tel_err))
        return {"reply": reply_text, "interaction_id": interaction_id}

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model_name,
                response_model=SuggestedReply,
                messages=[
                    {"role": "system", "content": "You are a helpful customer support agent drafting a reply to a customer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.7,
            ),
            timeout=5.0
        )
        reply_text = response.reply
        latency_ms = (time.perf_counter() - t0) * 1000.0
        prompt_tokens = max(1, len(prompt) // 4)
        completion_tokens = max(1, len(reply_text) // 4)
        interaction_id = None
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="SUGGESTED_REPLY",
                model_name=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            interaction_id = interaction.id
        except Exception as tel_err:
            logger.warning("telemetry_logging_failed", error=str(tel_err))
        return {"reply": reply_text, "interaction_id": interaction_id}
    except Exception as e:
        logger.error("ai_suggest_reply_error", error=str(e))
        reply_text = fallback_suggest_reply()
        latency_ms = (time.perf_counter() - t0) * 1000.0
        interaction_id = None
        try:
            interaction = await log_ai_interaction(
                organization_id=organization_id,
                interaction_type="SUGGESTED_REPLY",
                model_name="mock-heuristic",
                prompt_tokens=max(1, len(prompt) // 4),
                completion_tokens=40,
                latency_ms=latency_ms,
                ticket_id=ticket_id,
            )
            interaction_id = interaction.id
        except Exception:
            pass
        return {"reply": reply_text, "interaction_id": interaction_id}
