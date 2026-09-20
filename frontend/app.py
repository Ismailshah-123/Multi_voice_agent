"""
app.py

WHAT THIS FILE DOES:
The entrypoint Streamlit runs first. Shows the login/signup screen if the
user isn't authenticated yet; once logged in, shows a welcome screen with
navigation into the rest of the app (Dashboard, Create Agent, Knowledge
Base, Call Logs, Billing — each is a file in pages/, which Streamlit
auto-adds to the sidebar navigation).

RUN:
    uv run streamlit run app.py
"""

import streamlit as st
st.set_page_config(page_title="AI Voice Agent Platform", page_icon="🎙️", layout="wide")
import streamlit.components.v1 as components
from utils import api_client as api
from utils.theme import inject_theme, kpi_card, section_header, CINEMATIC_CSS
inject_theme()

LANDING_CSS = """
<style>
.hero-title{font-size:54px;font-weight:800;line-height:1.08;letter-spacing:-.025em;color:#0B2545;margin:8px 0 14px}
.hero-sub{font-size:19px;line-height:1.6;color:#3B4B66;max-width:640px}
.cta{display:inline-block;background:#1D4ED8;color:#fff!important;font-weight:700;padding:13px 28px;border-radius:10px;text-decoration:none!important;margin-top:6px}
.cta:hover{background:#1E40AF}
.feature-card,.flow-step{background:#fff;border:1px solid #DDE5F0;border-radius:14px;padding:24px;height:100%;box-shadow:0 1px 2px rgba(11,37,69,.05);transition:border-color .2s}
.feature-card:hover,.flow-step:hover{border-color:#9DB8EE}
.flow-step{text-align:center;padding:18px}
.feature-icon{font-size:24px;margin-bottom:10px}
.feature-title{font-size:17px;font-weight:700;color:#0B2545;margin-bottom:6px}
.feature-desc{font-size:14px;color:#5A6B85;line-height:1.6}
.flow-num{display:inline-block;width:30px;height:30px;border-radius:50%;background:#1D4ED8;color:#fff;font-weight:700;line-height:30px;margin-bottom:8px}
.badge{display:inline-block;padding:5px 14px;margin:4px;border-radius:20px;border:1px solid #DDE5F0;background:#fff;color:#3B4B66;font-size:13px}
.free-badge{border-color:#BBF7D0;background:#F0FDF4;color:#15803D}
</style>
"""


def render_particle_hero():
    """Animated particle-network canvas background behind the hero — the kind of touch real AI product landing pages use."""
    components.html("""
    <canvas id="particle-canvas" style="width:100%; height:280px; display:block;"></canvas>
    <script>
        const canvas = document.getElementById('particle-canvas');
        const ctx = canvas.getContext('2d');
        function resize() { canvas.width = canvas.offsetWidth; canvas.height = canvas.offsetHeight; }
        resize();
        window.addEventListener('resize', resize);

        const particles = Array.from({length: 55}, () => ({
            x: Math.random() * canvas.width,
            y: Math.random() * canvas.height,
            vx: (Math.random() - 0.5) * 0.4,
            vy: (Math.random() - 0.5) * 0.4,
            r: Math.random() * 1.8 + 0.6,
        }));

        function tick() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            particles.forEach(p => {
                p.x += p.vx; p.y += p.vy;
                if (p.x < 0 || p.x > canvas.width) p.vx *= -1;
                if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(29, 78, 216, 0.35)';
                ctx.fill();
            });
            for (let i = 0; i < particles.length; i++) {
                for (let j = i + 1; j < particles.length; j++) {
                    const dx = particles[i].x - particles[j].x;
                    const dy = particles[i].y - particles[j].y;
                    const dist = Math.sqrt(dx * dx + dy * dy);
                    if (dist < 110) {
                        ctx.beginPath();
                        ctx.moveTo(particles[i].x, particles[i].y);
                        ctx.lineTo(particles[j].x, particles[j].y);
                        ctx.strokeStyle = `rgba(29, 78, 216, ${0.18 * (1 - dist / 110)})`;
                        ctx.lineWidth = 1;
                        ctx.stroke();
                    }
                }
            }
            requestAnimationFrame(tick);
        }
        tick();
    </script>
    """, height=280)


