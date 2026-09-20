"""
utils/api_client.py

WHAT THIS FILE DOES:
Every call from the Streamlit frontend to the FastAPI backend goes
through this one module instead of scattering `requests.get(...)` calls
across every page. This means: one place to handle the auth header, one
place to handle connection errors gracefully, one place to change the
backend URL. Every page imports `api` from here and calls e.g.
`api.list_companies()`.
"""

import requests
import streamlit as st

def _get_backend_url() -> str:
    """
    Reads BACKEND_URL from .streamlit/secrets.toml if one exists (used
    when the frontend is deployed separately from the backend, e.g.
    Streamlit Cloud). Falls back to localhost for local development.

    IMPORTANT: st.secrets raises FileNotFoundError (not AttributeError)
    when no secrets.toml exists at all — hasattr() does NOT catch that,
    so checking hasattr(st, "secrets") is not sufficient and previously
    crashed the entire app on first load for anyone without a secrets
    file. This wraps the access in a real try/except instead.
    """
    try:
        return st.secrets.get("BACKEND_URL", "http://localhost:8000")
    except Exception:
        return "http://localhost:8000"


BACKEND_URL = _get_backend_url()


class ApiError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


def _headers() -> dict:
    token = st.session_state.get("access_token")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _request(method: str, path: str, **kwargs) -> dict:
    url = f"{BACKEND_URL}{path}"
    try:
        response = requests.request(method, url, headers=_headers(), timeout=30, **kwargs)
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Can't reach the backend at {BACKEND_URL}. Is it running?")

    if response.status_code == 401:
        st.session_state.clear()
        raise ApiError("Your session expired. Please log in again.", status_code=401)

    if response.status_code >= 400:
        try:
            detail = response.json().get("detail", response.text)
        except ValueError:
            detail = response.text
        raise ApiError(str(detail), status_code=response.status_code)

    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


# ---- Auth ----
def signup(email: str, password: str, full_name: str) -> dict:
    return _request("POST", "/api/v1/auth/signup", json={"email": email, "password": password, "full_name": full_name})


def login(email: str, password: str) -> dict:
    return _request("POST", "/api/v1/auth/login", json={"email": email, "password": password})


# ---- Companies ----
def create_company(name: str, industry: str, website: str, timezone: str) -> dict:
    return _request("POST", "/api/v1/companies", json={"name": name, "industry": industry, "website": website, "timezone": timezone})


def list_companies() -> list:
    return _request("GET", "/api/v1/companies")


# ---- Agents ----
def create_agent(company_id: str, name: str, industry_key: str, language: str, custom_instructions: str, enabled_actions: list | None, business_description: str | None = None) -> dict:
    return _request("POST", "/api/v1/agents", json={
        "company_id": company_id, "name": name, "industry_key": industry_key,
        "language": language, "custom_instructions": custom_instructions,
        "enabled_actions": enabled_actions, "business_description": business_description,
    })


def list_agents(company_id: str) -> list:
    return _request("GET", "/api/v1/agents", params={"company_id": company_id})


def delete_agent(agent_id: str) -> dict:
    return _request("DELETE", f"/api/v1/agents/{agent_id}")


# ---- Knowledge base ----
def upload_document(company_id: str, category: str, file) -> dict:
    files = {"file": (file.name, file.getvalue())}
    data = {"company_id": company_id, "category": category}
    return _request("POST", "/api/v1/knowledge-base/upload", files=files, data=data)


def list_documents(company_id: str) -> list:
    return _request("GET", "/api/v1/knowledge-base", params={"company_id": company_id})


def delete_document(kb_item_id: str) -> dict:
    return _request("DELETE", f"/api/v1/knowledge-base/{kb_item_id}")


def test_kb_query(company_id: str, question: str) -> dict:
    return _request("GET", "/api/v1/knowledge-base/query", params={"company_id": company_id, "question": question})


# ---- Integrations ----
def list_integrations(company_id: str) -> list:
    return _request("GET", "/api/v1/integrations", params={"company_id": company_id})


def connect_google_url(company_id: str) -> dict:
    return _request("GET", "/api/v1/integrations/connect/google", params={"company_id": company_id})


def connect_microsoft_url(company_id: str) -> dict:
    return _request("GET", "/api/v1/integrations/connect/microsoft", params={"company_id": company_id})


# ---- Human handoff / escalation ----
def set_escalation_number(company_id: str, phone_number: str) -> dict:
    return _request("PATCH", f"/api/v1/companies/{company_id}/escalation-number", json={"phone_number": phone_number})


# ---- A/B testing ----
def create_variant(agent_id: str, variant_label: str, system_prompt: str) -> dict:
    return _request("POST", f"/api/v1/ab-tests/{agent_id}/variants", json={"variant_label": variant_label, "system_prompt": system_prompt})


def list_variants(agent_id: str) -> list:
    return _request("GET", f"/api/v1/ab-tests/{agent_id}/variants")


# ---- Onboarding ----
def get_onboarding_status(company_id: str) -> dict:
    return _request("GET", "/api/v1/onboarding/status", params={"company_id": company_id})


