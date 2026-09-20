# AI Voice Agent Platform — Backend

Multi-tenant FastAPI backend. One codebase, any industry — clinic, restaurant,
hotel, real estate, gym, salon, law firm, e-commerce, HR, cold-calling —
driven entirely by data in `app/templates/industry_templates.py`, not
per-industry code.

## What's included (Phase 1 — verified working)

- JWT auth (signup/login) — tested end-to-end
- Multi-tenant DB models: User, Company, Agent, IndustryTemplate, KnowledgeBaseItem, CallLog, Integration
- Agent Builder API that generates a prompt from an industry template and deploys a live Vapi assistant
- Vapi webhook handling for live function-calls and end-of-call transcripts/analytics
- Google Calendar/Gmail and Microsoft Outlook/Calendar OAuth service stubs
- WhatsApp Business messaging service
- Action dispatch table for appointments, orders, leads, FAQs — ready to wire to real integrations

## Setup

```powershell
cd backend
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
copy .env.example .env
# edit .env with your real DATABASE_URL (PostgreSQL) and API keys
```

## Run

```powershell
uv run uvicorn app.main:app --reload --port 8000
```

Docs: http://localhost:8000/docs

## Important — Database

Models use PostgreSQL's native UUID column type (best practice for
production: proper indexing, no string overhead). **You must point
`DATABASE_URL` at real PostgreSQL** — local via Docker, or a free-tier
Render/Supabase/Neon instance. SQLite will not work correctly with these
models.

Quick local Postgres via Docker:
```powershell
docker run --name voiceagent-db -e POSTGRES_PASSWORD=password -e POSTGRES_DB=voiceagent -p 5432:5432 -d postgres:16
```
Then set: `DATABASE_URL=postgresql://postgres:password@localhost:5432/voiceagent`

## What's a stub vs what's real

| Component | Status |
|---|---|
| Auth, DB models, Agent Builder, Vapi deploy | Fully working, tested |
| Industry templates (11 industries) | Fully working, data-driven |
| Webhook handling (function-calls, call logs) | Fully working |
| Google/Microsoft OAuth | Real code, needs your OAuth app credentials to activate |
| WhatsApp messaging | Real code, needs your Meta Business app credentials |
| Calendar booking inside action_handler.py | Stubbed with clear TODOs pointing to the exact function to call |
| RAG / knowledge base embeddings | **Fully working.** Upload PDF/DOCX/CSV/XLSX/TXT/images (OCR) → chunked → embedded (OpenAI) → stored per-company in Qdrant. Tested end-to-end including tenant isolation. |
| Billing (Stripe) | Fields exist on Company; checkout flow not yet built (Phase 5) |

## Next steps (in priority order)

1. Point at real Postgres, run the app, confirm `/health` and signup/login work in your environment.
2. Build the Streamlit frontend (Create Company → Create Agent → Deploy flow).
3. Get a Vapi API key and test a real agent deploy end-to-end with a live phone call.
4. Build the RAG ingestion pipeline (Phase 2) so agents can answer from uploaded docs.
5. Register Google/Microsoft/Meta developer apps to activate the integrations.