def render_landing():
    st.markdown(LANDING_CSS, unsafe_allow_html=True)
    render_particle_hero()

    st.markdown('<div class="hero-title">Create Your AI Employee<br>in 60 Seconds.</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="hero-sub">One platform. Any business. Clinics, restaurants, hotels, real estate, gyms, '
        'law firms, e-commerce — or describe your own and let AI build the agent for you. Every agent answers '
        'real phone calls, books real appointments, and learns from your own documents.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<a class="cta" href="#get-started">Get started</a>', unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)

    # ---- The problem / solution ----
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(section_header("The Problem"), unsafe_allow_html=True)
        st.markdown(
            "Every business misses calls. Receptionists get overwhelmed, hold times frustrate customers, "
            "and after-hours calls go straight to voicemail — lost bookings, lost orders, lost revenue. "
            "Hiring 24/7 phone staff isn't realistic for most small and mid-sized businesses."
        )
    with col2:
        st.markdown(section_header("The Solution"), unsafe_allow_html=True)
        st.markdown(
            "An AI voice employee that answers every call, instantly, 24/7 — takes orders, books appointments, "
            "answers questions from your actual menu or policy documents, remembers returning customers, and "
            "hands off complex requests to your team automatically. No code. No hiring. Live in minutes."
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- How it works ----
    st.markdown(section_header("How It Works"), unsafe_allow_html=True)
    steps = [
        ("1", "Sign Up", "Create your account and add your business."),
        ("2", "Describe or Pick Industry", "Choose from 11 presets, or describe any business and AI builds it."),
        ("3", "Upload Knowledge", "Add your menu, policies, or FAQs — the agent learns instantly."),
        ("4", "Go Live", "Get a real phone number. Your AI employee starts answering calls."),
    ]
    cols = st.columns(4)
    for col, (num, title, desc) in zip(cols, steps):
        with col:
            st.markdown(
                f'<div class="flow-step"><div class="flow-num">{num}</div>'
                f'<div class="feature-title">{title}</div>'
                f'<div class="feature-desc">{desc}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown("<br>", unsafe_allow_html=True)

    # ---- Feature grid ----
    st.markdown(section_header("What's Inside"), unsafe_allow_html=True)
    features = [
        ("🎙️", "Real Voice Calls", "Powered by Vapi + Groq's Llama 3.3 70B — natural, fast, live phone conversations, not a chatbot."),
        ("🧠", "Industry-Grade RAG", "Hybrid search (vector + keyword) with cross-encoder reranking and semantic caching — your agent answers from your real documents, accurately."),
        ("✨", "AI Agent Builder", "11 ready-made industries, or describe any business in plain English and AI generates a tailored agent — actions included."),
        ("📅", "Real Calendar Booking", "Connects to Google Calendar — bookings and cancellations actually happen, not just get logged."),
        ("🧬", "Repeat-Caller Memory", "Recognizes returning phone numbers and personalizes the greeting using history from past calls."),
        ("👥", "Built-in CRM", "Every booking, order, and lead captured automatically — no manual data entry."),
        ("💬", "WhatsApp Automation", "Sends automatic booking/order confirmations after every call ends."),
        ("💳", "Subscription Billing", "Stripe-powered plans ($30/$60/$90) with usage limits enforced automatically."),
        ("📈", "Live Analytics", "Real call volume, conversion rate, and outcome tracking — not vanity metrics."),
        ("🧪", "Free Agent Testing", "Test your agent's conversation via text chat before spending a single call minute."),
        ("🔒", "True Multi-Tenant Isolation", "Every business's data, documents, and calls are fully isolated — one platform, unlimited customers."),
        ("🆓", "Free AI Stack", "Groq (free LLM) + local embeddings + local reranker — no OpenAI dependency, minimal running cost."),
    ]
    for row_start in range(0, len(features), 3):
        cols = st.columns(3)
        for col, (icon, title, desc) in zip(cols, features[row_start:row_start + 3]):
            with col:
                st.markdown(
                    f'<div class="feature-card"><div class="feature-icon">{icon}</div>'
                    f'<div class="feature-title">{title}</div>'
                    f'<div class="feature-desc">{desc}</div></div>',
                    unsafe_allow_html=True,
                )
        st.markdown("<br>", unsafe_allow_html=True)

    # ---- Tech stack ----
    st.markdown(section_header("Built On"), unsafe_allow_html=True)
    tech_free = ["Groq Llama 3.3 70B", "Local Embeddings (BGE)", "Local Reranker", "Qdrant", "PostgreSQL", "FastAPI", "Streamlit"]
    tech_paid = ["Vapi (voice)", "Stripe (billing)", "Google Calendar", "WhatsApp Business"]
    badges_html = "".join(f'<span class="badge free-badge">{t} — Free</span>' for t in tech_free)
    badges_html += "".join(f'<span class="badge">{t}</span>' for t in tech_paid)
    st.markdown(badges_html, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ---- Live dashboard preview (sample data, clearly labeled) ----
    st.markdown(section_header("📊 See What Your Dashboard Looks Like"), unsafe_allow_html=True)
    st.caption("Sample data shown below — this is what YOUR real analytics look like once your agents start taking calls.")

    from utils.enterprise_widgets import render_animated_kpi_row, render_radial_gauge
    render_animated_kpi_row([
        {"label": "Total Calls", "value": 342, "sub": "Last 30 days", "color": "#1D4ED8", "sparkline": [12, 18, 15, 24, 20, 28, 31, 26, 33, 29]},
        {"label": "Avg Duration", "value": 2.4, "suffix": " min", "sub": "142s average", "color": "#0EA5E9"},
        {"label": "Leads Captured", "value": 118, "sub": "Bookings + orders + inquiries", "color": "#60A5FA"},
        {"label": "Conversion Rate", "value": 41.5, "suffix": "%", "sub": "142 booked of 342 calls", "color": "#16A34A"},
    ], height=170)

    gauge_col1, gauge_col2, gauge_col3 = st.columns(3)
    with gauge_col1:
        render_radial_gauge("Plan Minutes Used", 62, color="#1D4ED8")
    with gauge_col2:
        render_radial_gauge("Calls Auto-Resolved", 87, color="#16A34A")
    with gauge_col3:
        render_radial_gauge("Customer Satisfaction", 94, color="#0EA5E9")

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ---- Full About / architecture section ----
    st.markdown(section_header("ℹ️ About This Platform"), unsafe_allow_html=True)

    about_tab1, about_tab2, about_tab3, about_tab4 = st.tabs(["What It Is", "How It Works", "What's Included", "Who It's For"])

    with about_tab1:
        st.markdown("""
This is a **multi-tenant AI Voice Agent platform** — one piece of software that lets ANY business
create a fully functional AI phone employee in minutes, without writing a single line of code.

A clinic gets a receptionist. A restaurant gets an order-taker. A law firm gets an intake assistant.
A business that doesn't fit any preset category gets one **AI-generated on the spot** from a plain-English
description. All of it runs on ONE shared platform — one login system, one billing system, one dashboard —
while every business's data, calls, documents, and customers stay completely isolated from every other
business using the platform.

The AI's "brain" is a real large language model (Groq's Llama 3.3 70B) having a live voice conversation
through Vapi's telephony infrastructure — not a scripted phone tree, not press-1-for-sales. It listens,
understands, and responds naturally, and it can actually DO things: book a real appointment on your
calendar, take a real order, answer questions from your actual uploaded documents, and remember
returning customers by name.
        """)

    with about_tab2:
        st.markdown("""
**1. Sign up and create a company** — this is your business/tenant on the platform.

**2. Deploy an agent** — pick an industry template, or describe your business in plain English and
let AI build a custom one. This deploys a real, live voice assistant in under a minute.

**3. Upload your documents** — menus, price lists, policies, FAQs. The agent chunks, embeds, and
indexes them automatically so it can answer real questions accurately.

**4. Connect your calendar (optional)** — one click connects Google Calendar, enabling real
appointment booking and email confirmations.

**5. Go live** — get a real phone number, or test instantly through the built-in browser voice widget
with zero setup.

**6. Every call is handled automatically** — the agent talks, takes action, and after the call ends,
sends confirmations (WhatsApp/email), updates your built-in CRM, and remembers the caller for next time.
        """)

    with about_tab3:
        st.markdown("""
- **11 ready-made industries** + unlimited AI-generated custom industries
- **Industry-grade RAG** — hybrid search, cross-encoder reranking, semantic caching, 100% free local AI models
- **Real calendar booking AND cancellation** — not just logged, actually happens
- **WhatsApp + email confirmations** sent automatically after every call
- **Structured customer memory** — the agent recalls preferences across calls, not just a name
- **Live call monitoring** — watch conversations happen in near real-time, with automatic frustration detection
- **Human handoff** — agents transfer to a real person when they can't help
- **Outbound cold-calling campaigns** — upload a CSV, the platform dials automatically
- **A/B prompt testing** — run two prompt variants, compare real conversion rates
- **Built-in CRM, live analytics, team accounts, and platform admin panel**
- **Stripe billing** with three plans, PDF receipts included
        """)

    with about_tab4:
        st.markdown("""
- **Solo operators or agencies** who want to resell AI phone agents to local businesses
- **Clinics, restaurants, hotels, salons, gyms, law firms, real estate agencies** — any business that
  answers a phone and loses revenue when nobody picks up
- **Anyone building a SaaS product** who wants a working multi-tenant foundation rather than starting
  from a blank repo
        """)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ---- ROI Calculator ----
    st.markdown(section_header("💰 See What Missed Calls Are Costing You"), unsafe_allow_html=True)
    roi_col1, roi_col2 = st.columns([1, 1])
    with roi_col1:
        missed_calls_per_week = st.slider("Missed or unanswered calls per week", 5, 200, 30)
        avg_order_value = st.number_input("Average value per booking/order ($)", min_value=5, value=40, step=5)
        close_rate = st.slider("Estimated % of missed calls that would've converted", 10, 80, 35)

    with roi_col2:
        monthly_missed = missed_calls_per_week * 4.3
        recovered_conversions = monthly_missed * (close_rate / 100)
        recovered_revenue = recovered_conversions * avg_order_value

        st.markdown(kpi_card("Missed Calls / Month", f"{monthly_missed:.0f}", "Based on your input"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(kpi_card("Potential Revenue Recovered", f"${recovered_revenue:,.0f}/mo", f"~{recovered_conversions:.0f} recovered bookings"), unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown(kpi_card("Plan Cost", "$30–$90/mo", "vs. potential revenue above"), unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)

    # ---- Live Demo Chat ----
    st.markdown(section_header("🎙️ Try It Right Now — No Signup Needed"), unsafe_allow_html=True)
    st.caption("This is a live AI agent for a demo pizza restaurant. Order something, ask about the menu, or book a table.")

    if "demo_chat_history" not in st.session_state:
        st.session_state["demo_chat_history"] = []

    for turn in st.session_state["demo_chat_history"]:
        with st.chat_message(turn["role"]):
            st.write(turn["content"])

    demo_msg = st.chat_input("Try: \"I'd like to order a pepperoni pizza\"")
    if demo_msg:
        st.session_state["demo_chat_history"].append({"role": "user", "content": demo_msg})
        try:
            result = api.demo_chat(demo_msg, st.session_state["demo_chat_history"][:-1])
            st.session_state["demo_chat_history"].append({"role": "assistant", "content": result["reply"]})
        except api.ApiError as e:
            st.error(str(e))
        st.rerun()

    st.markdown("<br><br>", unsafe_allow_html=True)

    st.markdown(section_header("Ready to build your first AI employee?"), unsafe_allow_html=True)
    st.caption("Log in or create an account below to get started.")


render_landing()
st.divider()


def render_login_signup():
    st.markdown('<div id="get-started"></div>' + section_header("Log in or create your account"), unsafe_allow_html=True)
    st.caption("Build your first AI employee in about 60 seconds.")

    tab_login, tab_signup = st.tabs(["Log In", "Sign Up"])

    with tab_login:
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log In", type="primary", use_container_width=True)
            if submitted:
                try:
                    result = api.login(email, password)
                    st.session_state["access_token"] = result["access_token"]
                    st.session_state["user"] = result["user"]
                    st.rerun()
                except api.ApiError as e:
                    st.error(str(e))

    with tab_signup:
        with st.form("signup_form"):
            full_name = st.text_input("Full Name")
            email = st.text_input("Email", key="signup_email")
            password = st.text_input("Password", type="password", key="signup_password")
            submitted = st.form_submit_button("Create Account", type="primary", use_container_width=True)
            if submitted:
                if len(password) < 8:
                    st.error("Password must be at least 8 characters.")
                else:
                    try:
                        result = api.signup(email, password, full_name)
                        st.session_state["access_token"] = result["access_token"]
                        st.session_state["user"] = result["user"]
                        st.rerun()
                    except api.ApiError as e:
                        st.error(str(e))


def render_welcome():
    user = st.session_state.get("user", {})
    st.title(f"Welcome back, {user.get('full_name') or user.get('email')} ")
    st.write("Use the sidebar to manage your companies, build AI agents, upload knowledge, and view call analytics.")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Platform", "AI Voice Agent SaaS")
    with col2:
        st.metric("Status", "Connected")
    with col3:
        if st.button("Log Out"):
            st.session_state.clear()
            st.rerun()

    st.divider()
    st.subheader("Get started")
    st.markdown(
        "1. Go to **Dashboard** and create your first company.\n"
        "2. Go to **Create Agent** and deploy an AI employee for it.\n"
        "3. Go to **Knowledge Base** and upload your menu, policies, or FAQs.\n"
        "4. Go to **Call Logs** to see how your agent is performing.\n"
        "5. Go to **Billing** to upgrade your plan."
    )


if "access_token" not in st.session_state:
    render_login_signup()
else:
    render_welcome()
