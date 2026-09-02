"""
ResolveAI — Authentication Test Suite

Tests user registration, validation rules, valid/invalid login, token generation, and /me profile.
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register_success(client: AsyncClient):
    """Test successful customer registration."""
    payload = {
        "email": "newuser@example.com",
        "password": "SecurePassword123",
        "full_name": "New User",
        "organization_name": "New Ventures Inc",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@example.com"
    assert data["full_name"] == "New User"
    assert data["role"] == "customer"
    assert "id" in data


@pytest.mark.asyncio
async def test_register_weak_password(client: AsyncClient):
    """Test registration failure on password without uppercase/numbers."""
    payload = {
        "email": "weak@example.com",
        "password": "password",
        "full_name": "Weak Password User",
        "organization_name": "Test Org",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "password" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_register_duplicate_email(client: AsyncClient, seed_data: dict):
    """Test that registering an existing email returns 400."""
    payload = {
        "email": seed_data["customer_a"].email,
        "password": "Password1234",
        "full_name": "Duplicate User",
        "organization_name": "Duplicate Org",
    }
    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 400
    assert "already exists" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_success(client: AsyncClient, seed_data: dict):
    """Test login with valid credentials returns a valid JWT."""
    payload = {
        "email": seed_data["customer_a"].email,
        "password": "password123",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, seed_data: dict):
    """Test login with incorrect password returns 401."""
    payload = {
        "email": seed_data["customer_a"].email,
        "password": "WrongPassword123",
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert "incorrect" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_get_me(customer_client: AsyncClient, seed_data: dict):
    """Test fetching profile for authenticated user via /auth/me."""
    response = await customer_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == seed_data["customer_a"].email
    assert data["role"] == "customer"
