"""
utils/theme.py

Global design system - clean, professional light theme: white cards on a soft blue-grey page,
dark-navy sidebar and headings, one strong blue for actions. Manrope throughout.
Call `inject_theme()` right after `st.set_page_config` on every page.
Class names (kpi-card, section-header, pulse-dot...) are used across the app - keep them stable.
"""

import streamlit as st

CINEMATIC_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--navy:#0B2545;--blue:#1D4ED8;--blue-deep:#1E40AF;--tint:#EAF1FF;--bg:#F4F7FB;--card:#FFFFFF;--line:#DDE5F0;--text:#0B2545;--soft:#3B4B66;--muted:#5A6B85;--ok:#16A34A}

.stApp{font-family:'Manrope',system-ui,-apple-system,'Segoe UI',sans-serif;color:var(--text);background:var(--bg)}
button,input,textarea,select{font-family:inherit}
h1,h2,h3,h4,.section-header,.kpi-value{font-weight:700;letter-spacing:-.015em;color:var(--navy)}
h1{font-size:2rem} h2{font-size:1.5rem} h3{font-size:1.2rem}
p,li,label,[data-testid="stCaptionContainer"]{color:var(--soft)}
a{color:var(--blue)}
.block-container{max-width:1240px;padding-top:2.4rem;padding-bottom:4rem}
#MainMenu,footer,.stDeployButton{display:none!important}
header[data-testid="stHeader"]{background:transparent}
::-webkit-scrollbar{width:10px;height:10px}::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:#C5D2E6;border-radius:10px}

/* Sidebar: dark navy */
section[data-testid="stSidebar"]{background:var(--navy);border-right:none}
section[data-testid="stSidebar"] :is(h1,h2,h3,p,label,span,small){color:#DCE6F5}
[data-testid="stSidebarNav"] a{border-radius:10px;color:#C9D6EA;font-weight:500}
[data-testid="stSidebarNav"] a span{color:inherit}
[data-testid="stSidebarNav"] a:hover{background:rgba(255,255,255,.08);color:#fff}
[data-testid="stSidebarNav"] a[aria-current="page"]{background:rgba(255,255,255,.12);color:#fff;box-shadow:inset 3px 0 0 #60A5FA}
[data-testid="stSidebarCollapseButton"] *{color:#C9D6EA}

/* Cards */
.kpi-card,[data-testid="stMetric"]{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:20px 22px;box-shadow:0 1px 2px rgba(11,37,69,.05);transition:border-color .2s}
.kpi-card:hover{border-color:#9DB8EE}
.kpi-label,[data-testid="stMetricLabel"]{font-size:13px;color:var(--muted);font-weight:600;margin-bottom:10px}
.kpi-value{font-size:30px;font-weight:800;line-height:1.1}
.kpi-sub{font-size:12.5px;color:var(--muted);margin-top:8px}
.section-header{font-size:20px;margin:4px 0 8px}
div[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px!important;border-color:var(--line)!important;background:var(--card);box-shadow:0 1px 2px rgba(11,37,69,.04)}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:12px;background:var(--card)}
[data-testid="stAlert"]{border-radius:12px}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:12px;overflow:hidden}

/* Buttons: default = quiet white, type="primary" = solid blue */
.stButton>button,.stDownloadButton>button,.stFormSubmitButton>button{background:var(--card);color:var(--navy);border:1px solid var(--line);border-radius:10px;font-weight:600;padding:.55rem 1.1rem;transition:border-color .15s,background .15s}
.stButton>button:hover,.stDownloadButton>button:hover,.stFormSubmitButton>button:hover{background:var(--tint);border-color:var(--blue);color:var(--blue)}
button p{color:inherit}
button[data-testid="stBaseButton-primary"],button[data-testid="stBaseButton-primaryFormSubmit"]{background:var(--blue);border-color:var(--blue);color:#fff}
button[data-testid="stBaseButton-primary"]:hover,button[data-testid="stBaseButton-primaryFormSubmit"]:hover{background:var(--blue-deep);border-color:var(--blue-deep);color:#fff}
button:focus-visible,a:focus-visible{outline:2px solid var(--blue)!important;outline-offset:2px}

/* Inputs */
[data-baseweb="input"]>div,[data-baseweb="select"]>div,[data-baseweb="textarea"]>div{background:var(--card)!important;border:1px solid var(--line)!important;border-radius:10px!important}
[data-baseweb="input"]>div:focus-within,[data-baseweb="select"]>div:focus-within,[data-baseweb="textarea"]>div:focus-within{border-color:var(--blue)!important;box-shadow:0 0 0 3px rgba(29,78,216,.15)}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:4px;border-bottom:1px solid var(--line)}
.stTabs [data-baseweb="tab"]{background:transparent;color:var(--muted);font-weight:600}
.stTabs [aria-selected="true"]{color:var(--navy)}
.stTabs [data-baseweb="tab-highlight"]{background:var(--blue)}

/* Live status dot */
.pulse-dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--ok);margin-right:8px;animation:pulse 2s infinite}
@keyframes pulse{0%{box-shadow:0 0 0 0 rgba(22,163,74,.5)}70%{box-shadow:0 0 0 9px rgba(22,163,74,0)}100%{box-shadow:0 0 0 0 rgba(22,163,74,0)}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
"""


def inject_theme():
    st.markdown(CINEMATIC_CSS, unsafe_allow_html=True)


def kpi_card(label: str, value: str, sub: str = "") -> str:
    """HTML for one KPI card - use with st.markdown(..., unsafe_allow_html=True)."""
    return f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
        <div class="kpi-sub">{sub}</div>
    </div>
    """


def section_header(text: str) -> str:
    return f'<div class="section-header">{text}</div>'


def pulse_dot() -> str:
    return '<span class="pulse-dot"></span>'
