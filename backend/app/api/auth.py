"""
ResolveAI — Authentication Endpoints

Provides endpoints for user registration, login (token generation), and profile retrieval.
"""

from __future__ import annotations

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.logging import get_logger
from app.core.permissions import get_current_user
from app.core.security import create_access_token, get_password_hash, verify_password
from app.db.session import get_db
from app.models.customer import Customer
from app.models.enums import UserRole
from app.models.organization import Organization
from app.models.user import User
from app.schemas.auth import TokenResponse, UserLogin, UserOut, UserRegister

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Registration ─────────────────────────────────────────────────────────────

def validate_password_complexity(password: str) -> None:
    """Enforce minimum password complexity."""
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long",
        )
    if not re.search(r"[A-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one uppercase letter",
        )
    if not re.search(r"[a-z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one lowercase letter",
        )
    if not re.search(r"[0-9]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one number",
        )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def register(
    payload: UserRegister,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Register a new customer account.
    
    Creates the Organization, User, and Customer profile automatically.
    """
    validate_password_complexity(payload.password)

    # Check if user already exists
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    if result.scalar_one_or_none():
        logger.warning("registration_failed_email_exists", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email already exists.",
        )

    # Create Organization (using the provided name, creating a basic slug)
    # In a real app, you'd want robust slug generation to avoid collisions
    slug = re.sub(r'[^a-z0-9]+', '-', payload.organization_name.lower()).strip('-')
    
    # Check if slug exists to avoid IntegrityError
    org_stmt = select(Organization).where(Organization.slug == slug)
    org_result = await db.execute(org_stmt)
    if org_result.scalar_one_or_none():
        # Append random suffix if collision
        import uuid
        slug = f"{slug}-{str(uuid.uuid4())[:8]}"

    org = Organization(name=payload.organization_name, slug=slug)
    db.add(org)
    await db.flush()  # To get the org.id

    # Create User
    hashed_password = get_password_hash(payload.password)
    user = User(
        email=payload.email,
        hashed_password=hashed_password,
        full_name=payload.full_name,
        role=payload.role,
        is_active=True,
        organization_id=org.id,
    )
    db.add(user)
    await db.flush()  # To get the user.id

    # Auto-initialize Customer profile if customer
    if payload.role == UserRole.CUSTOMER:
        customer = Customer(
            user_id=user.id,
            plan="Free",
            company_name=payload.organization_name,
        )
        db.add(customer)
    
    # Let the transaction commit via the get_db dependency
    logger.info("user_registered", user_id=user.id, org_id=org.id, email=user.email)
    return user


# ── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
async def login(
    payload: UserLogin,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TokenResponse:
    """
    Authenticate a user and return a JWT access token.
    
    Protects against timing attacks by always evaluating the password hash,
    even if the user is not found.
    """
    stmt = select(User).where(User.email == payload.email)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    # Determine what to verify against if user is not found to prevent timing attacks
    # We use a dummy hash for a constant time delay
    dummy_hash = "$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjIQG8.FjG" # valid format, random
    
    # If user exists, use their hash, else use dummy hash
    hash_to_verify = user.hashed_password if user else dummy_hash
    
    is_valid = verify_password(payload.password, hash_to_verify)

    if not user or not is_valid:
        logger.warning("login_failed_invalid_credentials", email=payload.email)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning("login_failed_inactive_user", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=user.id,
        role=user.role,
        org_id=user.organization_id,
    )
    
    logger.info("user_logged_in", user_id=user.id, role=user.role.value)
    
    return TokenResponse(access_token=access_token, token_type="bearer")


# ── Profile ──────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserOut)
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Get the currently authenticated user's profile.
    """
    return current_user