# ---- Team management ----
def list_members(company_id: str) -> list:
    return _request("GET", f"/api/v1/companies/{company_id}/members")


def invite_member(company_id: str, email: str, role: str) -> dict:
    return _request("POST", f"/api/v1/companies/{company_id}/invite", json={"email": email, "role": role})


# ---- Admin (superadmin only) ----
def admin_overview() -> dict:
    return _request("GET", "/api/v1/admin/overview")


def admin_list_companies() -> list:
    return _request("GET", "/api/v1/admin/companies")


# ---- Invoices ----
def list_invoices(company_id: str) -> list:
    return _request("GET", "/api/v1/billing/invoices", params={"company_id": company_id})


def download_invoice_pdf(invoice_id: str) -> bytes:
    """Returns raw PDF bytes - separate from _request since that assumes JSON responses."""
    import requests as req
    url = f"{BACKEND_URL}/api/v1/billing/invoices/{invoice_id}/pdf"
    response = req.get(url, headers=_headers(), timeout=30)
    if response.status_code >= 400:
        raise ApiError(f"Failed to download invoice: {response.text}")
    return response.content


# ---- Campaigns ----
def create_campaign(company_id: str, agent_id: str, name: str, file) -> dict:
    files = {"file": (file.name, file.getvalue())}
    data = {"company_id": company_id, "agent_id": agent_id, "name": name}
    return _request("POST", "/api/v1/campaigns", files=files, data=data)


def start_campaign(campaign_id: str) -> dict:
    return _request("POST", f"/api/v1/campaigns/{campaign_id}/start")


def list_campaigns(company_id: str) -> list:
    return _request("GET", "/api/v1/campaigns", params={"company_id": company_id})


def list_campaign_contacts(campaign_id: str) -> list:
    return _request("GET", f"/api/v1/campaigns/{campaign_id}/contacts")


# ---- Live calls ----
def list_live_calls(company_id: str) -> list:
    return _request("GET", "/api/v1/live-calls", params={"company_id": company_id})


# ---- Public demo (no auth) ----
def demo_chat(message: str, history: list) -> dict:
    return _request("POST", "/api/v1/demo/chat", json={"message": message, "history": history})


# ---- Preview chat (test agent without spending Vapi minutes) ----
def preview_chat(agent_id: str, message: str, history: list) -> dict:
    return _request("POST", f"/api/v1/agents/{agent_id}/preview-chat", json={"message": message, "history": history})


# ---- Leads / CRM ----
def list_leads(company_id: str) -> list:
    return _request("GET", "/api/v1/leads", params={"company_id": company_id})


# ---- Analytics ----
def get_analytics_summary(company_id: str, days: int = 30) -> dict:
    return _request("GET", "/api/v1/analytics/summary", params={"company_id": company_id, "days": days})


# ---- Billing ----
def list_plans() -> dict:
    return _request("GET", "/api/v1/billing/plans")


def create_checkout(company_id: str, plan: str, success_url: str, cancel_url: str) -> dict:
    return _request("POST", "/api/v1/billing/checkout", json={
        "company_id": company_id, "plan": plan, "success_url": success_url, "cancel_url": cancel_url,
    })


def create_portal(company_id: str, return_url: str) -> dict:
    return _request("POST", "/api/v1/billing/portal", json={"company_id": company_id, "return_url": return_url})

# ---- Added: endpoints the pages already call ----
def pause_campaign(campaign_id: str) -> dict:
    return _request("POST", f"/api/v1/campaigns/{campaign_id}/pause")


def list_do_not_call(company_id: str) -> list:
    return _request("GET", "/api/v1/campaigns/do-not-call", params={"company_id": company_id})


def add_do_not_call(company_id: str, phone: str, reason: str = "") -> dict:
    return _request("POST", "/api/v1/campaigns/do-not-call",
                    json={"company_id": company_id, "phone": phone, "reason": reason or "Added manually"})


def export_leads_csv(company_id: str) -> bytes:
    """Returns the raw CSV file (not JSON), so this doesn't go through _request."""
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/leads/export", headers=_headers(),
                         params={"company_id": company_id}, timeout=60)
    except requests.exceptions.ConnectionError:
        raise ApiError(f"Can't reach the backend at {BACKEND_URL}. Is it running?")
    if r.status_code == 401:
        st.session_state.clear()
        raise ApiError("Your session expired. Please log in again.", status_code=401)
    if r.status_code >= 400:
        raise ApiError(r.text, status_code=r.status_code)
    return r.content


def list_knowledge_gaps(company_id: str, include_resolved: bool = False) -> list:
    return _request("GET", "/api/v1/knowledge-gaps",
                    params={"company_id": company_id, "include_resolved": include_resolved})


def resolve_knowledge_gap(gap_id: str) -> dict:
    return _request("PATCH", f"/api/v1/knowledge-gaps/{gap_id}/resolve")


def delete_variant(agent_id: str, variant_id: str) -> dict:
    return _request("DELETE", f"/api/v1/ab-tests/{agent_id}/variants/{variant_id}")
