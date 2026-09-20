# AI Voice Agent Platform — Frontend

Streamlit dashboard: login/signup, company management, the 60-second
Agent Builder, Knowledge Base upload + retrieval testing, calendar
integration connection, and Stripe billing.

## Setup
```powershell
cd frontend
uv venv .venv
.\.venv\Scripts\Activate.ps1
uv pip install -r requirements.txt
```

## Run
```powershell
uv run streamlit run app.py
```
Opens at http://localhost:8501. Requires the backend running at
http://localhost:8000 (or set BACKEND_URL in .streamlit/secrets.toml
for a deployed backend).

## Pages
- **app.py** — login/signup
- **pages/1_Dashboard.py** — create/select company, view agents
- **pages/2_Create_Agent.py** — the agent builder (industry -> deploy)
- **pages/3_Knowledge_Base.py** — upload docs, test retrieval, connect calendar
- **pages/4_Billing.py** — plans ($30/$60/$90), Stripe checkout, billing portal

## Tested
All 5 pages verified to boot and render with zero server-side errors
(HTTP 200, no tracebacks) via Streamlit's headless test mode.
