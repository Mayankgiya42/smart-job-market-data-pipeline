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
from pathlib import Path

import pandas as pd
import plotly.express as px
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
    page_title="Job Market Insights",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Custom CSS — clean, professional dark-accented theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600&family=DM+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'DM Sans', sans-serif;
    }

    /* Page background */
    .stApp {
        background-color: #0f1117;
        color: #e8eaf0;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background-color: #161b27;
        border-right: 1px solid #1e2535;
    }
    section[data-testid="stSidebar"] .stMarkdown p {
        color: #8892a4;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }

    /* Metric cards */
    div[data-testid="metric-container"] {
        background: linear-gradient(135deg, #1a2035 0%, #1e2840 100%);
        border: 1px solid #2a3550;
        border-radius: 12px;
        padding: 1.2rem 1.5rem;
    }
    div[data-testid="metric-container"] label {
        color: #6b7a99 !important;
        font-size: 0.75rem !important;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }
    div[data-testid="metric-container"] div[data-testid="stMetricValue"] {
        color: #e8eaf0 !important;
        font-size: 2rem !important;
        font-weight: 600;
        font-family: 'DM Mono', monospace;
    }

    /* Section headers */
    h2 {
        color: #c8cfe0;
        font-weight: 600;
        font-size: 1.05rem;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        border-bottom: 1px solid #1e2840;
        padding-bottom: 0.5rem;
        margin-top: 2rem !important;
    }

    /* Divider */
    hr {
        border-color: #1e2535;
    }

    /* DataFrame table */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
    }

    /* Selectbox / multiselect in sidebar */
    .stMultiSelect > div, .stSelectbox > div {
        background-color: #1a2035;
        border-color: #2a3550;
        border-radius: 8px;
    }

    /* Alert/info box */
    .stAlert {
        background-color: #1a2035;
        border-color: #2a3550;
        border-radius: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Config loader
# ---------------------------------------------------------------------------

@st.cache_data(ttl=0)  # Load once per session
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
    """
    Open a psycopg2 connection using credentials from config.

    Args:
        config: Loaded YAML configuration dictionary.

    Returns:
        psycopg2 connection object.

    Raises:
        psycopg2.OperationalError: If the connection fails.
    """
    db = config["database"]
    return psycopg2.connect(
        host=db["host"],
        port=db["port"],
        dbname=db["name"],
        user=db["user"],
        password=db["password"],
    )


@st.cache_data(ttl=300, show_spinner=False)  # Cache queries for 5 minutes
def run_query(sql: str, config_key: str) -> pd.DataFrame:
    """
    Execute a SQL query and return results as a DataFrame.
    Cached per unique SQL string; cache invalidates every 5 minutes.

    Args:
        sql:        SQL query string.
        config_key: Serialisable string used as part of the cache key
                    (pass the db name so different DBs don't share cache).

    Returns:
        Query result as a Pandas DataFrame.
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
# SQL query definitions
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
# Chart helpers
# ---------------------------------------------------------------------------

_CHART_BG    = "rgba(0,0,0,0)"   # transparent — respects page bg
_GRID_COLOR  = "#1e2840"
_ACCENT      = "#4f8ef7"
_ACCENT2     = "#34d399"
_TEXT_COLOR  = "#8892a4"
_TITLE_COLOR = "#c8cfe0"

_LAYOUT_BASE = dict(
    paper_bgcolor=_CHART_BG,
    plot_bgcolor=_CHART_BG,
    font=dict(family="DM Sans, sans-serif", color=_TEXT_COLOR, size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    xaxis=dict(gridcolor=_GRID_COLOR, linecolor=_GRID_COLOR, tickfont=dict(size=11)),
    yaxis=dict(gridcolor=_GRID_COLOR, linecolor=_GRID_COLOR, tickfont=dict(size=11)),
    hoverlabel=dict(bgcolor="#1a2035", bordercolor="#2a3550", font_size=12),
)


def chart_top_skills(df: pd.DataFrame):
    """Horizontal bar chart — top 10 skills by job count."""
    fig = px.bar(
        df.sort_values("job_count"),
        x="job_count",
        y="skill_name",
        orientation="h",
        color="job_count",
        color_continuous_scale=[[0, "#1e3a6e"], [1, _ACCENT]],
        labels={"job_count": "Jobs", "skill_name": ""},
        title="",
    )
    fig.update_layout(**_LAYOUT_BASE, coloraxis_showscale=False, height=360)
    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{x} jobs<extra></extra>")
    return fig


def chart_jobs_by_city(df: pd.DataFrame):
    """Vertical bar chart — job count by city."""
    fig = px.bar(
        df,
        x="city",
        y="job_count",
        color="job_count",
        color_continuous_scale=[[0, "#1a3a2e"], [1, _ACCENT2]],
        labels={"job_count": "Jobs", "city": ""},
        title="",
    )
    fig.update_layout(**_LAYOUT_BASE, coloraxis_showscale=False, height=340)
    fig.update_traces(hovertemplate="<b>%{x}</b><br>%{y} jobs<extra></extra>")
    return fig


def chart_salary_dist(df: pd.DataFrame):
    """Histogram of salary_avg."""
    fig = px.histogram(
        df,
        x="salary_avg",
        nbins=15,
        labels={"salary_avg": "Annual Salary (USD)", "count": "Jobs"},
        title="",
        color_discrete_sequence=[_ACCENT],
    )
    fig.update_layout(**_LAYOUT_BASE, bargap=0.05, height=340)
    fig.update_traces(hovertemplate="$%{x:,.0f}<br>%{y} jobs<extra></extra>")
    return fig


def chart_top_companies(df: pd.DataFrame):
    """Donut chart — top companies by job count."""
    fig = px.pie(
        df,
        names="company",
        values="job_count",
        hole=0.55,
        color_discrete_sequence=px.colors.sequential.Blues_r,
        title="",
    )
    fig.update_layout(
        paper_bgcolor=_CHART_BG,
        font=dict(family="DM Sans, sans-serif", color=_TEXT_COLOR, size=12),
        margin=dict(l=10, r=10, t=20, b=10),
        legend=dict(font=dict(color=_TEXT_COLOR, size=11)),
        hoverlabel=dict(bgcolor="#1a2035", bordercolor="#2a3550"),
        height=340,
    )
    fig.update_traces(
        textfont_color=_TEXT_COLOR,
        hovertemplate="<b>%{label}</b><br>%{value} jobs (%{percent})<extra></extra>",
    )
    return fig


# ---------------------------------------------------------------------------
# Sidebar filters
# ---------------------------------------------------------------------------

def render_sidebar(config: dict) -> tuple[list[str], list[str]]:
    """
    Render sidebar filter widgets and return selected values.

    Returns:
        Tuple of (selected_cities, selected_skills).
    """
    db_name = config["database"]["name"]

    with st.sidebar:
        st.markdown("## 🔍 Filters")
        st.markdown("---")

        # City filter
        st.markdown("**City**")
        cities_df = run_query(SQL_ALL_CITIES, db_name)
        all_cities = cities_df["city"].tolist()
        selected_cities = st.multiselect(
            label="city_filter",
            options=all_cities,
            default=[],
            placeholder="All cities",
            label_visibility="collapsed",
        )

        st.markdown("**Skill**")
        skills_df = run_query(SQL_ALL_SKILLS, db_name)
        all_skills = skills_df["skill_name"].tolist()
        selected_skills = st.multiselect(
            label="skill_filter",
            options=all_skills,
            default=[],
            placeholder="All skills",
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown(
            "<p style='color:#4a5568;font-size:0.72rem;'>Data refreshes every 5 min.<br>"
            "Run the pipeline to update.</p>",
            unsafe_allow_html=True,
        )

    return selected_cities, selected_skills


# ---------------------------------------------------------------------------
# Jobs table with filtering
# ---------------------------------------------------------------------------

def render_jobs_table(jobs_df: pd.DataFrame, cities: list[str], skills: list[str]) -> None:
    """
    Apply sidebar filters to the jobs DataFrame and render it as a table.

    Args:
        jobs_df:  Full jobs DataFrame from SQL_ALL_JOBS.
        cities:   List of selected city names (empty = all).
        skills:   List of selected skill names (empty = all).
    """
    filtered = jobs_df.copy()

    if cities:
        filtered = filtered[filtered["city"].isin(cities)]

    if skills:
        # Keep rows where ANY selected skill appears in the skills string
        mask = filtered["skills"].apply(
            lambda s: any(sk in s for sk in skills) if isinstance(s, str) else False
        )
        filtered = filtered[mask]

    total = len(filtered)
    st.markdown(f"## 📋 Job Listings &nbsp; <span style='color:#4f8ef7;font-size:0.85rem;font-weight:400;'>{total} result{'s' if total != 1 else ''}</span>", unsafe_allow_html=True)

    if filtered.empty:
        st.info("No jobs match the selected filters.")
        return

    # Tidy up display columns
    display = filtered[[
        "title", "company", "city", "state_country",
        "contract_type", "salary_avg", "posted_date", "skills",
    ]].copy()

    display.columns = [
        "Title", "Company", "City", "State/Country",
        "Contract", "Avg Salary ($)", "Posted", "Skills",
    ]
    display["Avg Salary ($)"] = display["Avg Salary ($)"].apply(
        lambda v: f"{v:,.0f}" if pd.notna(v) else "—"
    )
    display["Posted"] = pd.to_datetime(display["Posted"], errors="coerce").dt.strftime("%b %d, %Y")

    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Skills": st.column_config.TextColumn(width="large"),
            "Title":  st.column_config.TextColumn(width="medium"),
        },
    )


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------

def main() -> None:
    config  = load_config()
    db_name = config["database"]["name"]

    # ── Header ──────────────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='color:#e8eaf0;font-size:1.8rem;font-weight:600;"
        "letter-spacing:-0.01em;margin-bottom:0;'>📊 Job Market Insights Dashboard</h1>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<p style='color:#6b7a99;margin-top:0.25rem;'>Data Engineer roles · "
        f"Powered by <code style='background:#1a2035;padding:1px 6px;"
        f"border-radius:4px;color:#4f8ef7;'>{db_name}</code></p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    # ── Sidebar filters ──────────────────────────────────────────────────────
    selected_cities, selected_skills = render_sidebar(config)

    # ── Metrics ─────────────────────────────────────────────────────────────
    metrics_df = run_query(SQL_METRICS, db_name)
    if not metrics_df.empty:
        row = metrics_df.iloc[0]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Jobs",        int(row["total_jobs"]))
        c2.metric("Unique Companies",  int(row["unique_companies"]))
        c3.metric("Tracked Skills",    int(row["total_skills"]))
        c4.metric("Cities Covered",
                  run_query("SELECT COUNT(DISTINCT city) AS n FROM jobs;", db_name).iloc[0]["n"])

    st.markdown("---")

    # ── Charts row 1: Skills + Cities ────────────────────────────────────────
    st.markdown("## 📈 Market Overview")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("#### 🔧 Top 10 In-Demand Skills")
        skills_df = run_query(SQL_TOP_SKILLS, db_name)
        if not skills_df.empty:
            st.plotly_chart(chart_top_skills(skills_df), use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No skill data available yet.")

    with col_b:
        st.markdown("#### 📍 Jobs by City")
        cities_df = run_query(SQL_JOBS_BY_CITY, db_name)
        if not cities_df.empty:
            st.plotly_chart(chart_jobs_by_city(cities_df), use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No location data available yet.")

    # ── Charts row 2: Salary + Companies ─────────────────────────────────────
    col_c, col_d = st.columns(2)

    with col_c:
        st.markdown("#### 💰 Salary Distribution")
        salary_df = run_query(SQL_SALARY_DIST, db_name)
        if not salary_df.empty:
            # Show median callout
            median_sal = salary_df["salary_avg"].median()
            st.caption(f"Median: **${median_sal:,.0f}** / year &nbsp;·&nbsp; {len(salary_df)} listings with salary data")
            st.plotly_chart(chart_salary_dist(salary_df), use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No salary data available yet.")

    with col_d:
        st.markdown("#### 🏢 Jobs by Company")
        companies_df = run_query(SQL_TOP_COMPANIES, db_name)
        if not companies_df.empty:
            st.plotly_chart(chart_top_companies(companies_df), use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No company data available yet.")

    st.markdown("---")

    # ── Filterable jobs table ────────────────────────────────────────────────
    jobs_df = run_query(SQL_ALL_JOBS, db_name)
    render_jobs_table(jobs_df, selected_cities, selected_skills)


if __name__ == "__main__":
    main()
