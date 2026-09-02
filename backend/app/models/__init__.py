"""
ResolveAI — Model Registry

All ORM models are imported here so that:

1. Alembic's ``target_metadata = Base.metadata`` discovers every table.
2. Relationship back-references resolve correctly at mapper
   configuration time.
3. Application code can do ``from app.models import User, Ticket, ...``.
"""

from app.models.enums import (
    ActionRiskLevel,
    ActionStatus,
    TicketCategory,
    TicketPriority,
    TicketStatus,
    UserRole,
)
from app.models.organization import Organization
from app.models.user import User
from app.models.customer import Customer
from app.models.ticket import Ticket
from app.models.ticket_message import TicketMessage
from app.models.knowledge import KnowledgeArticle
from app.models.action import ActionProposal
from app.models.ai_telemetry import AIInteraction
from app.models.automation import AutomationRule

__all__: list[str] = [
    # Enums
    "UserRole",
    "TicketStatus",
    "TicketPriority",
    "TicketCategory",
    "ActionStatus",
    "ActionRiskLevel",
    # Models
    "Organization",
    "User",
    "Customer",
    "Ticket",
    "TicketMessage",
    "KnowledgeArticle",
    "ActionProposal",
    "AIInteraction",
    "AutomationRule",
]
