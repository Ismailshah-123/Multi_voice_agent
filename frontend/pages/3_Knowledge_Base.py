"""
pages/3_Knowledge_Base.py

WHAT THIS FILE DOES:
The "Upload Documents" step from the product workflow. Lets the user
upload PDFs/CSVs/DOCX/images for their active company (feeds the RAG
pipeline), view processing status, delete documents, and test what the
agent would actually retrieve for a sample question before going live.
Also shows the Google/Microsoft calendar connection status for booking
actions.
"""

import streamlit as st
from utils import api_client as api
from utils.session import require_login, require_company
from utils.theme import inject_theme

st.set_page_config(layout="wide")
inject_theme()

require_login()
require_company()

company_id = st.session_state["active_company_id"]

st.title("📚 Knowledge Base")
st.caption("Upload menus, policies, price lists, or FAQs — your agent answers calls using this content.")

tab_upload, tab_test, tab_gaps, tab_integrations = st.tabs(["Upload Documents", "Test Retrieval", "Knowledge Gaps", "Integrations"])

with tab_upload:
    with st.form("upload_form", clear_on_submit=True):
        uploaded_file = st.file_uploader("Choose a file", type=["pdf", "docx", "csv", "xlsx", "txt", "md"])
        category = st.text_input("Category (optional)", placeholder="e.g. menu, insurance_policies, price_list")
        submitted = st.form_submit_button("Upload & Process", type="primary")
        if submitted:
            if not uploaded_file:
                st.error("Choose a file first.")
            else:
                with st.spinner("Extracting text, chunking, and embedding..."):
                    try:
                        result = api.upload_document(company_id, category, uploaded_file)
                        st.success(f"'{result['file_name']}' processed — {result['chunks_stored']} chunks stored.")
                    except api.ApiError as e:
                        st.error(f"Upload failed: {e}")

    st.divider()
    st.subheader("Uploaded documents")
    try:
        docs = api.list_documents(company_id)
    except api.ApiError as e:
        st.error(str(e))
        docs = []

    if not docs:
        st.info("No documents uploaded yet.")
    else:
        for doc in docs:
            status_icon = {"completed": "✅", "processing": "⏳", "failed": "❌", "pending": "⏳"}.get(doc["status"], "❓")
            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 1])
                c1.markdown(f"**{status_icon} {doc['file_name']}**")
                c1.caption(f"Category: {doc.get('category') or 'uncategorized'}")
                c2.write(f"Status: {doc['status']}")
                if doc.get("error_message"):
                    c2.caption(f"⚠️ {doc['error_message']}")
                if c3.button("Delete", key=f"del_doc_{doc['id']}"):
                    try:
                        api.delete_document(doc["id"])
                        st.rerun()
                    except api.ApiError as e:
                        st.error(str(e))

with tab_test:
    st.write("Ask a question the way a customer would, and see exactly what your agent would retrieve.")
    question = st.text_input("Test question", placeholder="What time do you close on Sundays?")
    if st.button("Test") and question:
        try:
            result = api.test_kb_query(company_id, question)
            matches = result.get("matches", [])
            generated_answer = result.get("generated_answer", "")
 
            st.markdown("### 🎙️ What your agent would actually say:")
            st.success(generated_answer)
            st.caption(
                "This is the real, generated answer used on live calls and in "
                "Text Chat testing. The raw matches below are for debugging "
                "only — their scores are small fusion scores, not confidence "
                "percentages, and that's expected."
            )
            st.divider()
 
            if not matches:
                st.warning("No relevant content found. Upload documents covering this topic.")
            else:
                with st.expander("🔍 Raw retrieved chunks (debug info)"):
                    for m in matches:
                        st.markdown(f"**Match (score: {m['score']:.4f})** — _{m.get('file_name') or 'unknown source'}_")
                        st.write(m["text"])
                        st.divider()
        except api.ApiError as e:
            st.error(str(e))

with tab_integrations:
    st.write("Connect your calendar so booking actions create real appointments.")
    try:
        integrations = api.list_integrations(company_id)
    except api.ApiError as e:
        st.error(str(e))
        integrations = []

    connected_providers = {i["provider"] for i in integrations}

    col1, col2 = st.columns(2)
    with col1:
        if "google_calendar" in connected_providers:
            st.success("✅ Google Calendar connected")
        else:
            if st.button("Connect Google Calendar", type="primary"):
                try:
                    result = api.connect_google_url(company_id)
                    st.markdown(f"[Click here to authorize Google Calendar]({result['authorization_url']})")
                except api.ApiError as e:
                    st.error(str(e))

    with col2:
        if "outlook_calendar" in connected_providers:
            st.success("✅ Outlook Calendar connected")
        else:
            if st.button("Connect Outlook Calendar", type="primary"):
                try:
                    result = api.connect_microsoft_url(company_id)
                    st.markdown(f"[Click here to authorize Outlook Calendar]({result['authorization_url']})")
                except api.ApiError as e:
                    st.error(str(e))
with tab_gaps:
        st.write("Real questions your agent couldn't confidently answer — this tells you exactly what to add to your documents.")
        try:
            gaps = api.list_knowledge_gaps(company_id)
        except api.ApiError as e:
            st.error(str(e))
            gaps = []
 
        if not gaps:
            st.success("No knowledge gaps yet — either your documents cover everything asked so far, or you haven't received questions yet.")
        else:
            for gap in gaps:
                with st.container(border=True):
                    col1, col2 = st.columns([4, 1])
                    col1.markdown(f"**\"{gap['question']}\"**")
                    col1.caption(f"Asked {gap['occurrence_count']} time(s) — last seen {str(gap['last_seen_at'])[:10]}")
                    if col2.button("Mark Resolved", key=f"resolve_{gap['id']}"):
                        try:
                            api.resolve_knowledge_gap(gap["id"])
                            st.success("Marked resolved.")
                            st.rerun()
                        except api.ApiError as e:
                            st.error(str(e))