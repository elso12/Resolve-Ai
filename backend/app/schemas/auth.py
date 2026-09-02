"""
ResolveAI — Authentication Schemas

Pydantic schemas for authentication API endpoints.
"""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import UserRole


# ── Requests ─────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    """Schema for user registration payload."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., min_length=8, description="User's password")
    full_name: str = Field(..., min_length=2, max_length=255, description="User's full name")
    organization_name: str = Field(default="Default Organization", min_length=2, max_length=255, description="Organization name")
    role: UserRole = Field(default=UserRole.CUSTOMER, description="User role")


class UserLogin(BaseModel):
    """Schema for user login payload."""
    email: EmailStr = Field(..., description="User's email address")
    password: str = Field(..., description="User's password")


# ── Responses ────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Schema for JWT token response."""
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    """Schema for returning user profile data. Never includes password hash."""
    id: int
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    organization_id: int
    
    model_config = ConfigDict(from_attributes=True)
