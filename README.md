# 🚀 Smart Job Market Data Pipeline

A production-style, end-to-end data engineering pipeline that **extracts** Data Engineer job listings from a public API, **transforms** and enriches the data with Pandas, **loads** it into PostgreSQL, and surfaces actionable **insights** through SQL analytics.

Built as a portfolio showcase project demonstrating professional Python architecture, clean data engineering practices, and solid SQL skills.

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PIPELINE FLOW                            │
│                                                                 │
│  ┌──────────┐    JSON     ┌─────────────┐    CSV    ┌────────┐  │
│  │ Adzuna   │ ─────────► │  Transform  │ ────────► │  Load  │  │
│  │   API    │             │  (Pandas)   │           │  (PG)  │  │
│  └──────────┘             └─────────────┘           └────────┘  │
│       ↓                         ↓                       ↓       │
│  data/raw/              data/processed/          PostgreSQL DB  │
│  jobs_raw.json          jobs_cleaned.csv        (3 tables)      │
└─────────────────────────────────────────────────────────────────┘
```

**Three-phase pipeline:**

| Phase | Module | Input | Output |
|---|---|---|---|
| **Extract** | `src/extract.py` | Adzuna REST API | `data/raw/jobs_raw.json` |
| **Transform** | `src/transform.py` | Raw JSON | `data/processed/jobs_cleaned.csv` |
| **Load** | `src/load.py` | Cleaned CSV | PostgreSQL `job_market_db` |

**Database schema (normalised, 3NF):**

```
jobs            skills          job_skills
───────────     ──────────      ──────────────
job_id (PK)     skill_id (PK)   job_id   (FK → jobs)
title           skill_name      skill_id (FK → skills)
company
city
state_country
salary_min/max/avg
posted_date
...
```

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11+ |
| Data manipulation | Pandas, NumPy |
| API client | Requests |
| Database | PostgreSQL 14+ |
| DB adapter | psycopg2 |
| Config | YAML |
| Logging | Python `logging` module |

---

## 📁 Project Structure

```
job-data-pipeline/
│
├── data/
│   ├── raw/                    # Raw JSON from API
│   └── processed/              # Cleaned CSV (Pandas output)
│
├── src/
│   ├── __init__.py
│   ├── extract.py              # Phase 1 — API extraction
│   ├── transform.py            # Phase 2 — data cleaning & enrichment
│   ├── load.py                 # Phase 3 — PostgreSQL loading
│   └── utils.py                # Logging, config helpers, utilities
│
├── sql/
│   ├── schema.sql              # DDL — table & index definitions
│   └── queries.sql             # Analytical queries (insights)
│
├── logs/                       # Auto-created; one log file per run
│
├── config.yaml                 # Credentials & pipeline settings
├── main.py                     # Orchestrator — run from here
├── requirements.txt
└── README.md
```

---

## ⚙️ Setup

### Prerequisites

- Python 3.11+
- PostgreSQL 14+ (running locally or via Docker)
- A free [Adzuna API key](https://developer.adzuna.com/) *(optional — mock data works without one)*

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/job-data-pipeline.git
cd job-data-pipeline
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the pipeline

```bash
# config.yaml is already present — edit it with your credentials
```

Open `config.yaml` and fill in:

```yaml
api:
  app_id: "YOUR_ADZUNA_APP_ID"    # Leave as-is to use mock data
  app_key: "YOUR_ADZUNA_APP_KEY"
  use_mock_data: false             # Set to true to skip the API entirely

database:
  host: "localhost"
  port: 5432
  name: "job_market_db"
  user: "postgres"
  password: "YOUR_DB_PASSWORD"
