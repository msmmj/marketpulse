# MarketPulse

An end-to-end data pipeline combining Australian macroeconomic data (ABS Data API)
with Australian banking product data (Consumer Data Right Product Reference APIs),
built to demonstrate data engineering skills: API extraction, orchestration, dbt
transformation, testing, and CI/CD — all on free infrastructure.

**Status:** personal portfolio project, under active build. Not a production system.

## What this answers

Given where lending conditions and inflation are heading (ABS), how competitively
are Australian banks pricing home loan and savings products right now, and how
does that move over time (CDR Product Reference Data)?

## Architecture

```
ABS Data API  ---\
                  >--  extraction (Python)  -->  raw storage (Postgres/Supabase)
CDR Bank APIs ---/                                        |
                                                            v
                                                    dbt (staging -> marts)
                                                            |
                                                            v
                                                   Streamlit dashboard

Orchestration: Airflow (added week 3)
CI/CD: GitHub Actions (lint + test on every push)
```

## Project structure

```
marketpulse/
  src/
    extract_abs.py          # pulls CPI / Lending Indicators from ABS Data API
    extract_cdr_products.py # pulls product data from CDR banking APIs
    utils/
      db.py                 # database connection helper
  tests/
    test_extract_abs.py
    test_extract_cdr_products.py
  .github/workflows/
    ci.yml                  # lint + pytest on every push
  requirements.txt
  .env.example
  .gitignore
```

## Setup (week 1)

1. Create a free Supabase project (supabase.com) — this gives you a hosted Postgres
   instance. Copy the connection string.
2. Copy `.env.example` to `.env` and fill in your `DATABASE_URL`.
3. `python -m venv venv && source venv/bin/activate`
4. `pip install -r requirements.txt`
5. Run `python src/extract_abs.py` — this will hit the ABS Data API and print
   what it retrieves. **Expect to need to debug the JSON parsing against the
   real response the first time** — SDMX-JSON has a specific nested shape and
   the parser here is a documented best-effort, not tested against a live call.
6. Run `python src/extract_cdr_products.py` — this loops over a small list of
   bank CDR endpoints and pulls their current product lists.
7. Once both scripts run cleanly, wire them to write into your Supabase raw
   tables instead of just printing (see `src/utils/db.py`).

## What's deliberately NOT here yet

Per the roadmap: dbt models, Airflow orchestration, and the Streamlit dashboard
are weeks 2-5. This first commit is intentionally just extraction + tests + CI,
so you have something working and demoable (via git history) at every stage,
not one big commit at the end.

## Honesty note for interviews

This project uses free-tier infrastructure and public APIs. It demonstrates the
skills (pipeline design, API integration, dbt modelling, CI/CD, orchestration)
at a scale appropriate to a portfolio project — it is not a claim of production-
scale data engineering experience.
