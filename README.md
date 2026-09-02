<div align="center">

# ⚡ ResolveAI
### Enterprise AI Customer Support & Operations Operating System

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7-3178C6?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![pgvector](https://img.shields.io/badge/pgvector-0.8-336791)](https://github.com/pgvector/pgvector)
[![Pytest](https://img.shields.io/badge/Pytest-26%2F26%20Passed-brightgreen?logo=pytest&logoColor=white)](https://docs.pytest.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

<p align="center">
  A production-grade, full-stack AI Customer Support Operating System combining <strong>Zendesk/Intercom-grade human workflows</strong> with <strong>agentic tool execution, hybrid RAG search, real-time collision detection, and autonomous SLA breach escalation</strong>.
</p>

</div>

---

## 📑 Table of Contents
1. [Executive Overview](#-executive-overview)
2. [System Architecture](#-system-architecture)
3. [Core Technical Innovations](#-core-technical-innovations)
4. [Enterprise Feature Matrix](#-enterprise-feature-matrix)
5. [API Reference & Schema Specification](#-api-reference--schema-specification)
6. [Local Quickstart & Development](#-local-quickstart--development)
7. [Automated Testing & Verification](#-automated-testing--verification)
8. [License](#-license)

---

## 🎯 Executive Overview

Modern customer support operations face high ticket volumes, escalating SLA breach risks, and fragmented support tooling. Traditional ticketing platforms require agents to perform repetitive lookups, write formulaic replies, and manually track SLA deadlines.

**ResolveAI** is an AI-augmented customer support operating system designed from first principles:
- **Sub-100ms API Response Times:** All heavy AI classification, tool reasoning, and vector indexing operations run non-blockingly via an asynchronous background task queue.
- **Human-In-The-Loop (HITL) Safety:** Low-risk actions (order tracking, ticket tagging) execute autonomously; high-risk actions (refunds > $25, account password resets) generate staged proposals requiring explicit agent review.
- **Enterprise Hybrid Search:** Combines dense semantic vectors (`pgvector` cosine similarity) with sparse lexical search (`tsvector` BM25 full-text search) fused using Reciprocal Rank Fusion (RRF, $k = 60$).
- **Agent Collision Prevention:** Real-time WebSockets with 30-second presence heartbeats alert agents when colleagues are viewing or drafting replies on the same ticket.

---

## 🏗️ System Architecture

```mermaid
flowchart TD
    subgraph ClientLayer["Frontend Application (React 19 + TypeScript + Vite)"]
        CustomerPortal["Customer Portal<br/>- My Tickets<br/>- Help Center RAG<br/>- Live Thread"]
        AgentInbox["3-Pane Agent Inbox<br/>- Queue Filter Pane<br/>- Live Feed Pane<br/>- Workspace & Copilot Drawer"]
        ManagerDashboard["Manager Analytics & Automations<br/>- SLA & Inflow Trends<br/>- AI Observability & Telemetry<br/>- ECA Rule Builder"]
    end

    subgraph APILayer["FastAPI Asynchronous Gateway (Python 3.11+)"]
        AuthMiddleware["JWT Auth & Multi-Role RBAC<br/>(Customer, Agent, Manager, Admin)"]
        FSMValidation["Ticket State Machine Engine<br/>(OPEN ➔ ASSIGNED ➔ IN_PROGRESS ➔ WAITING ➔ RESOLVED ➔ CLOSED)"]
        RESTEndpoints["RESTful API Endpoints<br/>/auth, /tickets, /knowledge, /ai, /analytics, /automations"]
        WSManager["WebSocket Connection Manager<br/>(Heartbeats, Typing, Collision Alerts)"]
    end

    subgraph ServiceLayer["Core Backend Engines"]
        WorkflowEngine["ECA Workflow Engine<br/>(WHEN [Event] AND [Condition] THEN [Action])"]
        SLADaemon["SLA Monitoring Daemon<br/>(60s Evaluation, Auto-Escalation, Priority Boost)"]
        HITLEngine["Agentic Tool Calling & HITL<br/>(Low-Risk Auto-Exec / High-Risk Approval)"]
        HybridSearch["Hybrid Retrieval Engine<br/>(pgvector Dense + PostgreSQL FTS + RRF)"]
        AIObservability["AI Telemetry & Cost Engine<br/>(Tokens, Latency, USD Pricing, Human Evals)"]
    end

    subgraph DataLayer["Storage & Vector Infrastructure"]
        PostgresDB[("PostgreSQL 16 Engine<br/>SQLAlchemy 2.0 Async + JSONB")]
        VectorStore[("pgvector Extension<br/>HNSW Cosine Vector Indexing")]
        LexicalFTS[("PostgreSQL tsvector<br/>GIN English Text Search")]
    end

    subgraph AIProviders["LLM & Embedding Services"]
        LLM["OpenAI / Instructor / Local LLM<br/>Structured JSON Outputs"]
        Embeddings["text-embedding-3-small<br/>1536-dim Embeddings"]
    end

    CustomerPortal <-->|HTTPS / REST| RESTEndpoints
    AgentInbox <-->|HTTPS / REST| RESTEndpoints
    AgentInbox <-->|WebSockets| WSManager
    ManagerDashboard <-->|HTTPS / REST| RESTEndpoints

    RESTEndpoints --> AuthMiddleware --> FSMValidation
    FSMValidation --> PostgresDB

    RESTEndpoints --> WorkflowEngine
    RESTEndpoints --> HITLEngine
    RESTEndpoints --> HybridSearch
    RESTEndpoints --> AIObservability

    SLADaemon --> PostgresDB
    SLADaemon --> WSManager
    WorkflowEngine --> PostgresDB

    HITLEngine <--> LLM
    AIObservability <--> LLM
    HybridSearch <--> VectorStore
    HybridSearch <--> LexicalFTS
    HybridSearch <--> Embeddings
```

---

## 🔬 Core Technical Innovations

### 1. Enterprise Hybrid Search & Reciprocal Rank Fusion (RRF)
Unlike naive vector-only RAG systems that struggle with exact error codes (`ERR_AUTH_OAUTH_TIMEOUT`) or product model numbers, ResolveAI executes dual-channel retrieval:
1. **Dense Semantic Search:** `pgvector` evaluates cosine distance ($\Leftrightarrow$) over 1536-dimensional embeddings.
2. **Sparse Lexical Search:** PostgreSQL `ts_rank` evaluates full-text BM25 matching on English `tsvector` columns indexed with GIN.
3. **Reciprocal Rank Fusion:** Combines ranks with $k=60$:
$$\text{RRF Score}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{k + \text{rank}_m(d)}$$

### 2. Human-In-The-Loop (HITL) Agentic Engine
Automated support actions are classified by blast radius:
- **Low-Risk Tools:** `check_order_status` autonomously executes, attaches real-time courier tracking, transitions status to `WAITING_FOR_CUSTOMER`, and replies directly to the customer.
- **High-Risk Tools:** `process_refund` (amounts > $25) or `reset_user_password` stage an `ActionProposal` in `PENDING` state with full parameter inspection. Support agents can approve or reject with one click from the workspace drawer.

### 3. Real-Time WebSockets & Agent Collision Detection
- Agents subscribe to ticket-specific rooms (`/ws/tickets/{ticket_id}`) and organization-wide broadcast rooms.
- In-memory presence heartbeats track active viewers with a 30-second TTL.
- When multiple agents open ticket #142 simultaneously, the UI presents an active collision banner: *"⚠️ Agent Sarah is currently viewing this ticket"* to prevent duplicate replies.

### 4. Asynchronous Task Queue & SLA Escalation Daemon
- Client endpoints return in `< 100ms` by offloading AI triage and vector embedding generation to non-blocking `BackgroundTasks`.
- A 60-second periodic background daemon continuously audits active tickets (`OPEN`, `ASSIGNED`, `IN_PROGRESS`). Overdue tickets automatically:
  - Set `sla_breached = True`.
  - Upgrade priority to **`CRITICAL`**.
  - Append an automated internal audit note.
  - Broadcast an `SLA_BREACH_ALERT` WebSocket event to team managers.

### 5. Event-Condition-Action (ECA) Workflow Engine
Support managers build custom automation rules:
- **Triggers:** `TICKET_CREATED`, `TICKET_STATUS_CHANGED`, `SLA_BREACHED`.
- **Conditions:** JSON matching on `category`, `priority`, `status`, `subject_contains`, `customer_plan`.
- **Actions:** `set_priority`, `set_status`, `assign_agent_id`, `add_internal_note`.

---

## 💎 Enterprise Feature Matrix

| Feature Area | Implementation Details |
| :--- | :--- |
| **Authentication & RBAC** | JWT (HS256) with strict multi-role authorization (`Customer`, `Agent`, `Manager`, `Admin`) and IDOR data isolation. |
| **State Machine (FSM)** | Finite State Machine with explicit validation preventing invalid transitions (e.g. `RESOLVED` directly to `ASSIGNED`). |
| **Agent Workspace** | 3-pane layout: Queue pane (dynamic counts), Feed pane (sorting, urgency indicators), Workspace pane (thread, internal notes, Customer 360). |
| **AI Copilot** | Thread summarization, context-aware suggested reply drafting, urgency scoring, and entity extraction. |
| **AI Observability** | Real-time token tracking (prompt & completion), runtime latency (ms), USD cost accounting, and human evaluation tracking (acceptance rate %). |
| **Customer Portal** | Self-service help center, grounded RAG instant answer widget, live message thread composer, and ticket tracking. |

---

## 📡 API Reference & Schema Specification

All endpoints are versioned under `/api/v1`. Interactive OpenAPI documentation is available at `http://localhost:8000/api/v1/docs`.

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Public | Register new customer or agent account. |
| `POST` | `/api/v1/auth/login` | Public | Authenticate user and issue JWT bearer token. |
| `GET` | `/api/v1/tickets` | Authenticated | List tickets with scoping (customers see own; agents see org). |
| `POST` | `/api/v1/tickets` | Customer | Create support ticket (< 100ms response with SLA computation). |
| `GET` | `/api/v1/tickets/{id}` | Authenticated | Fetch full ticket conversation history and SLA status. |
| `PATCH` | `/api/v1/tickets/{id}/status` | Agent / Admin | Transition ticket status validated against FSM. |
| `POST` | `/api/v1/tickets/{id}/messages` | Authenticated | Append public customer reply or internal agent note. |
| `GET` | `/api/v1/tickets/{id}/actions` | Agent / Admin | Fetch HITL agentic tool proposals for ticket. |
| `POST` | `/api/v1/tickets/{id}/actions/{action_id}/approve` | Agent / Admin | Approve and execute staged high-risk action. |
| `POST` | `/api/v1/ai/tickets/{id}/suggest-reply` | Agent / Admin | Generate AI Copilot suggested response. |
| `POST` | `/api/v1/ai/tickets/{id}/summarize` | Agent / Admin | Summarize full multi-party ticket conversation. |
| `GET` | `/api/v1/knowledge/search` | Authenticated | Query knowledge base via Hybrid Search (pgvector + FTS + RRF). |
| `POST` | `/api/v1/knowledge/ask` | Public / Auth | Grounded RAG question answering with exact source citations. |
| `GET` | `/api/v1/analytics/overview` | Manager / Admin | Query SLA compliance, MTTA, MTTR, and volume trends. |
| `GET` | `/api/v1/analytics/ai` | Manager / Admin | AI Observability telemetry (USD spend, tokens, latency, acceptance %). |
| `POST` | `/api/v1/analytics/sla/check-now` | Agent / Admin | On-demand trigger for SLA breach monitoring daemon. |
| `GET` | `/api/v1/automations` | Manager / Admin | List ECA workflow automation rules. |
| `POST` | `/api/v1/automations` | Manager / Admin | Create new dynamic workflow rule. |
| `WS` | `/api/v1/ws/tickets/{ticket_id}` | Authenticated | Real-time WebSocket connection for collisions and messages. |

---

## 🚀 Local Quickstart & Development

### Prerequisites
- **Python 3.11+**
- **Node.js 20+** & **npm**
- **Docker & Docker Compose** (Optional for PostgreSQL + pgvector)

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ResolveAI.git
cd ResolveAI/resolveai
```

### 2. Start PostgreSQL with pgvector via Docker
```bash
docker compose up -d postgres
```
*(Alternatively, ResolveAI fully supports local development using SQLite out of the box via `sqlite+aiosqlite:///./local_dev.db`)*.

### 3. Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env

# Run database table initialization and migrations
python migrate_db.py

# Launch FastAPI development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 4. Frontend Setup
```bash
cd ../frontend

# Install dependencies
npm install

# Configure environment variables
cp .env.example .env

# Launch Vite development server
npm run dev
```

Visit **`http://localhost:5173`** in your browser to access the application:
- Customer Portal: `http://localhost:5173/help`
- Agent Operations Inbox: `http://localhost:5173/agent/inbox`
- Manager Analytics: `http://localhost:5173/agent/analytics`
- Workflow Automations: `http://localhost:5173/agent/automations`

---

## 🧪 Automated Testing & Verification

ResolveAI includes an exhaustive test suite covering authentication, RBAC boundaries, state machine validation, SLA calculations, and AI triage fallbacks.

### Run Backend Pytest Suite
```bash
cd backend
pytest -v
```

Expected output:
```text
============================== test session starts ==============================
collected 26 items

tests/test_ai_service.py::test_fallback_classify_billing PASSED           [  3%]
tests/test_ai_service.py::test_fallback_classify_technical PASSED         [  7%]
tests/test_ai_service.py::test_fallback_classify_urgent_escalation PASSED  [ 11%]
tests/test_ai_service.py::test_fallback_summarize_structure PASSED        [ 15%]
tests/test_ai_service.py::test_fallback_suggest_reply PASSED              [ 19%]
tests/test_ai_service.py::test_classify_and_triage_resilience PASSED      [ 23%]
tests/test_auth.py::test_register_success PASSED                          [ 26%]
tests/test_auth.py::test_register_weak_password PASSED                    [ 30%]
tests/test_auth.py::test_register_duplicate_email PASSED                  [ 34%]
tests/test_auth.py::test_login_success PASSED                             [ 38%]
tests/test_auth.py::test_login_invalid_password PASSED                    [ 42%]
tests/test_auth.py::test_get_me PASSED                                    [ 46%]
tests/test_rbac.py::test_customer_cannot_access_analytics PASSED          [ 50%]
tests/test_rbac.py::test_customer_cannot_update_ticket_status PASSED      [ 53%]
tests/test_rbac.py::test_customer_cannot_assign_tickets PASSED            [ 57%]
tests/test_rbac.py::test_customer_cannot_publish_knowledge_articles PASSED  [ 61%]
tests/test_rbac.py::test_agent_can_access_analytics_and_articles PASSED   [ 65%]
tests/test_sla.py::test_sla_policy_tier_targets PASSED                    [ 69%]
tests/test_sla.py::test_calculate_sla_due_dates PASSED                    [ 73%]
tests/test_sla.py::test_record_first_response_on_time_and_breach PASSED   [ 76%]
tests/test_sla.py::test_record_resolution_breach PASSED                   [ 80%]
tests/test_tickets.py::test_create_ticket_success PASSED                  [ 84%]
tests/test_tickets.py::test_idor_protection_cross_customer PASSED         [ 88%]
tests/test_tickets.py::test_fsm_valid_state_transitions PASSED            [ 92%]
tests/test_tickets.py::test_fsm_invalid_state_transition_fails PASSED     [ 96%]
tests/test_tickets.py::test_customer_cannot_post_internal_notes PASSED    [100%]

======================== 26 passed in 102.87s (0:01:42) ========================
```

### Run Frontend Production Build & Typecheck
```bash
cd frontend
npm run build
```

Expected output:
```text
✓ 1899 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.45 kB │ gzip:   0.29 kB
dist/assets/index-DZBRxPWL.css   47.23 kB │ gzip:   8.37 kB
dist/assets/index-Biw-Vxx0.js   422.08 kB │ gzip: 122.05 kB
✓ built in 6.46s
```

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

Copyright © 2026 Elsay Belude / ResolveAI. All rights reserved.