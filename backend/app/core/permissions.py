"""
ResolveAI — Permissions & Access Control

FastAPI dependencies for resolving the current user from a JWT Bearer token
and enforcing Role-Based Access Control (RBAC).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db
from app.models.enums import UserRole
from app.models.user import User

logger = get_logger(__name__)

# FastAPI's built-in OAuth2 password bearer scheme
# It extracts the token from the "Authorization: Bearer <token>" header
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/auth/login",
    auto_error=False,  # We handle the error manually for standard JSON responses
)

# Exception raised when token is invalid or missing
CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    request: Request,
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """
    Extract the JWT from the Authorization header, verify it, and load
    the current user along with their organization and customer profile.
    """
    if not token:
        # Check for token in cookies or other headers if needed in the future
        raise CREDENTIALS_EXCEPTION

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id_str: str | None = payload.get("sub")
        if user_id_str is None:
            raise CREDENTIALS_EXCEPTION
            
        try:
            user_id = int(user_id_str)
        except ValueError:
            raise CREDENTIALS_EXCEPTION
            
    except JWTError:
        raise CREDENTIALS_EXCEPTION

    # Load user with related data using eager loading (selectinload)
    stmt = (
        select(User)
        .options(
            selectinload(User.organization),
            selectinload(User.customer_profile),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise CREDENTIALS_EXCEPTION
        
    if not user.is_active:
        logger.warning("inactive_user_login_attempt", user_id=user.id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User is inactive",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Bind user_id and org_id to the structured logging context
    import structlog
    structlog.contextvars.bind_contextvars(
        user_id=user.id,
        org_id=user.organization_id,
        role=user.role.value,
    )

    return user


def require_roles(*allowed_roles: UserRole) -> Callable[[User], User]:
    """
    Dependency factory to enforce RBAC.
    
    Returns a dependency that asserts the current user has one of the
    allowed roles. Returns HTTP 403 Forbidden with RFC 7807 format
    if the user lacks clearance.
    """
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role not in allowed_roles:
            logger.warning(
                "unauthorized_role_access",
                user_id=current_user.id,
                required_roles=[r.value for r in allowed_roles],
                actual_role=current_user.role.value,
            )
            # Standard RFC 7807 Problem Details format
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "type": "https://api.resolveai.com/errors/unauthorized",
                    "title": "Forbidden",
                    "status": status.HTTP_403_FORBIDDEN,
                    "detail": "You do not have permission to perform this action.",
                    "required_roles": [r.value for r in allowed_roles],
                }
            )
        return current_user
        
    return role_checker
