# ResolveAI — AI Customer Support & Operations Platform

ResolveAI is a full-stack, AI-augmented customer support operating system designed for multi-role support workflows, automated ticket triage, SLA monitoring, and contextual knowledge base grounding (RAG).

## Architecture & Tech Stack
- **Backend:** Python 3.11+, FastAPI (Async), SQLAlchemy 2.0, Alembic, Pydantic v2
- **Database:** PostgreSQL + pgvector
- **Frontend:** React, TypeScript, Vite, Tailwind CSS
- **AI & Retrieval:** OpenAI / Anthropic / Local LLM APIs, Vector Embeddings (RAG)
- **Queue & Background Jobs:** Redis + Celery / FastAPI BackgroundTasks
- **Testing & CI/CD:** Pytest, GitHub Actions, Docker Compose

## Project Phases
- [ ] **Phase 1:** Core Platform (FastAPI, Async SQLAlchemy, JWT Auth, RBAC, Ticket State Machine)
- [ ] **Phase 2:** Agent Operations (Multi-pane Inbox, SLA Engine, In-app Notifications, Analytics)
- [ ] **Phase 3:** AI Layer (Automated Triage, Suggested Replies, RAG Knowledge Assistant)
- [ ] **Phase 4:** Production Readiness (Pytest Suite, Docker, CI Pipeline, Monitoring)