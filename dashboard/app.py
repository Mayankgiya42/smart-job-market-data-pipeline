"""
dashboard/app.py
----------------
Streamlit dashboard for the Smart Job Market Data Pipeline.

Connects to PostgreSQL (credentials from config.yaml), loads data via SQL,
and renders interactive charts, metrics, and a filterable job table.

Run:
    streamlit run dashboard/app.py

Must be run from the project root so config.yaml is found correctly.
"""

import os
import sys
import textwrap
from pathlib import Path
from datetime import datetime

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import psycopg2
import streamlit as st
import yaml

# ---------------------------------------------------------------------------
# Ensure project root is on the path (for config.yaml resolution)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Page config — must be the very first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Job Market Analytics | Enterprise",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — Premium Enterprise Theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');

    /* Color Palette Variables */
    :root {
        --bg-color: #0B1120;
        --sidebar-bg: #111827;
        --card-bg: rgba(30, 41, 59, 0.7);
        --card-border: #334155;
        --primary-blue: #3B82F6;
        --secondary-blue: #60A5FA;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --text-primary: #E5E7EB;
        --text-secondary: #94A3B8;
        --glass-bg: rgba(30, 41, 59, 0.4);
        --glass-border: rgba(51, 65, 85, 0.5);
    }

    /* Global Typography */
    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
        background-color: var(--bg-color);
        color: var(--text-primary);
    }

    /* Page background overrides */
    .stApp {
        background-color: var(--bg-color);
    }

    /* Top Padding adjustment */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 3rem !important;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: var(--sidebar-bg);
        border-right: 1px solid var(--card-border);
    }
    
    section[data-testid="stSidebar"] hr {
        border-color: var(--card-border);
        margin: 1.5rem 0;
    }

    /* Typography Hierarchy */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
        letter-spacing: -0.02em;
    }

    /* Headers */
    .section-header {
        font-size: 1.25rem;
        color: var(--text-primary);
        font-weight: 600;
        margin-top: 2.5rem;
        margin-bottom: 1.25rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .section-header::after {
        content: "";
        flex-grow: 1;
        height: 1px;
        background: linear-gradient(90deg, var(--card-border) 0%, transparent 100%);
        margin-left: 1rem;
    }

    /* Hero Section / Header */
    .hero-container {
        background: linear-gradient(145deg, var(--card-bg) 0%, rgba(11, 17, 32, 0) 100%);
        border: 1px solid var(--glass-border);
        border-radius: 16px;
        padding: 2rem;
        margin-bottom: 2rem;
        backdrop-filter: blur(10px);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    .hero-title {
        font-size: 2.25rem;
        font-weight: 700;
        margin: 0 0 0.5rem 0;
        background: linear-gradient(90deg, var(--text-primary), var(--secondary-blue));
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .hero-subtitle {
        color: var(--text-secondary);
        font-size: 1rem;
        margin: 0 0 1.5rem 0;
        font-weight: 500;
    }
    .badge-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
    }
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        background: var(--glass-bg);
        border: 1px solid var(--card-border);
        color: var(--text-secondary);
        transition: all 0.3s ease;
    }
    .status-badge:hover {
        background: var(--card-bg);
        border-color: var(--secondary-blue);
        color: var(--text-primary);
    }
    .dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
    }
    .dot-success { background-color: var(--success); box-shadow: 0 0 8px var(--success); }
    .dot-blue { background-color: var(--primary-blue); box-shadow: 0 0 8px var(--primary-blue); }

    /* Custom KPI Cards */
    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .kpi-card {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 1.5rem;
        backdrop-filter: blur(8px);
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; width: 100%; height: 3px;
        background: linear-gradient(90deg, var(--primary-blue), var(--secondary-blue));
        opacity: 0;
        transition: opacity 0.3s ease;
    }
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.2), 0 4px 6px -2px rgba(0, 0, 0, 0.1);
        border-color: var(--secondary-blue);
    }
    .kpi-card:hover::before {
        opacity: 1;
    }
    .kpi-title {
        color: var(--text-secondary);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.5rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    .kpi-value {
        color: var(--text-primary);
        font-size: 2.25rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
        line-height: 1.2;
    }
    .kpi-subtitle {
        color: var(--text-secondary);
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }

    /* Mini Info Cards */
    .mini-card-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
        gap: 1rem;
        margin-bottom: 2rem;
    }
    .mini-card {
        background: var(--sidebar-bg);
        border: 1px solid var(--card-border);
        border-radius: 8px;
        padding: 1rem;
        text-align: center;
        transition: all 0.2s ease;
    }
    .mini-card:hover {
        border-color: var(--primary-blue);
        background: var(--card-bg);
    }
    .mini-card-title {
        color: var(--text-secondary);
        font-size: 0.7rem;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 0.25rem;
    }
    .mini-card-val {
        color: var(--secondary-blue);
        font-size: 1.1rem;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    /* Charts Containers */
    .stPlotlyChart {
        background: var(--card-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 1rem;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        transition: border-color 0.3s ease;
    }
    .stPlotlyChart:hover {
        border-color: var(--glass-border);
    }

    /* Tables */
    .stDataFrame {
        background: var(--sidebar-bg);
        border: 1px solid var(--card-border);
        border-radius: 12px;
        padding: 0.5rem;
    }
    div[data-testid="stTable"] {
        background: transparent !important;
    }

    /* Footer */
    .dashboard-footer {
        margin-top: 4rem;
        padding-top: 2rem;
        border-top: 1px solid var(--card-border);
        display: flex;
        justify-content: space-between;
        color: var(--text-secondary);
        font-size: 0.8rem;
    }
    .footer-links span {
        margin-left: 1rem;
    }
    .footer-links strong {
        color: var(--text-primary);
    }

    /* Sidebar custom styling */
    .sidebar-section-title {
        color: var(--text-primary);
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.5rem;
    }
    
    .sys-info-box {
        background: rgba(0,0,0,0.2);
        border: 1px solid var(--card-border);
        border-radius: 8px;
        padding: 1rem;
        margin-top: 2rem;
    }
    .sys-info-row {
        display: flex;
        justify-content: space-between;
        margin-bottom: 0.5rem;
        font-size: 0.75rem;
    }
    .sys-info-label { color: var(--text-secondary); }
    .sys-info-val { color: var(--text-primary); font-family: 'JetBrains Mono', monospace; }
    
    /* Input overrides */
    .stMultiSelect > div > div {
        background-color: var(--sidebar-bg) !important;
        border-color: var(--card-border) !important;
    }
    .stSlider > div > div > div > div {
        background-color: var(--primary-blue) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------
@st.cache_data(ttl=0)
def load_config() -> dict:
    """Load config.yaml from the project root."""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        st.error(f"config.yaml not found at: {config_path}")
        st.stop()
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Database connection
# ---------------------------------------------------------------------------
def get_connection(config: dict):
    """Open a psycopg2 connection using credentials from config."""
    db = config["database"]
    return psycopg2.connect(
        host=db["host"],
        port=db["port"],
        dbname=db["name"],
        user=db["user"],
        password=db["password"],
    )


@st.cache_data(ttl=300, show_spinner=False)
def run_query(sql: str, config_key: str) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a DataFrame.
    Cached per unique SQL string; cache invalidates every 5 minutes.
    """
    config = load_config()
    try:
        conn = get_connection(config)
        df = pd.read_sql_query(sql, conn)
        conn.close()
        return df
    except psycopg2.OperationalError as exc:
        st.error(
            f"**Database connection failed.**\n\n"
            f"```\n{exc}\n```\n\n"
            "Check that PostgreSQL is running and your credentials in `config.yaml` are correct."
        )
        st.stop()
    except Exception as exc:
        st.error(f"Query error: {exc}")
        st.stop()


# ---------------------------------------------------------------------------
# SQL query definitions (UNCHANGED)
# ---------------------------------------------------------------------------
SQL_METRICS = """
    SELECT
        (SELECT COUNT(*)        FROM jobs)   AS total_jobs,
        (SELECT COUNT(DISTINCT company) FROM jobs
         WHERE company != 'Unknown Company') AS unique_companies,
        (SELECT COUNT(*)        FROM skills) AS total_skills;
"""

SQL_TOP_SKILLS = """
    SELECT s.skill_name, COUNT(js.job_id) AS job_count
    FROM job_skills js
    JOIN skills s ON js.skill_id = s.skill_id
    GROUP BY s.skill_name
    ORDER BY job_count DESC
    LIMIT 10;
"""

SQL_JOBS_BY_CITY = """
    SELECT city, COUNT(*) AS job_count
    FROM jobs
    GROUP BY city
    ORDER BY job_count DESC
    LIMIT 10;
"""

SQL_SALARY_DIST = """
    SELECT salary_avg
    FROM jobs
    WHERE salary_avg IS NOT NULL
    ORDER BY salary_avg;
"""

SQL_TOP_COMPANIES = """
    SELECT company, COUNT(*) AS job_count
    FROM jobs
    WHERE company != 'Unknown Company'
    GROUP BY company
    ORDER BY job_count DESC
    LIMIT 10;
"""

SQL_ALL_JOBS = """
    SELECT
        j.job_id,
        j.title,
        j.company,
        j.city,
        j.state_country,
        j.contract_type,
        j.salary_avg,
        j.posted_date,
        j.url,
        COALESCE(
            STRING_AGG(DISTINCT s.skill_name, ', ' ORDER BY s.skill_name),
            ''
        ) AS skills
    FROM jobs j
    LEFT JOIN job_skills js ON j.job_id = js.job_id
    LEFT JOIN skills s      ON js.skill_id = s.skill_id
    GROUP BY
        j.job_id, j.title, j.company, j.city, j.state_country,
        j.contract_type, j.salary_avg, j.posted_date, j.url
    ORDER BY j.posted_date DESC NULLS LAST;
"""

SQL_ALL_CITIES = "SELECT DISTINCT city FROM jobs ORDER BY city;"
SQL_ALL_SKILLS = "SELECT skill_name FROM skills ORDER BY skill_name;"

# ---------------------------------------------------------------------------
# UI Components
# ---------------------------------------------------------------------------
def render_header(db_name: str):
    """Render the premium hero section with high-end enterprise styling."""
    now_str = datetime.now().strftime("%b %d, %Y • %H:%M:%S")
    
    html = f"""
    <style>
        .enterprise-header {{
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
            border: 1px solid rgba(51, 65, 85, 0.5);
            border-top: 1px solid rgba(255, 255, 255, 0.08); /* Simulates glass edge */
            border-radius: 16px;
            padding: 32px 36px;
            margin-bottom: 24px;
            box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.2), 0 10px 10px -5px rgba(0, 0, 0, 0.1);
            backdrop-filter: blur(12px);
        }}
        .header-title-row {{
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 8px;
        }}
        .header-icon {{
            font-size: 2.2rem;
            line-height: 1;
            filter: drop-shadow(0 0 8px rgba(96, 165, 250, 0.4));
        }}
        .header-title {{
            font-size: 2.4rem;
            font-weight: 700;
            margin: 0;
            background: linear-gradient(90deg, #FFFFFF 0%, #93C5FD 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            letter-spacing: -0.02em;
        }}
        .header-subtitle {{
            color: #94A3B8;
            font-size: 1.1rem;
            font-weight: 400;
            margin: 0 0 28px 0;
            letter-spacing: 0.01em;
        }}
        .header-badges {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
        }}
        .premium-badge {{
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 6px 14px;
            border-radius: 8px;
            font-size: 0.75rem;
            font-weight: 600;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            transition: all 0.2s ease;
        }}
        .premium-badge:hover {{
            transform: translateY(-2px);
            filter: brightness(1.2);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        
        /* Specific Badge Tinting */
        .badge-live {{ background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.25); color: #34D399; }}
        .badge-db {{ background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.25); color: #60A5FA; }}
        .badge-api {{ background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.25); color: #FBBF24; }}
        .badge-etl {{ background: rgba(168, 85, 247, 0.1); border: 1px solid rgba(168, 85, 247, 0.25); color: #C084FC; }}
        .badge-time {{ background: rgba(148, 163, 184, 0.1); border: 1px solid rgba(148, 163, 184, 0.25); color: #E2E8F0; }}
        
        /* Glowing Indicator Dots */
        .pulse-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }}
        .pulse-green {{ background-color: #10B981; box-shadow: 0 0 10px #10B981, 0 0 4px #10B981; }}
        .pulse-blue {{ background-color: #3B82F6; box-shadow: 0 0 10px #3B82F6, 0 0 4px #3B82F6; }}
    </style>
    
    <div class="enterprise-header">
        <div class="header-title-row">
            <div class="header-icon">📊</div>
            <h1 class="header-title">Smart Job Market Analytics</h1>
        </div>
        <p class="header-subtitle">Real-Time Indian Data Engineering Job Market Intelligence</p>
        
        <div class="header-badges">
            <span class="premium-badge badge-live">
                <span class="pulse-dot pulse-green"></span> Live Data
            </span>
            <span class="premium-badge badge-db">
                <span class="pulse-dot pulse-blue"></span> PostgreSQL ({db_name})
            </span>
            <span class="premium-badge badge-api">
                🔌 Adzuna API
            </span>
            <span class="premium-badge badge-etl">
                ⚙️ Python ETL
            </span>
            <span class="premium-badge badge-time">
                ⏱️ {now_str}
            </span>
        </div>
    </div>
    """
    st.html(html)


def render_kpis(metrics_df: pd.DataFrame, jobs_df: pd.DataFrame):
    """Render the main KPI cards and mini analytics cards."""
    if metrics_df.empty or jobs_df.empty:
        return

    row = metrics_df.iloc[0]
    cities_count = jobs_df['city'].nunique()
    
    # --- Main KPIs ---
    html_kpis = f"""<div class="metric-grid">
    <div class="kpi-card">
        <div class="kpi-title">📄 Total Jobs</div>
        <div class="kpi-value">{int(row['total_jobs']):,}</div>
        <div class="kpi-subtitle">Active pipeline listings</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">🏢 Unique Companies</div>
        <div class="kpi-value">{int(row['unique_companies']):,}</div>
        <div class="kpi-subtitle">Hiring organizations</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">⚡ Tracked Skills</div>
        <div class="kpi-value">{int(row['total_skills']):,}</div>
        <div class="kpi-subtitle">Extracted technologies</div>
    </div>
    <div class="kpi-card">
        <div class="kpi-title">📍 Cities Covered</div>
        <div class="kpi-value">{cities_count:,}</div>
        <div class="kpi-subtitle">Geographic locations</div>
    </div>
</div>"""
    st.html(html_kpis)
    
    # --- Mini Analytics Cards (With Empty Data Handling) ---
    valid_salaries = jobs_df['salary_avg'].dropna()
    
    if not valid_salaries.empty and (valid_salaries != 0).any():
        avg_sal_str = f"${valid_salaries.mean():,.0f}"
        max_sal_str = f"${valid_salaries.max():,.0f}"
        min_sal_str = f"${valid_salaries.min():,.0f}"
    else:
        avg_sal_str = "N/A"
        max_sal_str = "N/A"
        min_sal_str = "N/A"
    
    top_city = jobs_df['city'].mode()[0] if not jobs_df['city'].empty else "N/A"
    
    comps = jobs_df[jobs_df['company'] != 'Unknown Company']['company']
    top_comp = comps.mode()[0] if not comps.empty else "N/A"
    
    if not jobs_df['posted_date'].dropna().empty:
        newest_date = pd.to_datetime(jobs_df['posted_date']).max().strftime('%b %d')
    else:
        newest_date = "N/A"

    html_mini = f"""<div class="mini-card-grid">
    <div class="mini-card">
        <div class="mini-card-title">Average Salary</div>
        <div class="mini-card-val">{avg_sal_str}</div>
    </div>
    <div class="mini-card">
        <div class="mini-card-title">Highest Salary</div>
        <div class="mini-card-val">{max_sal_str}</div>
    </div>
    <div class="mini-card">
        <div class="mini-card-title">Lowest Salary</div>
        <div class="mini-card-val">{min_sal_str}</div>
    </div>
    <div class="mini-card">
        <div class="mini-card-title">Top Hiring City</div>
        <div class="mini-card-val">{top_city}</div>
    </div>
    <div class="mini-card">
        <div class="mini-card-title">Top Company</div>
        <div class="mini-card-val">{top_comp}</div>
    </div>
    <div class="mini-card">
        <div class="mini-card-title">Newest Listing</div>
        <div class="mini-card-val">{newest_date}</div>
    </div>
</div>"""
    st.html(html_mini)


def render_footer():
    """Render a professional enterprise footer."""
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""<div class="dashboard-footer">
    <div>
        Smart Job Market Analytics &copy; {datetime.now().year}
    </div>
    <div class="footer-links">
        <span><strong>Source:</strong> Adzuna API</span>
        <span><strong>DB:</strong> PostgreSQL</span>
        <span><strong>ETL:</strong> Python</span>
        <span><strong>UI:</strong> Streamlit v2.0</span>
        <span><strong>Last Updated:</strong> {now_str}</span>
    </div>
</div>"""
    # FIX: Use st.html
    st.html(html)
# ---------------------------------------------------------------------------
# Plotly Chart Configurations
# ---------------------------------------------------------------------------
def apply_plotly_enterprise_layout(fig, title_text):
    """Applies a consistent dark enterprise layout to Plotly figures."""
    fig.update_layout(
        title=dict(text=f"<b>{title_text}</b>", font=dict(size=18, color="#E5E7EB", family="DM Sans")),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#94A3B8", family="DM Sans", size=12),
        margin=dict(l=20, r=20, t=60, b=20),
        hoverlabel=dict(bgcolor="#1E293B", bordercolor="#3B82F6", font_size=13, font_family="DM Sans"),
        xaxis=dict(gridcolor="#334155", zerolinecolor="#334155", title=""),
        yaxis=dict(gridcolor="#334155", zerolinecolor="#334155", title="")
    )
    # Hides the color gradient legend for a cleaner look
    fig.update_coloraxes(showscale=False) 
    return fig

def render_charts(db_name: str):
    """Renders the top 3 charts in a premium, space-optimized layout."""
    # st.html("<h3 style='color: #E5E7EB; margin-bottom: 20px; font-family: \"DM Sans\", sans-serif;'>📈 Market Intelligence Visualizations</h3>")
    
    # --- ROW 1: Full-Width Top Skills Chart (Vertical) ---
    skills_df = run_query(SQL_TOP_SKILLS, db_name)
    if not skills_df.empty:
        df_sorted = skills_df.sort_values("job_count", ascending=False)
        fig1 = px.bar(
            df_sorted, 
            x="skill_name", 
            y="job_count",
            text="job_count",
            color="job_count",
            color_continuous_scale=["#1E3A8A", "#3B82F6", "#93C5FD"] # Premium Blue gradient
        )
        fig1.update_traces(
            textposition="outside", 
            textfont=dict(color="#E5E7EB", family="JetBrains Mono", size=14),
            marker_line_width=0, 
            hovertemplate="<b>%{x}</b><br>%{y} postings<extra></extra>",
            cliponaxis=False # Prevents text cutoff at the top
        )
        fig1 = apply_plotly_enterprise_layout(fig1, "⚡ Top In-Demand Skills")
        fig1.update_layout(
            height=350, 
            yaxis_showgrid=True, 
            xaxis_showgrid=False,
            yaxis=dict(range=[0, df_sorted["job_count"].max() * 1.15]) # Room for labels
        )
        st.plotly_chart(fig1, use_container_width=True, config={"displayModeBar": False})

    # --- ROW 2: 50/50 Split for City and Companies (Horizontal) ---
    c1, c2 = st.columns(2)

    with c1:
        cities_df = run_query(SQL_JOBS_BY_CITY, db_name)
        if not cities_df.empty:
            df_sorted = cities_df.sort_values("job_count", ascending=True)
            fig2 = px.bar(
                df_sorted, 
                x="job_count", 
                y="city", 
                orientation="h",
                text="job_count",
                color="job_count",
                color_continuous_scale=["#064E3B", "#10B981", "#6EE7B7"] # Emerald gradient
            )
            fig2.update_traces(
                textposition="outside", 
                textfont=dict(color="#E5E7EB", family="JetBrains Mono"),
                marker_line_width=0,
                hovertemplate="<b>%{y}</b><br>%{x} jobs<extra></extra>",
                cliponaxis=False
            )
            fig2 = apply_plotly_enterprise_layout(fig2, "📍 Job Distribution by City")
            fig2.update_layout(
                height=380, 
                xaxis_showgrid=True, 
                yaxis_showgrid=False,
                xaxis=dict(range=[0, df_sorted["job_count"].max() * 1.2])
            )
            st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    with c2:
        companies_df = run_query(SQL_TOP_COMPANIES, db_name)
        if not companies_df.empty:
            df_sorted = companies_df.sort_values("job_count", ascending=True)
            
            # Ensure long company names don't break layout by truncating them for the axis
            df_sorted['company_short'] = df_sorted['company'].apply(lambda x: x[:22] + '...' if len(x) > 22 else x)
            
            fig3 = px.bar(
                df_sorted, 
                x="job_count", 
                y="company_short", 
                orientation="h",
                text="job_count",
                color="job_count",
                color_continuous_scale=["#4C1D95", "#8B5CF6", "#C4B5FD"], # Purple gradient
                custom_data=['company'] # Keep full name stored for hover
            )
            fig3.update_traces(
                textposition="outside", 
                textfont=dict(color="#E5E7EB", family="JetBrains Mono"),
                marker_line_width=0,
                hovertemplate="<b>%{customdata[0]}</b><br>%{x} open positions<extra></extra>",
                cliponaxis=False
            )
            fig3 = apply_plotly_enterprise_layout(fig3, "🏢 Top Hiring Organizations")
            fig3.update_layout(
                height=380, 
                xaxis_showgrid=True, 
                yaxis_showgrid=False,
                xaxis=dict(range=[0, df_sorted["job_count"].max() * 1.2])
            )
            st.plotly_chart(fig3, use_container_width=True, config={"displayModeBar": False})

# ---------------------------------------------------------------------------
# Sidebar Filters & Controls
# ---------------------------------------------------------------------------
def render_sidebar(config: dict, jobs_df: pd.DataFrame) -> dict:
    """Render redesigned enterprise sidebar filters and system info."""
    db_name = config["database"]["name"]
    filters = {}

    with st.sidebar:
        st.markdown("<div class='sidebar-section-title'>🔍 Global Filters</div>", unsafe_allow_html=True)

        # Base Data Extraction
        cities_df = run_query(SQL_ALL_CITIES, db_name)
        skills_df = run_query(SQL_ALL_SKILLS, db_name)
        
        all_cities = cities_df["city"].tolist()
        all_skills = skills_df["skill_name"].tolist()
        all_contracts = sorted(jobs_df["contract_type"].dropna().unique().tolist())
        
        min_sal = float(jobs_df["salary_avg"].min()) if not jobs_df["salary_avg"].empty and pd.notna(jobs_df["salary_avg"].min()) else 0.0
        max_sal = float(jobs_df["salary_avg"].max()) if not jobs_df["salary_avg"].empty and pd.notna(jobs_df["salary_avg"].max()) else 100000.0

        # Build UI
        filters["cities"] = st.multiselect("Location", options=all_cities, default=[], placeholder="Select cities...")
        filters["skills"] = st.multiselect("Required Skills", options=all_skills, default=[], placeholder="Select skills...")
        filters["contracts"] = st.multiselect("Contract Type", options=all_contracts, default=[], placeholder="Select types...")
        
        if min_sal < max_sal:
            filters["salary_range"] = st.slider(
                "Minimum Salary (USD)", 
                min_value=min_sal, 
                max_value=max_sal, 
                value=min_sal,
                step=1000.0,
                format="$%d"
            )
        else:
            filters["salary_range"] = 0.0

        # System Information Block
        now_str = datetime.now().strftime("%H:%M:%S UTC")
        html_sys_info = f"""
        <div class="sys-info-box">
            <div class="sidebar-section-title" style="margin-bottom:0.5rem;font-size:0.75rem;">⚙️ System Info</div>
            <div class="sys-info-row">
                <span class="sys-info-label">Database</span>
                <span class="sys-info-val">PostgreSQL</span>
            </div>
            <div class="sys-info-row">
                <span class="sys-info-label">Source</span>
                <span class="sys-info-val">Adzuna API</span>
            </div>
            <div class="sys-info-row">
                <span class="sys-info-label">Pipeline</span>
                <span class="sys-info-val">Python ETL</span>
            </div>
            <div class="sys-info-row">
                <span class="sys-info-label">Status</span>
                <span class="sys-info-val" style="color:var(--success);">● Online</span>
            </div>
            <div class="sys-info-row">
                <span class="sys-info-label">Last Sync</span>
                <span class="sys-info-val">{now_str}</span>
            </div>
        </div>
        """
        st.markdown(html_sys_info, unsafe_allow_html=True)

    return filters

# ---------------------------------------------------------------------------
# Jobs Table (Enhanced Data Grid)
# ---------------------------------------------------------------------------
def render_jobs_table(jobs_df: pd.DataFrame, filters: dict) -> None:
    """Filter locally and render the premium data grid."""
    
    # 1. Apply Filters
    filtered = jobs_df.copy()

    if filters.get("cities"):
        filtered = filtered[filtered["city"].isin(filters["cities"])]

    if filters.get("skills"):
        mask = filtered["skills"].apply(
            lambda s: any(sk in s for sk in filters["skills"]) if isinstance(s, str) else False
        )
        filtered = filtered[mask]
        
    if filters.get("contracts"):
        filtered = filtered[filtered["contract_type"].isin(filters["contracts"])]
        
    if filters.get("salary_range"):
        min_req = filters["salary_range"]
        # Keep jobs where salary >= min_req OR salary is null (to not exclude unlisted salaries entirely, 
        # but typical behavior is strictly filtering. We will do strict filtering).
        filtered = filtered[filtered["salary_avg"] >= min_req]

    # 2. Render Header
    total = len(filtered)
    st.markdown("<div class='section-header'>📋 Detailed Job Listings</div>", unsafe_allow_html=True)
    st.caption(f"Showing **{total}** matching records based on current filter criteria.")

    if filtered.empty:
        st.warning("No jobs match the selected criteria. Please adjust your filters.")
        return

    # 3. Format Data for Display
    display = filtered[[
        "title", "company", "city", "contract_type", "salary_avg", "posted_date", "skills", "url"
    ]].copy()

    display.columns = [
        "Job Title", "Company", "Location", "Contract", "Est. Salary", "Date Posted", "Extracted Skills", "Action"
    ]
    
    # Clean up formatting
    display["Est. Salary"] = display["Est. Salary"].apply(
        lambda v: f"${v:,.0f}" if pd.notna(v) else "Not Specified"
    )
    display["Date Posted"] = pd.to_datetime(display["Date Posted"], errors="coerce").dt.strftime("%Y-%m-%d")

    # 4. Render Table with Streamlit v1.30+ column configs
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "Job Title": st.column_config.TextColumn("Job Title", width="medium"),
            "Company": st.column_config.TextColumn("Company", width="medium"),
            "Extracted Skills": st.column_config.TextColumn("Extracted Skills", width="large"),
            "Action": st.column_config.LinkColumn(
                "Apply Link",
                help="Click to view original posting",
                validate="^http.*",
                max_chars=100,
                display_text="View Post ↗"
            ),
        },
    )


# ---------------------------------------------------------------------------
# Main Application Architecture
# ---------------------------------------------------------------------------
def main() -> None:
    config = load_config()
    db_name = config["database"]["name"]

    # Pre-fetch Base Data
    jobs_df = run_query(SQL_ALL_JOBS, db_name)
    metrics_df = run_query(SQL_METRICS, db_name)

    # UI Rendering Pipeline
    render_header(db_name)
    
    filters = render_sidebar(config, jobs_df)
    
    render_kpis(metrics_df, jobs_df)

    # Visualizations Layer
    st.markdown("<div class='section-header'>📈 Market Intelligence Visualizations</div>", unsafe_allow_html=True)
    
    render_charts(db_name)
    
    # Details Data Grid
    render_jobs_table(jobs_df, filters)
    
    render_footer()


if __name__ == "__main__":
    main()