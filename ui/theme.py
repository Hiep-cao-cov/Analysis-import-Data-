"""Streamlit theme — dark professional dashboard style."""

PAGE_BG = "#111315"
CARD_BG = "#1B1F23"
FILTER_PANEL_BG = "#171A1E"
CARD_BORDER = "#2E343C"

BRAND = {
    "primary": "#3B82F6",
    "accent": "#10B981",
    "accent_light": "#7DD3FC",
    "surface": PAGE_BG,
    "card": CARD_BG,
    "text": "#E5E7EB",
    "muted": "#9CA3AF",
    "border": CARD_BORDER,
    "success": "#10B981",
    "warning": "#F59E0B",
    "danger": "#EF4444",
    "tab_active": "#D1FAE5",
    "tab_inactive": "#2B3138",
}

# Chart palette
CHART = {
    "green": "#10B981",
    "red": "#EF4444",
    "blue": "#3B82F6",
    "yellow": "#F59E0B",
    "purple": "#A78BFA",
    "gray": "#9CA3AF",
    "pie": ["#10B981", "#3B82F6", "#F59E0B", "#A78BFA", "#22D3EE", "#9CA3AF"],
}

CUSTOM_CSS = f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Segoe+UI:wght@400;600;700&display=swap');

    html, body, [class*="css"] {{
        font-family: 'Segoe UI', system-ui, sans-serif;
    }}

    /* Main app background */
    .stApp {{
        background: radial-gradient(circle at top right, #20252B 0%, {PAGE_BG} 40%);
    }}
    section.main .block-container {{
        padding-top: 1.25rem;
        max-width: 100%;
    }}

    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header[data-testid="stHeader"] {{
        background: transparent;
    }}
    section.main .stMarkdown,
    section.main p,
    section.main span,
    section.main label,
    section.main h2,
    section.main h3 {{
        color: {BRAND["text"]};
    }}
    section.main h1:not(.dash-title) {{
        color: {BRAND["text"]};
    }}

    /* Sidebar (step 1) */
    section[data-testid="stSidebar"] {{
        background: #14181D;
        border-right: 1px solid {CARD_BORDER};
        font-size: 0.78rem;
    }}
    section[data-testid="stSidebar"] > div {{
        padding-top: 0.35rem;
    }}
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] label {{
        color: #E2E8F0 !important;
    }}
    /* Do not force gray on all p/span — it overrides expander title colors */
    section[data-testid="stSidebar"] [data-testid="stExpanderDetails"] p,
    section[data-testid="stSidebar"] [data-testid="stExpanderDetails"] span,
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        color: #CBD5E1 !important;
    }}
    /* Tight vertical spacing between sidebar expander sections */
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"],
    section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {{
        gap: 0.15rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="element-container"] {{
        margin-top: 0 !important;
        margin-bottom: 0.1rem !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {{
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
    }}
    section[data-testid="stSidebar"] label,
    section[data-testid="stSidebar"] label p {{
        font-size: 0.75rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{
        font-size: 0.68rem !important;
        line-height: 1.35 !important;
        margin-top: 0.15rem !important;
    }}
    section[data-testid="stSidebar"] hr {{
        border-color: rgba(255,255,255,0.12);
        margin: 0.4rem 0;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] hr {{
        margin: 0.2rem 0 !important;
    }}
    section[data-testid="stSidebar"] .stButton > button {{
        width: 100%;
        border-radius: 8px;
        border: 1px solid #3B434D;
        background: #20252C;
        color: #E5E7EB !important;
        font-weight: 600;
        font-size: 0.76rem !important;
        padding: 0.38rem 0.55rem;
        min-height: 0;
        transition: all 0.15s ease;
        text-align: left;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background: #2A313A;
        border-color: #4A5562;
    }}
    section[data-testid="stSidebar"] .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        border-color: #34D399 !important;
        color: #FFFFFF !important;
        text-shadow: 0 1px 1px rgba(0, 0, 0, 0.25);
        font-weight: 700;
        box-shadow: none;
    }}
    section[data-testid="stSidebar"] .stExpander {{
        border: 1px solid #3B434D;
        background: #1B1F23;
        border-radius: 8px;
        margin-top: 0 !important;
        margin-bottom: 0.1rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] {{
        margin: 0 !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        padding: 0.3rem 0.45rem !important;
        min-height: 0 !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {{
        padding: 0.25rem 0.45rem 0.35rem;
    }}
    /* Sidebar expander title typography */
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary span,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary label,
    section[data-testid="stSidebar"] [data-testid="stExpander"] summary * {{
        font-weight: 700 !important;
        font-size: 0.78rem !important;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] div[data-testid="stRadio"] label {{
        color: #E5E7EB !important;
        font-size: 0.74rem !important;
        padding: 0.15rem 0.1rem;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] div[data-testid="stRadio"] label[data-baseweb="radio"] {{
        background: #222831;
        border-color: #4B5563;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] div[data-testid="stRadio"] label p {{
        color: #F3F4F6 !important;
        font-weight: 500;
    }}
    section[data-testid="stSidebar"] [data-testid="stExpander"] div[data-testid="stRadio"] > div {{
        gap: 0.1rem;
    }}
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] > div > div {{
        background: #222831;
        border-color: #3B434D;
        border-radius: 6px;
        min-height: 1.75rem;
        font-size: 0.75rem;
    }}
    section[data-testid="stSidebar"] div[data-testid="stCheckbox"] label p {{
        font-size: 0.75rem !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stRadio"] label p {{
        font-size: 0.74rem !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] div[data-baseweb="select"] * {{
        color: #F9FAFB !important;
    }}
    section[data-testid="stSidebar"] div[data-testid="stSelectbox"] input {{
        color: #F9FAFB !important;
        -webkit-text-fill-color: #F9FAFB !important;
    }}
    div[role="listbox"] {{
        background: #1F252C !important;
        color: #F9FAFB !important;
    }}
    div[role="option"] {{
        color: #F9FAFB !important;
    }}
    /* Hide empty auto-generated sidebar wrappers to avoid blank blocks */
    section[data-testid="stSidebar"] div[data-testid="stVerticalBlock"] > div:empty {{
        display: none !important;
        margin: 0 !important;
        padding: 0 !important;
    }}

    .sidebar-brand {{
        text-align: left;
        padding: 0.55rem 0.65rem;
        margin-bottom: 0.35rem;
        background: #1B1F23;
        border-radius: 8px;
        border: 1px solid #2F363D;
    }}
    .sidebar-brand h2 {{ color: #F3F4F6 !important; font-size: 0.92rem; margin: 0.1rem 0 0.05rem 0; font-weight: 700; }}
    .sidebar-brand span {{ color: #9CA3AF !important; font-size: 0.65rem; letter-spacing: 0.04em; text-transform: uppercase; }}

    .sidebar-section-label {{
        color: #6EE7B7;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.06em;
        text-transform: uppercase;
        margin: 0.35rem 0 0.5rem 0;
    }}

    .sidebar-section-header {{
        background: #1B1F23;
        border: 1px solid #2F363D;
        border-radius: 12px 12px 0 0;
        border-bottom: none;
        padding: 0.65rem 0.75rem 0.4rem 0.75rem;
        margin-top: 0.65rem;
    }}
    .sidebar-section-body {{
        background: #171B20;
        border: 1px solid #2F363D;
        border-radius: 0 0 12px 12px;
        padding: 0.45rem 0.6rem 0.65rem 0.6rem;
        margin-bottom: 0.2rem;
    }}
    .sidebar-section-title {{
        font-size: 0.68rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: #9CA3AF !important;
        margin: 0 0 0.5rem 0.15rem;
        display: flex;
        align-items: center;
        gap: 0.4rem;
    }}
    .sidebar-title-left {{
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
    }}
    .sidebar-section-icon {{
        font-size: 0.9rem;
        line-height: 1;
    }}
    .sidebar-section-status {{
        margin-left: auto;
        font-size: 0.62rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        border-radius: 999px;
        padding: 0.12rem 0.45rem;
        border: 1px solid #3B434D;
        color: #D1D5DB !important;
        background: #2A313A;
    }}
    .sidebar-section-status.ok {{
        background: rgba(16,185,129,0.18);
        border-color: rgba(52,211,153,0.45);
        color: #A7F3D0 !important;
    }}
    .sidebar-section-status.pending {{
        background: rgba(245,158,11,0.16);
        border-color: rgba(245,158,11,0.45);
        color: #FCD34D !important;
    }}
    .sidebar-section-desc {{
        font-size: 0.72rem;
        color: #9CA3AF !important;
        margin: -0.2rem 0 0.55rem 0.15rem;
        line-height: 1.35;
    }}
    .sidebar-footer {{
        margin-top: 0.5rem;
        padding-top: 0.75rem;
        border-top: 1px solid #343B44;
    }}
    .sidebar-status {{
        background: #1B1F23;
        border: 1px solid #2F363D;
        border-radius: 10px;
        padding: 0.65rem 0.75rem;
        margin-bottom: 0.5rem;
    }}
    .sidebar-status-label {{
        font-size: 0.65rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: #9CA3AF !important;
        margin-bottom: 0.35rem;
    }}

    /* KPI row (step 2) */
    .kpi-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 1rem 1rem;
        margin-bottom: 0.8rem;
        min-height: 92px;
        box-shadow: 0 8px 18px rgba(0,0,0,0.22);
    }}
    .kpi-card .kpi-value {{
        font-size: 1.95rem;
        font-weight: 700;
        color: #F3F4F6;
        line-height: 1.2;
    }}
    .kpi-card .kpi-label {{
        font-size: 0.8rem;
        color: #9CA3AF;
        margin-top: 0.2rem;
    }}
    .kpi-label-green-lg {{
        font-size: 1.18rem;
        font-weight: 700;
        color: #10B981;
        margin-top: 0.25rem;
        line-height: 1.35;
    }}
    .kpi-label-blue-lg {{
        font-size: 1.18rem;
        font-weight: 700;
        color: #3B82F6;
        margin-top: 0.25rem;
        line-height: 1.35;
    }}
    .kpi-label-yellow-lg {{
        font-size: 1.18rem;
        font-weight: 700;
        color: #FACC15;
        margin-top: 0.25rem;
        line-height: 1.35;
    }}
    .kpi-card .kpi-delta {{
        font-size: 0.75rem;
        font-weight: 600;
        margin-top: 0.18rem;
    }}
    .kpi-card .kpi-delta.up {{ color: #34D399; }}
    .kpi-card .kpi-delta.down {{ color: #F87171; }}
    .kpi-icon {{
        position: absolute;
        top: 12px;
        right: 12px;
        width: 34px;
        height: 34px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.92rem;
    }}
    .kpi-icon.green {{ background: rgba(16,185,129,0.18); color: #34D399; }}
    .kpi-icon.red {{ background: rgba(239,68,68,0.18); color: #F87171; }}
    .kpi-icon.blue {{ background: rgba(59,130,246,0.18); color: #60A5FA; }}
    .kpi-icon.gray {{ background: rgba(156,163,175,0.18); color: #D1D5DB; }}

    /* Chart cards (step 3) */
    .chart-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 0.8rem 0.9rem 0.5rem 0.9rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 8px 18px rgba(0,0,0,0.2);
    }}
    .chart-card-title {{
        font-size: 0.95rem;
        font-weight: 700;
        color: #F3F4F6;
        margin: 0 0 0.45rem 0.15rem;
    }}
    .chart-card-title-lg {{
        font-size: 1.25rem;
        font-weight: 700;
        color: #F9FAFB;
        margin: 0 0 0.55rem 0.15rem;
        letter-spacing: 0.01em;
    }}
    .chart-subtitle {{
        font-size: 0.78rem;
        color: #9CA3AF;
        margin: -0.25rem 0 0.5rem 0.15rem;
    }}
    .chart-subtitle-lg {{
        font-size: 1.18rem;
        color: #D1D5DB;
        margin: -0.2rem 0 0.55rem 0.15rem;
        font-weight: 500;
    }}
    .chart-subtitle-lg strong {{
        color: #F3F4F6;
        font-weight: 700;
    }}
    .chart-footnote-yellow {{
        color: #FACC15 !important;
        -webkit-text-fill-color: #FACC15 !important;
        font-size: 0.8rem;
        line-height: 1.45;
        margin: 0.1rem 0 0.75rem 0.15rem;
    }}
    .chart-footnote-yellow strong {{
        color: #FDE047 !important;
        -webkit-text-fill-color: #FDE047 !important;
        font-weight: 700;
    }}
    /* Card-like style without empty HTML wrappers */
    section.main div[data-testid="stVerticalBlock"] > div:has(.chart-card-title),
    section.main div[data-testid="stVerticalBlock"] > div:has(.chart-card-title-lg) {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 0.8rem 0.9rem 0.5rem 0.9rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 8px 18px rgba(0,0,0,0.2);
    }}

    /* Content controls and tables */
    section.main div[data-testid="stSelectbox"] > div > div,
    section.main div[data-testid="stMultiSelect"] > div > div,
    section.main div[data-testid="stTextInput"] input {{
        background: #1C2229;
        border: 1px solid #38424D;
        color: #E5E7EB;
    }}
    section.main div[data-testid="stFileUploaderDropzone"] {{
        background: #1C2229;
        border: 1px dashed #4B5563;
    }}
    section.main div[data-testid="stDataFrame"] {{
        background: #151A20;
        border: 1px solid #334155;
        border-radius: 12px;
        padding: 0.35rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
    }}
    section.main div[data-testid="stDataFrame"] [data-testid="stDataFrameResizable"] {{
        border-radius: 10px;
    }}
    .detail-table-panel {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 14px;
        padding: 0.9rem 1rem 0.75rem 1rem;
        margin-top: 0.5rem;
        box-shadow: 0 10px 24px rgba(0,0,0,0.22);
    }}
    .detail-table-title {{
        font-size: 1rem;
        font-weight: 700;
        color: #F3F4F6;
        margin: 0;
    }}
    .detail-table-subtitle {{
        font-size: 0.78rem;
        color: #9CA3AF;
        margin: 0.2rem 0 0 0;
    }}
    .detail-table-badge {{
        display: inline-block;
        margin-left: 0.45rem;
        padding: 0.12rem 0.5rem;
        border-radius: 999px;
        font-size: 0.68rem;
        font-weight: 700;
        color: #A7F3D0;
        background: rgba(16,185,129,0.16);
        border: 1px solid rgba(16,185,129,0.35);
        vertical-align: middle;
    }}
    .detail-table-scroll-host {{
        overflow: auto;
        overflow-x: auto;
        overflow-y: auto;
        border: 1px solid #334155;
        border-radius: 12px;
        background: #151A20;
        margin-top: 0.55rem;
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
    }}
    .detail-table-scroll-host table {{
        width: max-content;
        min-width: 100%;
        border-collapse: collapse;
        margin: 0;
    }}
    .detail-table-scroll-host thead th {{
        position: sticky;
        top: 0;
        z-index: 2;
        box-shadow: 0 2px 6px rgba(0,0,0,0.35);
    }}
    .detail-table-scroll-host tbody tr:hover td {{
        background-color: #243041 !important;
    }}

    .analysis-placeholder {{
        background: {CARD_BG};
        border: 1px dashed #4B5563;
        border-radius: 14px;
        padding: 2rem 2.25rem;
        margin-top: 0.75rem;
        text-align: center;
        color: #D1D5DB;
    }}
    .analysis-placeholder-icon {{
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
    }}
    .analysis-placeholder h3 {{
        color: #F3F4F6;
        font-size: 1.15rem;
        margin: 0 0 0.75rem 0;
    }}
    .analysis-placeholder p {{
        color: #9CA3AF;
        font-size: 0.88rem;
        margin: 0.35rem 0;
    }}
    .analysis-placeholder ul {{
        text-align: left;
        display: inline-block;
        margin: 0.5rem auto 1rem auto;
        color: #D1D5DB;
        font-size: 0.86rem;
    }}
    .analysis-placeholder-meta {{
        font-size: 0.78rem !important;
        color: #6B7280 !important;
        margin-top: 1rem !important;
    }}

    .pill {{
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.75rem;
        font-weight: 600;
    }}
    .pill-ok {{ background: rgba(16,185,129,0.18); color: #A7F3D0; }}
    .pill-warn {{ background: rgba(245,158,11,0.18); color: #FCD34D; }}
    /* Header and tabs */
    .dash-header {{
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.85rem;
        padding: 0;
    }}
    .dash-header-inner {{
        background: linear-gradient(90deg, rgba(16, 185, 129, 0.12) 0%, rgba(27, 31, 35, 0.6) 100%);
        border: 1px solid rgba(52, 211, 153, 0.35);
        border-left: 4px solid #34D399;
        border-radius: 10px;
        padding: 0.85rem 1.1rem;
        width: 100%;
    }}
    .dash-header .dash-title,
    section.main .dash-header .dash-title,
    [data-testid="stAppViewContainer"] .dash-header .dash-title,
    [data-testid="stMarkdownContainer"] .dash-header .dash-title {{
        display: block;
        font-size: 1.8rem;
        font-weight: 800;
        color: #ECFDF5 !important;
        -webkit-text-fill-color: #ECFDF5 !important;
        margin: 0 !important;
        padding: 0 !important;
        letter-spacing: 0.01em;
        line-height: 1.2;
        opacity: 1 !important;
        filter: none !important;
    }}
    .dash-header .dash-subtitle,
    section.main .dash-header .dash-subtitle,
    [data-testid="stAppViewContainer"] .dash-header .dash-subtitle {{
        font-size: 0.92rem;
        color: #D1FAE5 !important;
        -webkit-text-fill-color: #D1FAE5 !important;
        margin: 0.35rem 0 0 0 !important;
        font-weight: 500;
        opacity: 1 !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        gap: 8px;
        background: transparent;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: {BRAND["tab_inactive"]};
        color: #D1D5DB;
        border-radius: 999px;
        padding: 0.38rem 1rem;
        font-weight: 600;
        border: 1px solid #3B434D;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {BRAND["tab_active"]} !important;
        color: #064E3B !important;
        border-color: #A7F3D0 !important;
    }}
    .top-chip-row {{
        display: flex;
        gap: 0.45rem;
        flex-wrap: wrap;
        margin: 0.15rem 0 0.7rem 0;
    }}
    .chip {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        box-sizing: border-box;
        width: 7.5rem;
        min-width: 7.5rem;
        max-width: 7.5rem;
        height: 2.1rem;
        padding: 0 0.45rem;
        border-radius: 999px;
        font-size: 0.94rem;
        border: 1px solid #4B5563;
        color: #3B82F6;
        background: #6B7280;
        font-weight: 600;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }}
    .chip-active {{
        background: #1E40AF;
        border-color: #FACC15;
        color: #FDE047;
    }}
    .info-card {{
        background: {CARD_BG};
        border: 1px solid {CARD_BORDER};
        border-radius: 12px;
        padding: 0.8rem 0.9rem;
        margin-bottom: 0.85rem;
        box-shadow: 0 8px 18px rgba(0,0,0,0.2);
    }}
    .info-card-title {{
        font-size: 0.95rem;
        font-weight: 700;
        color: #F3F4F6;
        margin: 0 0 0.45rem 0;
    }}
    .event-row {{
        padding: 0.45rem 0;
        border-bottom: 1px solid #2E343C;
        color: #D1D5DB;
        font-size: 0.78rem;
        line-height: 1.35;
    }}
    .event-row:last-child {{
        border-bottom: none;
    }}
    .supplier-row {{
        margin: 0.48rem 0;
    }}
    .supplier-row .label {{
        display: flex;
        justify-content: space-between;
        font-size: 0.76rem;
        color: #D1D5DB;
        margin-bottom: 0.25rem;
    }}
    .supplier-row .bar {{
        width: 100%;
        height: 7px;
        border-radius: 999px;
        background: #2B3138;
        overflow: hidden;
    }}
    .supplier-row .bar > span {{
        display: block;
        height: 100%;
        border-radius: 999px;
        background: linear-gradient(90deg, #10B981 0%, #3B82F6 100%);
    }}

    /* Force bright dashboard title (Streamlit markdown parent overrides) */
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] .dash-title {{
        color: #ECFDF5 !important;
        -webkit-text-fill-color: #ECFDF5 !important;
    }}
    [data-testid="stAppViewContainer"] [data-testid="stMarkdownContainer"] .dash-subtitle {{
        color: #D1FAE5 !important;
        -webkit-text-fill-color: #D1FAE5 !important;
    }}
</style>
"""


def inject_theme():
    import streamlit as st
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def kpi_card(
    value: str,
    label: str,
    icon: str,
    icon_class: str = "green",
    delta: str | None = None,
    delta_up: bool = True,
    *,
    label_variant: str | None = None,
):
    import html

    import streamlit as st

    delta_html = ""
    if delta:
        cls = "up" if delta_up else "down"
        delta_html = f'<div class="kpi-delta {cls}">{delta}</div>'
    label_cls = {
        "green-lg": "kpi-label-green-lg",
        "blue-lg": "kpi-label-blue-lg",
        "yellow-lg": "kpi-label-yellow-lg",
    }.get(label_variant or "", "kpi-label")
    safe_label = html.escape(str(label))
    st.markdown(
        f"""
        <div class="kpi-card">
            <div class="kpi-icon {icon_class}">{icon}</div>
            <div class="kpi-value">{value}</div>
            <div class="{label_cls}">{safe_label}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def chart_card_title(title: str, *, large: bool = False):
    import streamlit as st
    cls = "chart-card-title-lg" if large else "chart-card-title"
    st.markdown(f'<div class="{cls}">{title}</div>', unsafe_allow_html=True)


def chart_footnote(text: str) -> None:
    """Yellow chart note aligned under chart columns (Tab 1 pair captions)."""
    import re

    import streamlit as st

    escaped = text.replace("&", "&amp;").replace("<", "&lt;")
    body = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    st.markdown(f'<p class="chart-footnote-yellow">{body}</p>', unsafe_allow_html=True)


def chart_card_open():
    import streamlit as st
    st.markdown('<div class="chart-card">', unsafe_allow_html=True)


def chart_card_close():
    import streamlit as st
    st.markdown("</div>", unsafe_allow_html=True)


def info_card_open(title: str):
    import streamlit as st
    st.markdown(f'<div class="info-card"><div class="info-card-title">{title}</div>', unsafe_allow_html=True)


def info_card_close():
    import streamlit as st
    st.markdown("</div>", unsafe_allow_html=True)


def dashboard_header(title: str, subtitle: str = ""):
    import streamlit as st
    sub = f'<p class="dash-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        (
            '<div class="dash-header">'
            '<div class="dash-header-inner">'
            f'<div class="dash-title">{title}</div>'
            f"{sub}"
            "</div></div>"
        ),
        unsafe_allow_html=True,
    )


def filter_panel_open():
    import streamlit as st
    st.markdown('<div class="filter-panel">', unsafe_allow_html=True)


def filter_panel_close():
    import streamlit as st
    st.markdown("</div>", unsafe_allow_html=True)


def filter_label(text: str):
    import streamlit as st
    st.markdown(f'<div class="filter-panel-label">{text}</div>', unsafe_allow_html=True)


def hero(title: str, subtitle: str = ""):
    """Page title block for Train / Predict / Settings pages."""
    dashboard_header(title, subtitle)


def sidebar_section(
    title: str,
    description: str = "",
    step: str = "",
    icon: str = "",
    status_text: str = "",
    status_kind: str = "pending",
):
    import streamlit as st
    step_html = f'<span style="color:#5CE1E6;font-weight:800;">{step}</span> · ' if step else ""
    desc = f'<div class="sidebar-section-desc">{description}</div>' if description else ""
    icon_html = f'<span class="sidebar-section-icon">{icon}</span>' if icon else ""
    status_html = (
        f'<span class="sidebar-section-status {status_kind}">{status_text}</span>'
        if status_text
        else ""
    )
    st.markdown(
        (
            '<div class="sidebar-section-header">'
            f'<div class="sidebar-section-title"><span class="sidebar-title-left">{step_html}{icon_html}{title}</span>{status_html}</div>'
            f"{desc}</div>"
        ),
        unsafe_allow_html=True,
    )


def format_supplier_display_name(supplier: str, *, max_len: int | None = None) -> str:
    """Display supplier names in uppercase (e.g. KMC)."""
    text = str(supplier).strip().upper()
    if max_len is None or len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def format_supplier_sale_kpi_label(
    *,
    supplier: str,
    material_type: str,
    year: str | int,
    sale_channel: str,
) -> str:
    """Supplier volume KPI label, e.g. 'WANHUA PMDI sale in 2025 - indent'."""
    supplier_label = format_supplier_display_name(supplier)
    channel_label = str(sale_channel).strip().lower()
    return f"{supplier_label} {material_type} sale in {year} - {channel_label}"


def format_market_total_kpi_label(
    *,
    material_type: str,
    year: str | int,
    sale_channel: str,
) -> str:
    """Total market KPI label, e.g. 'PMDI market in 2025 - indent'."""
    channel_label = str(sale_channel).strip().lower()
    return f"{material_type} market in {year} - {channel_label}"


def format_supplier_share_kpi_label(
    *,
    supplier: str,
    material_type: str,
    year: str | int,
    sale_channel: str,
) -> str:
    """Market share KPI label, e.g. 'WANHUA share of PMDI in 2025 - indent'."""
    supplier_label = format_supplier_display_name(supplier)
    channel_label = str(sale_channel).strip().lower()
    return f"{supplier_label} share of {material_type} in {year} - {channel_label}"


def format_supplier_customers_kpi_label(
    *,
    supplier: str,
    year: str | int,
) -> str:
    """Tab 2 customer count KPI, e.g. 'Customer of BASF in year 2025'."""
    supplier_label = format_supplier_display_name(supplier)
    return f"Customer of {supplier_label} in year {year}"


def format_customer_display_name(name: str, *, max_len: int = 48) -> str:
    """Display customer name; truncate long company names for charts/KPIs."""
    text = str(name).strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def format_customer_import_kpi_label(
    *,
    customer_name: str,
    material_type: str,
    year: str | int,
    sale_channel: str,
) -> str:
    """Tab 3 import volume KPI, e.g. 'Samsung … PMDI import in 2025 - indent'."""
    customer_label = format_customer_display_name(customer_name, max_len=32)
    channel_label = str(sale_channel).strip().lower()
    return f"{customer_label} {material_type} import in {year} - {channel_label}"


def format_customer_suppliers_kpi_label(*, year: str | int) -> str:
    """Tab 3 supplier count KPI, e.g. 'Suppliers sourced in 2025'."""
    return f"Suppliers sourced in {year}"


def render_analysis_chip_row(
    *,
    dataset_label: str,
    sale_channel: str,
    sale_channel_options: list[str],
    year: str | int,
    supplier: str,
) -> None:
    """Top filter chips: dataset, sale channel, year, and supplier."""
    import html

    import streamlit as st

    def _chip(label: str, *, active: bool = False) -> str:
        cls = "chip chip-active" if active else "chip"
        return f'<span class="{cls}">{html.escape(str(label))}</span>'

    chips = [
        _chip("TDI", active=dataset_label == "TDI"),
        _chip("MDI", active=dataset_label in ("MDI", "PMDI")),
    ]
    for channel in sale_channel_options:
        chips.append(_chip(channel, active=channel == sale_channel))
    chips.append(_chip(str(year), active=True))
    chips.append(_chip(format_supplier_display_name(supplier), active=True))

    st.markdown(
        f'<div class="top-chip-row">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


def render_customer_analysis_chip_row(
    *,
    dataset_label: str,
    sale_channel: str,
    sale_channel_options: list[str],
    year: str | int,
    customer_name: str,
) -> None:
    """Top filter chips for Tab 3: dataset, sale channel, year, and customer."""
    import html

    import streamlit as st

    def _chip(label: str, *, active: bool = False) -> str:
        cls = "chip chip-active" if active else "chip"
        return f'<span class="{cls}">{html.escape(str(label))}</span>'

    chips = [
        _chip("TDI", active=dataset_label == "TDI"),
        _chip("MDI", active=dataset_label in ("MDI", "PMDI")),
    ]
    for channel in sale_channel_options:
        chips.append(_chip(channel, active=channel == sale_channel))
    chips.append(_chip(str(year), active=True))
    chips.append(
        _chip(format_customer_display_name(customer_name, max_len=36), active=True)
    )

    st.markdown(
        f'<div class="top-chip-row">{"".join(chips)}</div>',
        unsafe_allow_html=True,
    )


def sidebar_section_body_open():
    import streamlit as st
    st.markdown('<div class="sidebar-section-body">', unsafe_allow_html=True)


def sidebar_section_close():
    import streamlit as st
    st.markdown("</div>", unsafe_allow_html=True)


def section_header(title: str, subtitle: str = ""):
    import streamlit as st
    sub = f'<p style="color:{BRAND["muted"]};font-size:0.875rem;margin:0 0 0.75rem 0;">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<h3 style="color:{BRAND["text"]};font-size:1.05rem;font-weight:700;margin:1rem 0 0.25rem 0;">{title}</h3>{sub}',
        unsafe_allow_html=True,
    )
