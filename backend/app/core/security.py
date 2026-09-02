"""
ResolveAI — Security & Cryptography

Handles password hashing, constant-time verification, and JWT creation.
Uses passlib with bcrypt for password storage.
"""

from __future__ import annotations

import datetime
from typing import Any

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.models.enums import UserRole

# ── Password Hashing ─────────────────────────────────────────────────────────

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plaintext password against a hash in constant time.
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a password using bcrypt.
    """
    return pwd_context.hash(password)


# ── JWT Tokens ───────────────────────────────────────────────────────────────

def create_access_token(
    subject: str | int,
    role: UserRole,
    org_id: int,
    expires_delta: datetime.timedelta | None = None,
) -> str:
    """
    Create a JWT access token.
    
    Includes claims:
      - sub: user_id
      - role: UserRole
      - org_id: organization_id
      - exp: Expiration time
      - iat: Issued at time
      - nbf: Not before time
    """
    now = datetime.datetime.now(datetime.timezone.utc)
    
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + datetime.timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        
    to_encode: dict[str, Any] = {
        "sub": str(subject),
        "role": role.value,
        "org_id": org_id,
        "exp": expire,
        "iat": now,
        "nbf": now,
    }
    
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.SECRET_KEY, 
        algorithm=settings.ALGORITHM
    )
    return encoded_jwt
