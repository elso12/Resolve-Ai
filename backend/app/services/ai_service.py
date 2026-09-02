"""
ResolveAI — AI Service

Handles interaction with Large Language Models for automated classification
and triage using instructor for strictly validated JSON outputs.
"""
import asyncio
from typing import Literal

import instructor
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.models.enums import TicketCategory, TicketPriority

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


async def classify_and_triage(subject: str, description: str) -> dict:
    """
    Classify a ticket using an LLM. Returns a dictionary of AI metadata.
    Enforces a strict 3-second timeout and falls back to heuristics on failure.
    """
    if not client:
        logger.info("ai_classification_fallback", reason="No OPENAI_API_KEY")
        return fallback_classify(subject, description)

    prompt = f"""
    Please classify the following support ticket:
    Subject: {subject}
    Description: {description}
    """

    try:
        # Wrap the LLM call in a strict timeout
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
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
        logger.info("ai_classification_success")
        # Ensure we return primitive types/enums that are JSON serialisable
        return {
            "predicted_category": response.predicted_category.value,
            "predicted_priority": response.predicted_priority.value,
            "sentiment": response.sentiment,
            "urgency_score": response.urgency_score,
            "key_entities": response.key_entities,
        }
    except asyncio.TimeoutError:
        logger.warning("ai_classification_timeout", duration=3.0)
        return fallback_classify(subject, description)
    except Exception as e:
        logger.error("ai_classification_error", error=str(e))
        return fallback_classify(subject, description)


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


async def summarize_thread(messages: list[dict]) -> dict:
    """Summarizes a ticket thread using the LLM."""
    if not client:
        return fallback_summarize()

    prompt = f"Please summarize the following ticket conversation:\n\n{messages}"

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
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
        return response.model_dump()
    except Exception as e:
        logger.error("ai_summary_error", error=str(e))
        return fallback_summarize()


class SuggestedReply(BaseModel):
    reply: str = Field(..., description="The AI-generated suggested reply")


async def suggest_reply(messages: list[dict]) -> str:
    """Generates a courteous, solution-oriented draft reply."""
    if not client:
        return fallback_suggest_reply()

    prompt = f"Draft a courteous, solution-oriented reply from the support agent to the customer based on this conversation:\n\n{messages}"

    try:
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model="gpt-3.5-turbo",
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
        return response.reply
    except Exception as e:
        logger.error("ai_suggest_reply_error", error=str(e))
        return fallback_suggest_reply()
