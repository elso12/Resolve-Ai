"""
ResolveAI — Enterprise Outbound Webhook Dispatcher Verification Script

Simulates end-to-end integration:
1. Manager registers an outbound webhook subscription with an HMAC secret key.
2. Customer creates a support ticket.
3. System dispatches an outbound webhook HTTP POST request.
4. Script intercepts and cryptographically verifies the HMAC SHA-256 signature header.
5. Manager sends a mock test ping probe.
6. Manager deletes the webhook subscription.
"""

import asyncio
import hashlib
import hmac
import json
import sys
from typing import Any

import httpx
from httpx import ASGITransport, AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

import logging

# Mute noisy internal DB debug logs during standalone verification
logging.getLogger("aiosqlite").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.enums import TicketCategory, TicketPriority, UserRole
from app.models.organization import Organization
from app.models.customer import Customer
from app.models.user import User
from tests.conftest import test_engine, TestSessionLocal


async def run_verification() -> bool:
    print("=" * 80)
    print(" ResolveAI — Enterprise Outbound Webhook Dispatcher Verification")
    print("=" * 80)

    # 1. Setup in-memory SQLite schema
    print("\n[1/6] Initializing test database schema...")
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Dependency override to use TestSessionLocal for DB operations
    async def override_get_db():
        async with TestSessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    # 2. Seed Org, Manager, and Customer
    print("[2/6] Seeding test organization, manager, and customer...")
    async with TestSessionLocal() as db:
        org = Organization(name="Acme Global Technologies", slug="acme-global")
        db.add(org)
        await db.flush()

        manager = User(
            email="manager@acme.com",
            hashed_password=get_password_hash("password123"),
            full_name="Sarah Jenkins (Support Manager)",
            role=UserRole.MANAGER,
            is_active=True,
            organization_id=org.id,
        )
        db.add(manager)

        cust_user = User(
            email="customer@client.com",
            hashed_password=get_password_hash("password123"),
            full_name="Alex Chen (Enterprise Customer)",
            role=UserRole.CUSTOMER,
            is_active=True,
            organization_id=org.id,
        )
        db.add(cust_user)
        await db.flush()

        customer_profile = Customer(
            user_id=cust_user.id,
            company_name="Client Corp",
            plan="Enterprise",
        )
        db.add(customer_profile)
        await db.commit()

        org_id = org.id
        manager_id = manager.id
        customer_id = cust_user.id

    manager_token = create_access_token(manager_id, UserRole.MANAGER, org_id)
    customer_token = create_access_token(customer_id, UserRole.CUSTOMER, org_id)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        manager_headers = {"Authorization": f"Bearer {manager_token}"}
        customer_headers = {"Authorization": f"Bearer {customer_token}"}

        # 3. Manager registers an outbound webhook
        print("\n[3/6] Registering outbound webhook subscription via POST /api/v1/webhooks...")
        secret_key = "whsec_prod_crm_integration_token_99998888"
        target_url = "https://hooks.slack.com/services/T00000000/B00000000/XXXX"
        webhook_create_payload = {
            "target_url": target_url,
            "events": ["TICKET_CREATED", "SLA_BREACHED", "ACTION_APPROVED"],
            "secret_key": secret_key,
            "is_active": True,
        }

        resp = await client.post("/api/v1/webhooks", json=webhook_create_payload, headers=manager_headers)
        if resp.status_code != 201:
            print(f"FAILED: Expected HTTP 201, got {resp.status_code}: {resp.text}")
            return False

        webhook_data = resp.json()
        webhook_id = webhook_data["id"]
        print(f"       Created Webhook ID: {webhook_id}")
        print(f"       Target URL:        {webhook_data['target_url']}")
        print(f"       Subscribed Events: {webhook_data['events']}")
        print(f"       Status:            Active ({webhook_data['is_active']})")

        # 4. Intercept outbound HTTP requests and trigger ticket creation
        print("\n[4/6] Triggering ticket creation event and intercepting outbound payload...")
        captured_webhook: dict[str, Any] = {}
        orig_post = httpx.AsyncClient.post

        async def capture_outbound_post(self, url, *args, **kwargs):
            url_str = str(url)
            if "hooks.slack.com" in url_str:
                captured_webhook["url"] = url_str
                captured_webhook["content"] = kwargs.get("content", b"")
                captured_webhook["headers"] = kwargs.get("headers", {})
                return Response(200, json={"ok": True})
            return await orig_post(self, url, *args, **kwargs)

        from unittest.mock import patch
        with patch.object(httpx.AsyncClient, "post", new=capture_outbound_post):
            ticket_create_payload = {
                "subject": "CRITICAL: Database connection pool exhausted",
                "description": "Production API instances reporting HTTP 500 on all queries.",
                "category": "technical",
                "priority": "critical",
            }
            ticket_resp = await client.post(
                "/api/v1/tickets",
                json=ticket_create_payload,
                headers=customer_headers,
            )
            if ticket_resp.status_code != 201:
                print(f"FAILED: Ticket creation failed: {ticket_resp.status_code} {ticket_resp.text}")
                return False

            ticket_info = ticket_resp.json()
            print(f"       Ticket Created: RSV-{ticket_info['id']} | Subject: {ticket_info['subject']}")

            # Allow background dispatch tasks to execute
            await asyncio.sleep(0.3)

        if not captured_webhook:
            print("FAILED: No outbound webhook POST was captured!")
            return False

        print("\n[5/6] Verifying Outbound Webhook cryptographic signature & envelope...")
        print(f"       Target Destination: {captured_webhook['url']}")
        headers = captured_webhook["headers"]
        print(f"       Header X-ResolveAI-Event:    {headers.get('X-ResolveAI-Event')}")
        print(f"       Header X-ResolveAI-Delivery: {headers.get('X-ResolveAI-Delivery')}")
        print(f"       Header X-Signature-SHA256:   {headers.get('X-Signature-SHA256')}")

        raw_payload_bytes = captured_webhook["content"]
        payload_json = json.loads(raw_payload_bytes.decode("utf-8"))
        print(f"       Payload Event:   {payload_json.get('event')}")
        print(f"       Payload Ticket:  {payload_json.get('data', {}).get('subject')}")

        # Compute HMAC-SHA256 locally
        expected_sig = hmac.new(secret_key.encode("utf-8"), raw_payload_bytes, hashlib.sha256).hexdigest()
        actual_sig = headers.get("X-Signature-SHA256")

        print(f"       Computed HMAC:   {expected_sig}")
        print(f"       Header HMAC:     {actual_sig}")

        if actual_sig != expected_sig:
            print("FAILED: Cryptographic signature mismatch!")
            return False
        print("       >>> SIGNATURE VERIFICATION: SUCCESSFUL (Exact match) <<<")

        # 6. Test Ping & Clean Up
        print("\n[6/6] Testing mock ping probe & webhook teardown...")
        with patch("app.api.webhooks.send_test_ping", return_value=(True, 200, 1, None)):
            test_resp = await client.post(f"/api/v1/webhooks/{webhook_id}/test", headers=manager_headers)
            if test_resp.status_code != 200:
                print(f"FAILED: Test ping failed with status {test_resp.status_code}")
                return False
            print(f"       Ping Probe Result: {test_resp.json()}")

        del_resp = await client.delete(f"/api/v1/webhooks/{webhook_id}", headers=manager_headers)
        if del_resp.status_code != 204:
            print(f"FAILED: Webhook delete failed with status {del_resp.status_code}")
            return False
        print(f"       Webhook {webhook_id} deleted successfully (HTTP 204).")

    print("\n" + "=" * 80)
    print(" ALL VERIFICATIONS PASSED: Enterprise Outbound Webhook Dispatcher is operational!")
    print("=" * 80)
    return True


if __name__ == "__main__":
    success = asyncio.run(run_verification())
    sys.exit(0 if success else 1)