```

### 5. Create the PostgreSQL database

```bash
psql -U postgres -c "CREATE DATABASE job_market_db;"
```

The schema is created **automatically** by `load.py`, but you can also run it manually:

```bash
psql -U postgres -d job_market_db -f sql/schema.sql
```

---

## ▶️ Running the Pipeline

### Full pipeline (all three phases)

```bash
python main.py
```

### Individual phases

```bash
python main.py --phase extract     # API → data/raw/
python main.py --phase transform   # data/raw/ → data/processed/
python main.py --phase load        # data/processed/ → PostgreSQL
```

### Without a database (extract + transform only)

```bash
python main.py --phase extract
python main.py --phase transform
# Inspect data/processed/jobs_cleaned.csv — no DB needed
```

### Custom config file

```bash
python main.py --config path/to/my_config.yaml
```

---

## 📊 Sample Outputs

### Cleaned CSV (`data/processed/jobs_cleaned.csv`)

| job_id | title | company | city | salary_avg | skills |
|---|---|---|---|---|---|
| mock_001 | Senior Data Engineer | TechCorp Inc | New York | 140000 | Python, SQL, AWS, Spark, Airflow, dbt, Snowflake, Docker, Kubernetes, ETL |
| mock_002 | Data Engineer | DataStream LLC | San Francisco | 127500 | Python, PySpark, Kafka, GCP, Terraform, BigQuery, Databricks |
| mock_005 | Data Engineer | FinTech Solutions | Chicago | 115000 | Python, SQL, Kafka, Redis, AWS, Redshift, Docker, Kubernetes, Airflow, REST API |

### Insight: Top 10 Skills

| Skill | Job Count | % of Listings |
|---|---|---|
| Python | 8 | 100.0% |
| SQL | 6 | 75.0% |
| AWS | 5 | 62.5% |
| Airflow | 4 | 50.0% |
| Docker | 4 | 50.0% |
| Kafka | 3 | 37.5% |
| dbt | 3 | 37.5% |
| Spark | 3 | 37.5% |

### Insight: Top Companies

| Company | Open Roles | Avg Salary |
|---|---|---|
| TechCorp Inc | 2 | $170,000 |
| DataStream LLC | 2 | $131,250 |
| Analytics Co | 1 | N/A |

### Insight: Jobs by City

| City | State | Job Count | Avg Salary |
|---|---|---|---|
| New York | NY | 2 | $170,000 |
| San Francisco | CA | 1 | $127,500 |
| Austin | TX | 1 | N/A |
| Seattle | WA | 1 | $122,500 |

---

## 🔍 Running SQL Queries

After the pipeline loads data, run the analytical queries directly:

```bash
psql -U postgres -d job_market_db -f sql/queries.sql
```

Or connect interactively:

```bash
psql -U postgres -d job_market_db

-- Example: top skills
SELECT s.skill_name, COUNT(*) AS job_count
FROM job_skills js
JOIN skills s ON js.skill_id = s.skill_id
GROUP BY s.skill_name
ORDER BY job_count DESC
LIMIT 10;
```

---

## 🔧 Key Engineering Decisions

**Idempotent loading** — Every INSERT uses `ON CONFLICT DO NOTHING`, so re-running the pipeline never creates duplicates.

**Modular phases** — Each phase (extract / transform / load) can be run independently via `--phase`, making debugging and testing straightforward.

**Mock data fallback** — The pipeline ships with realistic mock data so the full Extract → Transform → Load flow works without API credentials.

**Normalised schema** — Skills are stored in a dedicated `skills` table with a many-to-many bridge, avoiding data redundancy and enabling efficient aggregations.

**Structured logging** — Every run produces a timestamped log file in `logs/`, separate from console output.

---

## 🔮 Future Improvements

- [ ] **Incremental loading** — Track `last_extracted_at` in a metadata table and fetch only new listings on subsequent runs
- [ ] **Airflow/Prefect DAG** — Replace `main.py` orchestration with a proper workflow scheduler
- [ ] **dbt models** — Add a transformation layer with lineage and testing via dbt
- [ ] **Docker Compose** — Package the app + PostgreSQL into a one-command `docker compose up` environment
- [ ] **Unit tests** — Add pytest coverage for transformation functions and mock API responses
- [ ] **Dashboard** — Connect a Grafana or Metabase dashboard to the PostgreSQL database for live visualisation
- [ ] **Multi-source extraction** — Add LinkedIn, Indeed, or Glassdoor adapters behind a common interface
- [ ] **Salary normalisation** — Detect hourly vs. annual rates and normalise to annual USD

---

## 📝 License

MIT — free to use, modify, and distribute.

---

## 🙋 Author

Built as a portfolio project to demonstrate production-style data engineering patterns.  
Connect on [LinkedIn](https://linkedin.com/in/YOUR_PROFILE) or view more projects at [GitHub](https://github.com/YOUR_USERNAME).
