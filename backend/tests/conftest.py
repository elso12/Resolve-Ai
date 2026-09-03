"""
ResolveAI — Pytest Configuration & Test Fixtures

Provides isolated SQLite in-memory async database sessions, HTTPX AsyncClient fixtures,
and pre-authenticated user clients (Customer A, Customer B, Agent, Manager/Admin).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.ext.compiler import compiles

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Customer, Organization, User, UserRole


# ── SQLite Compatibility Compilers for Postgres Types ─────────────────────────
@compiles(Vector, "sqlite")
def compile_vector_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    return "TEXT"


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(type_: Any, compiler: Any, **kw: Any) -> str:
    return "TEXT"


# ── In-Memory Async Database Engine ───────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine: AsyncEngine = create_async_engine(
    TEST_DATABASE_URL,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Creates fresh schema in SQLite in-memory DB per test and tears it down afterward.
    """
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def seed_data(db_session: AsyncSession) -> dict[str, Any]:
    """
    Seeds organization, customers, agent, and manager users for RBAC & IDOR testing.
    """
    # 1. Organization
    org = Organization(name="Acme Corp", slug="acme-corp")
    db_session.add(org)
    await db_session.flush()

    # 2. Customer A
    user_cust_a = User(
        email="alice@acme.com",
        hashed_password=get_password_hash("password123"),
        full_name="Alice Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(user_cust_a)
    await db_session.flush()

    profile_a = Customer(
        user_id=user_cust_a.id,
        company_name="Acme Corp",
        plan="Pro",
    )
    db_session.add(profile_a)

    # 3. Customer B (for IDOR tests)
    user_cust_b = User(
        email="bob@acme.com",
        hashed_password=get_password_hash("password123"),
        full_name="Bob Customer",
        role=UserRole.CUSTOMER,
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(user_cust_b)
    await db_session.flush()

    profile_b = Customer(
        user_id=user_cust_b.id,
        company_name="Beta Corp",
        plan="Basic",
    )
    db_session.add(profile_b)

    # 4. Support Agent
    user_agent = User(
        email="agent@acme.com",
        hashed_password=get_password_hash("password123"),
        full_name="Sarah Agent",
        role=UserRole.AGENT,
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(user_agent)

    # 5. Support Manager / Admin
    user_manager = User(
        email="manager@acme.com",
        hashed_password=get_password_hash("password123"),
        full_name="Marcus Manager",
        role=UserRole.MANAGER,
        is_active=True,
        organization_id=org.id,
    )
    db_session.add(user_manager)

    await db_session.commit()
    await db_session.refresh(user_cust_a)
    await db_session.refresh(user_cust_b)
    await db_session.refresh(user_agent)
    await db_session.refresh(user_manager)

    return {
        "org": org,
        "customer_a": user_cust_a,
        "customer_b": user_cust_b,
        "agent": user_agent,
        "manager": user_manager,
    }


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    HTTPX AsyncClient configured with FastAPI app and database dependency override.
    """
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def customer_client(db_session: AsyncSession, seed_data: dict[str, Any]) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated independent client for Customer A."""
    user = seed_data["customer_a"]
    token = create_access_token(subject=user.id, role=user.role, org_id=user.organization_id)
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def customer_b_client(db_session: AsyncSession, seed_data: dict[str, Any]) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated independent client for Customer B (IDOR testing)."""
    user = seed_data["customer_b"]
    token = create_access_token(subject=user.id, role=user.role, org_id=user.organization_id)
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def agent_client(db_session: AsyncSession, seed_data: dict[str, Any]) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated independent client for Support Agent."""
    user = seed_data["agent"]
    token = create_access_token(subject=user.id, role=user.role, org_id=user.organization_id)
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture(scope="function")
async def manager_client(db_session: AsyncSession, seed_data: dict[str, Any]) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated independent client for Support Manager / Admin."""
    user = seed_data["manager"]
    token = create_access_token(subject=user.id, role=user.role, org_id=user.organization_id)
    
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test", headers={"Authorization": f"Bearer {token}"}) as ac:
        yield ac

    app.dependency_overrides.clear()
