"""
ResolveAI — Development Database Seed Script
Seeds Organizations, Knowledge Articles, Demo Users, and Sample Tickets into the configured DATABASE_URL.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import get_password_hash
from app.models import (
    Customer,
    KnowledgeArticle,
    Organization,
    Ticket,
    TicketMessage,
    TicketPriority,
    TicketStatus,
    User,
    UserRole,
)

logger = get_logger(__name__)


DEMO_USERS = [
    ("agent@resolveai.dev", "Support Agent", UserRole.AGENT),
    ("customer@resolveai.dev", "Demo Customer", UserRole.CUSTOMER),
    ("manager@resolveai.dev", "Operations Manager", UserRole.MANAGER),
]

DEMO_ARTICLES = [
    {
        "title": "Understanding OAuth 2.0 and Authentication Architecture",
        "slug": "oauth-2-authentication-architecture",
        "category": "Security",
        "content": (
            "ResolveAI employs OAuth 2.0 with JWT access tokens for stateless session management. "
            "Access tokens carry the user's role (CUSTOMER, AGENT, MANAGER) and expire after 30 minutes. "
            "To refresh your session, submit your valid refresh token to POST /api/v1/auth/refresh. "
            "If you receive an ERR_AUTH_OAUTH_TIMEOUT error, verify that clock skew does not exceed 60 seconds."
        ),
    },
    {
        "title": "Troubleshooting General Login Errors and Session Timeouts",
        "slug": "troubleshooting-login-session-timeouts",
        "category": "Security",
        "content": (
            "When encountering login failures, first verify that cookies and local storage are enabled. "
            "If your session terminates unexpectedly during active use, check if your IP address has changed, "
            "as token validation strictly cross-references origin fingerprints for security compliance. "
            "For password resets, use the self-service flow at /forgot-password or contact support."
        ),
    },
    {
        "title": "OAuth Gateway Timeout Resolution",
        "slug": "oauth-gateway-timeout-resolution",
        "category": "Troubleshooting",
        "content": (
            "An HTTP 504 Gateway Timeout during authentication indicates high network latency between the reverse proxy "
            "and the FastAPI authentication worker pool. To remediate: 1) Verify Redis connection health, "
            "2) Ensure connection pooling limits are set to at least 20 connections per worker, "
            "and 3) Check that upstream DNS resolution times are below 50ms."
        ),
    },
    {
        "title": "Enterprise Subscription & Invoicing FAQ",
        "slug": "enterprise-subscription-invoicing-faq",
        "category": "Billing",
        "content": (
            "ResolveAI Enterprise plans include dedicated SLA escalation channels, custom ECA automation quotas, "
            "and priority vector retrieval. Invoices are generated on the 1st of each calendar month and sent via email. "
            "Refund requests for disputed charges exceeding $25.00 are automatically routed to our human review queue "
            "per our Human-In-The-Loop safety policies."
        ),
    },
]

DEMO_TICKETS = [
    {
        "ticket_number": "RSV-2026-E409ADBC",
        "subject": "Can I get a refund for order ORD-9982? The item arrived damaged.",
        "description": "Hi team, I received order ORD-9982 yesterday but the package was heavily damaged. Requesting a full refund of $89.99.",
        "status": TicketStatus.OPEN,
        "priority": TicketPriority.HIGH,
        "category": "billing",
    },
    {
        "ticket_number": "RSV-2026-AFAB0575",
        "subject": "Where is my order ORD-4521?",
        "description": "Ordered 3 days ago with expedited shipping. The tracking status has not updated from 'In Transit'.",
        "status": TicketStatus.IN_PROGRESS,
        "priority": TicketPriority.MEDIUM,
        "category": "general",
    },
    {
        "ticket_number": "RSV-2026-733956AD",
        "subject": "Checkout freeze on mobile Safari",
        "description": "Whenever I tap 'Complete Purchase' on iOS 17 Safari, the spinner spins indefinitely without completing.",
        "status": TicketStatus.ASSIGNED,
        "priority": TicketPriority.CRITICAL,
        "category": "technical",
    },
    {
        "ticket_number": "RSV-2026-0078B702",
        "subject": "Critical Server Down in EU Region",
        "description": "EU webhook ingestion endpoint is returning 502 Bad Gateway across all staging services.",
        "status": TicketStatus.RESOLVED,
        "priority": TicketPriority.CRITICAL,
        "category": "technical",
    },
]


async def seed_database() -> None:
    logger.info("seed_connecting_db", database_url=str(settings.DATABASE_URL).split("@")[-1])
    engine = create_async_engine(settings.async_database_url, echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        # 1. Organization
        stmt = select(Organization).where(Organization.id == 1)
        res = await session.execute(stmt)
        org = res.scalar_one_or_none()
        if not org:
            org = Organization(id=1, name="Resolve Retail", slug="resolve-retail")
            session.add(org)
            await session.commit()
            logger.info("seed_created_organization", name="Resolve Retail", org_id=1)
        else:
            logger.info("seed_organization_exists", name="Resolve Retail")

        # 2. Demo Users
        pwd_hash = get_password_hash("Password123!")
        created_users = {}
        for email, name, role in DEMO_USERS:
            stmt = select(User).where(User.email == email)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(
                    email=email,
                    full_name=name,
                    hashed_password=pwd_hash,
                    role=role,
                    is_active=True,
                    organization_id=1,
                )
                session.add(user)
                await session.flush()
                logger.info("seed_created_user", email=email, role=role.value)
            else:
                user.hashed_password = pwd_hash
                logger.info("seed_updated_user_password", email=email)
            created_users[role] = user

            if role == UserRole.CUSTOMER:
                stmt_c = select(Customer).where(Customer.user_id == user.id)
                res_c = await session.execute(stmt_c)
                cust_profile = res_c.scalar_one_or_none()
                if not cust_profile:
                    cust_profile = Customer(user_id=user.id, company_name="Acme Global", plan="Enterprise")
                    session.add(cust_profile)
                    await session.flush()
                    logger.info("seed_created_customer_profile", email=email)

        await session.commit()

        # Fetch customer profile for tickets
        cust_user = created_users[UserRole.CUSTOMER]
        agent_user = created_users[UserRole.AGENT]
        stmt_cust = select(Customer).where(Customer.user_id == cust_user.id)
        cust_profile = (await session.execute(stmt_cust)).scalar_one()

        # 3. Knowledge Articles
        for item in DEMO_ARTICLES:
            stmt = select(KnowledgeArticle).where(KnowledgeArticle.slug == item["slug"])
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                art = KnowledgeArticle(
                    title=item["title"],
                    slug=item["slug"],
                    category=item["category"],
                    content=item["content"],
                    is_published=True,
                    organization_id=1,
                )
                session.add(art)
                logger.info("seed_created_article", title=item["title"])
        await session.commit()

        # 4. Tickets

        for item in DEMO_TICKETS:
            stmt = select(Ticket).where(Ticket.ticket_number == item["ticket_number"])
            res = await session.execute(stmt)
            if not res.scalar_one_or_none():
                t = Ticket(
                    ticket_number=item["ticket_number"],
                    subject=item["subject"],
                    description=item["description"],
                    status=item["status"],
                    priority=item["priority"],
                    category=item["category"],
                    customer_id=cust_profile.id,
                    assigned_agent_id=agent_user.id if (agent_user and item["status"] != TicketStatus.OPEN) else None,
                    organization_id=1,
                )
                session.add(t)
                await session.flush()
                
                # Add initial customer message
                msg = TicketMessage(
                    ticket_id=t.id,
                    sender_id=cust_user.id if cust_user else 1,
                    body=item["description"],
                    is_internal=False,
                )
                session.add(msg)
                logger.info("seed_created_ticket", ticket_number=item["ticket_number"], subject=item["subject"])
        await session.commit()

    await engine.dispose()
    logger.info("seed_database_completed")


if __name__ == "__main__":
    asyncio.run(seed_database())
