
""" 
pages/8_Campaigns.py 
 
WHAT THIS FILE DOES: 
Outbound cold-calling campaigns. Upload a CSV of phone numbers (with 
optional names), pick which agent should make the calls, and start the campaign — the platform calls every contact automatically via Vapi. 
Track progress and results per contact. 
""" 
 
import streamlit as st 
from utils import api_client as api 
from utils.session import require_login, require_company 
 
st.set_page_config(page_title="Campaigns", page_icon="📞", layout="wide") 
from utils.theme import inject_theme, section_header, pulse_dot 
inject_theme() 
require_login() 
require_company() 
 
company_id = st.session_state["active_company_id"] 
 
st.markdown(section_header("📞 Outbound Campaigns"), unsafe_allow_html=True) 
st.caption("Upload a list of phone numbers and let your AI agent call them automatically.") 
 
try: 
    agents = api.list_agents(company_id) 
except api.ApiError as e: 
    st.error(str(e)) 
    agents = [] 
 
if not agents: 
    st.info("Create an agent first (Create Agent page) before starting a campaign.") 
    st.stop() 
 
with st.expander("➕ Create a new campaign", expanded=False): 
    with st.form("create_campaign_form"): 
        campaign_name = st.text_input("Campaign name", placeholder="Q3 Outreach") 
        agent_options = {a["id"]: a["name"] for a in agents} 
        agent_id = st.selectbox( 
            "Which agent should make these calls?", 
            options=list(agent_options.keys()), 
            format_func=lambda a: agent_options[a] 
        ) 
        uploaded_file = st.file_uploader( 
            "Contact list (CSV with 'phone' column, optional 'name' column)", 
            type=["csv"] 
        ) 
        submitted = st.form_submit_button("Create Campaign", type="primary") 
 
        if submitted: 
            if not campaign_name or not uploaded_file: 
                st.error("Campaign name and a CSV file are required.") 
            else: 
                try: 
                    result = api.create_campaign( 
                        company_id, 
                        agent_id, 
                        campaign_name, 
                        uploaded_file 
                    ) 
                    st.success( 
                        f"Campaign '{result['name']}' created with " 
                        f"{result['total_contacts']} contacts." 
                    ) 
                    st.rerun() 
                except api.ApiError as e: 
                    st.error(str(e)) 
 
st.divider() 
 
# ----------------------------------------------------------------------------- 
# Do Not Call List 
# ----------------------------------------------------------------------------- 
 
with st.expander("🚫 Do Not Call List", expanded=False): 
    st.caption( 
        "Numbers added here should not be contacted by outbound campaigns." 
    ) 
 
    with st.form("add_do_not_call_form"): 
        dnc_phone = st.text_input( 
            "Phone number", 
            placeholder="+923001234567" 
        ) 
        dnc_reason = st.text_input( 
            "Reason (optional)", 
            placeholder="Customer requested no further calls" 
        ) 
        dnc_submitted = st.form_submit_button("Add to Do Not Call List") 
 
        if dnc_submitted: 
            if not dnc_phone.strip(): 
                st.error("Phone number is required.") 
            else: 
                try: 
                    api.add_do_not_call( 
                        company_id, 
                        dnc_phone.strip(), 
                        dnc_reason.strip() 
                    ) 
                    st.success("Number added to the Do Not Call List.") 
                    st.rerun() 
                except api.ApiError as e: 
                    st.error(str(e)) 
 
    try: 
        dnc_entries = api.list_do_not_call(company_id) 
    except api.ApiError as e: 
        st.error(str(e)) 
        dnc_entries = [] 
 
    if dnc_entries: 
        for entry in dnc_entries: 
            phone = entry.get("phone", "") 
            reason = entry.get("reason", "") 
            if reason: 
                st.write(f"🚫 {phone} — {reason}") 
            else: 
                st.write(f"🚫 {phone}") 
    else: 
        st.info("No numbers are currently on the Do Not Call List.") 
 
st.divider() 
 
# ----------------------------------------------------------------------------- 
# Campaigns 
# ----------------------------------------------------------------------------- 
 
try: 
    campaigns = api.list_campaigns(company_id) 
except api.ApiError as e: 
    st.error(str(e)) 
    campaigns = [] 
 
if not campaigns: 
    st.info("No campaigns yet. Create one above.") 
else: 
    for c in campaigns: 
        with st.container(border=True): 
            status_display = ( 
                f'{pulse_dot()} Running' 
                if c["status"] == "running" 
                else c["status"].capitalize() 
            ) 
 
            col1, col2, col3 = st.columns([2, 2, 1]) 
 
            col1.markdown(f"**{c['name']}**") 
            col1.markdown(status_display, unsafe_allow_html=True) 
 
            col2.write( 
                f"{c['calls_completed']} / " 
                f"{c['total_contacts']} calls completed" 
            ) 
 
            if c["total_contacts"]: 
                col2.progress( 
                    min( 
                        c["calls_completed"] / c["total_contacts"], 
                        1.0 
                    ) 
                ) 
 
            if c["status"] == "draft": 
                if col3.button( 
                    "Start Campaign", 
                    key=f"start_{c['id']}" 
                ): 
                    try: 
                        result = api.start_campaign(c["id"]) 
                        st.success( 
                            f"Placed {result['calls_placed']} calls. " 
                            f"{result['calls_failed_to_start']} failed to start." 
                        ) 
                        st.rerun() 
                    except api.ApiError as e: 
                        st.error(str(e)) 
 
            elif c["status"] == "running": 
                if col3.button( 
                    "Pause Campaign", 
                    key=f"pause_{c['id']}" 
                ): 
                    try: 
                        api.pause_campaign(c["id"]) 
                        st.success("Campaign paused successfully.") 
                        st.rerun() 
                    except api.ApiError as e: 
                        st.error(str(e)) 
 
            with st.expander("View contacts"): 
                try: 
                    contacts = api.list_campaign_contacts(c["id"]) 
                    status_icons = { 
                        "pending": "⚪", 
                        "calling": "🟡", 
                        "completed": "✅", 
                        "failed": "🔴", 
                        "no_answer": "📵" 
                    } 
 
                    for contact in contacts: 
                        icon = status_icons.get( 
                            contact["status"], 
                            "⚪" 
                        ) 
 
                        st.write( 
                            f"{icon} " 
                            f"{contact.get('name') or 'Unknown'} — " 
                            f"{contact['phone']} " 
                            f"({contact['status']})" 
                        ) 
 
                        if contact.get("outcome_notes"): 
                            st.caption(contact["outcome_notes"]) 
 
                except api.ApiError as e: 
                    st.error(str(e)) 
 
st.divider() 
 
# ----------------------------------------------------------------------------- 
# Lead Export 
# ----------------------------------------------------------------------------- 
 
st.markdown("### 📤 Export Leads") 
st.caption("Download the company's leads as a CSV file.") 
 
if st.button("Export Leads CSV", key="export_leads_csv"): 
    try: 
        csv_data = api.export_leads_csv(company_id) 
 
        st.download_button( 
            label="⬇️ Download Leads CSV", 
            data=csv_data, 
            file_name="leads.csv", 
            mime="text/csv", 
            key="download_leads_csv" 
        ) 
 
    except api.ApiError as e: 
        st.error(str(e)) 

