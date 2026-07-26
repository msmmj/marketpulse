# The Basis Point

**A live dashboard tracking how Australian banks actually price against
inflation — extraction, orchestration, transformation, testing, and
visualization, built entirely on free infrastructure.**

*(Internal codebase name: `marketpulse` — folder structure and internal
references below still use this name; it's just not the public-facing title.)*

![CI](https://github.com/msmmj/marketpulse/actions/workflows/ci.yml/badge.svg)

---

## The question this project answers

> Given where Australian inflation and lending conditions are heading, how
> competitively are the major banks actually pricing their loan and deposit
> products right now — and which bank comes out ahead in which category?

This is the same question comparison sites like Canstar and Finder answer
commercially, and the same question a bank's own pricing/strategy team asks
when benchmarking against competitors. This project answers it end-to-end,
from raw government and banking APIs through to an interactive dashboard,
without touching a single paid tool.

---

## Live dashboard

*(Screenshot placeholders below — replace with your own exported images from
the running Streamlit app before publishing. Suggested path: `docs/screenshots/`.)*

![Overview tab](docs/screenshots/overview.png)
![Key Insights tab](docs/screenshots/key_insights.png)
![Rate Comparison tab](docs/screenshots/rate_comparison.png)

---

## Architecture

```
                 ┌────────────────────┐        ┌──────────────────────┐
                 │  ABS Data API      │        │  CDR Bank APIs        │
                 │  (macro/CPI data)  │        │  (product + rate data)│
                 └─────────┬──────────┘        └──────────┬───────────┘
                           │                                │
                           └──────────────┬─────────────────┘
                                          ▼
                              Extraction (Python)
                        · SDMX/CSV parsing (ABS)
                        · Per-endpoint API version
                          auto-negotiation (CDR)
                        · Graceful per-bank failure
                          handling
                                          │
                                          ▼
                        Raw storage (Postgres / Supabase)
                        · Append-only, timestamped snapshots
                                          │
                                          ▼
                             dbt (staging → marts)
                        · Cleaning, type-casting
                        · Deduplication to latest snapshot
                        · 16 automated data tests
                                          │
                                          ▼
                          Streamlit dashboard
                        · Overview, Key Insights,
                          Rate Comparison, Product
                          Browser, CPI Trend

        Orchestration: Apache Airflow (Dockerized, run via GitHub Codespaces)
        CI/CD: GitHub Actions — lint, format-check, and unit tests on every push
```

---

## What was actually built

### 1. Extraction
- **`extract_abs.py`** — pulls Australian CPI (inflation) data from the ABS
  Data API. Uses the labelled-CSV response format rather than raw SDMX-JSON,
  which turned out to be far more reliable to parse. Filtered from an initial
  197,736-row unfiltered pull down to the correct 14-month headline series
  after manually inspecting the API's dimension structure.
- **`extract_cdr_products.py`** — pulls live product listings from 4 Australian
  banks' public Consumer Data Right (Open Banking) APIs: ANZ, Westpac, CBA,
  and Suncorp.
- **`extract_cdr_product_rates.py`** — pulls the actual interest rate detail
  for every product (a separate API call per product, ~200 calls per run).
  Includes **automatic API version negotiation**: each bank's product detail
  endpoint requires a different, undocumented API version, and each phrases
  its version-mismatch error differently. Rather than hardcoding four
  different configurations by hand, the extractor reads each bank's own
  error response, parses out the version it wants (handling three different
  real-world phrasings), retries automatically, and caches the working
  version — so it self-adapts if a bank changes its supported version again
  in future.

### 2. Storage
Free-tier hosted Postgres via Supabase. Every extraction run **appends** a
timestamped snapshot rather than overwriting — a deliberate design choice so
the pipeline builds a genuine history of how rates move over time, which is
the entire point of the analysis.

### 3. Transformation (dbt)
- **Staging models** — light cleaning: renaming, type casting, dropping
  redundant columns.
- **Mart models** — the real business logic: deduplicating each append-only
  raw table down to the latest snapshot per product/rate/month using window
  functions, then joining rates against product metadata.
- **16 automated data tests** (`not_null`, `unique`, `accepted_values`) —
  and genuinely caught a real bug during development: the CPI mart initially
  lacked the same deduplication logic as the product mart, which a `unique`
  test surfaced the moment a second pipeline run created real duplicate data
  to test against.

### 4. Orchestration
A fully Dockerized Apache Airflow setup (webserver, scheduler, its own
metadata database) running a 3-task DAG: extract → transform → test, in
that order, with dependency enforcement and retry logic. Built and run via
GitHub Codespaces after a local Windows machine's virtualization support
proved unstable mid-build — a deliberate infrastructure decision, not a
shortcut.

### 5. CI/CD
GitHub Actions runs linting (flake8), formatting checks (black), and a unit
test suite (pytest, with all external API calls mocked) on every push.

### 6. Visualization
A Streamlit dashboard with five tabs:
- **Overview** — headline metrics and an auto-generated sentence connecting
  CPI direction to average lending rate spread.
- **Key Insights** — for every rate category with enough bank coverage to
  compare meaningfully, automatically identifies the winning bank, the
  margin over the runner-up, and an overall "most competitive bank" leaderboard.
- **Rate Comparison** — filterable charts with consistent per-bank colour
  coding and auto-generated comparison sentences.
- **Product Browser** — searchable/filterable table of all tracked products.
- **CPI Trend** — detailed inflation trend and month-over-month movement.

---

## Key insights (example findings from a test run — re-run the pipeline for current numbers)

*Numbers below are illustrative, captured during development, and will differ
from a live run — that's the entire design point of the project. Replace this
section with your dashboard's current output before publishing.*

- Credit card cash advance and purchase rates clustered in the **18–21%**
  range across the three banks that reported them, with roughly a **2.5
  percentage point spread** between the cheapest and most expensive.
- Fixed-rate home loan pricing showed real competitive variation: a
  **~0.6 percentage point gap** between the most and least competitive bank
  in the same category — a meaningful difference on a mortgage over its
  lifetime.
- Not every bank competes in every category — this is a real finding in
  itself, not a data gap. Suncorp, for example, doesn't publish a
  market-linked home loan product, while it does compete aggressively in
  bonus savings rates.
- Headline CPI moved between roughly 1.9% and 4.6% year-on-year across the
  tracked window, with average advertised lending rates sitting several
  percentage points above the current inflation reading throughout — the
  kind of spread a lending-conditions analyst would actually track.

---

## Why this is relevant beyond a portfolio exercise

This mirrors a real, existing commercial function:
- **Comparison sites** (Canstar, Finder, RateCity) exist specifically to
  answer "which bank has the best rate right now" — this project answers
  the same question independently, end-to-end.
- **Bank pricing/strategy teams** benchmark their own rates against
  competitors using data structured exactly like this.
- **Fintechs building lending or refinancing products** use signals like
  "where is the market underpriced right now" to time customer acquisition.

The Consumer Data Right (Open Banking) data source used here is itself a
meaningful, under-used dataset — genuinely public, genuinely live, and
rarely appearing in portfolio projects, since most people default to Kaggle
CSVs instead of real regulatory APIs.

---

## Key learnings

**Technical:**
- Real-world APIs rarely behave like their documentation promises — CDR
  banks negotiate API versions inconsistently, and building automatic
  negotiation (rather than hardcoding per-bank config) was a better, more
  resilient engineering decision than it first appeared necessary.
- Tools that seem compatible on paper (dbt and Airflow) can have silently
  conflicting dependency trees — isolating dbt in its own virtual environment
  inside the same container solved this properly rather than papering over it.
- Automated tests don't just catch typos — a `unique` test caught a genuine
  logic gap (missing deduplication) that manual review had missed entirely.
- Encoding issues are still a real, current problem: a single UTF-16 vs
  UTF-8 mismatch in a `.gitignore` file (caused by PowerShell's default
  redirect encoding) silently caused an entire folder to vanish from version
  control for several sessions before being traced to its root cause.

**Process:**
- Scoping decisions are part of the engineering, not a failure of it —
  explicitly excluding a bank with a persistent, undiagnosable API bug (and
  documenting why) is a legitimate decision, not an incomplete project.
- Free-tier infrastructure has real, honest limits (Codespaces isn't
  meant to run 24/7) — being upfront about what a portfolio-scale build
  does and doesn't demonstrate is more credible than overstating it.

---

## Known limitations

- **AMP is excluded** from bank product/rate extraction — its CDR endpoint
  returns a persistent, unresolvable version-negotiation error regardless
  of the version requested, which points to a bug in AMP's own
  implementation rather than anything fixable from this side.
- **Individual banks occasionally have transient API failures** (observed
  with Westpac) — the pipeline logs a warning and continues rather than
  failing the whole run; a bank's absence from one snapshot doesn't mean
  permanent exclusion.
- **This is a portfolio-scale build**, not a production system: it runs on
  free-tier infrastructure, isn't deployed to run continuously, and doesn't
  handle the volume or reliability guarantees a real commercial deployment
  would require.

---

## Project structure

```
marketpulse/
  src/
    extract_abs.py                 # ABS CPI extraction
    extract_cdr_products.py        # CDR product listing extraction
    extract_cdr_product_rates.py   # CDR rate detail extraction w/ version negotiation
    load_raw.py                    # orchestrates all extraction -> Supabase
    utils/db.py                    # database connection helper
  marketpulse_dbt/
    models/staging/                # cleaning models
    models/marts/                  # business-logic models (dedup, joins)
  dags/
    marketpulse_pipeline.py        # Airflow DAG
  streamlit_app/
    app.py                         # dashboard
  tests/                           # pytest unit tests (mocked API responses)
  .github/workflows/ci.yml         # lint + test on every push
  Dockerfile, docker-compose.yaml  # Airflow container setup
  requirements.txt
  NOTES.md                         # running decision log
```

## Setup

1. Create a free Supabase project — copy the Session Pooler connection string
   (not the direct connection; it's IPv4-only and avoids a connectivity issue
   documented in `NOTES.md`).
2. Copy `.env.example` to `.env` and fill in `DATABASE_URL`.
3. `pip install -r requirements.txt`
4. `python src/load_raw.py` — runs full extraction and loads Supabase.
5. `cd marketpulse_dbt && dbt run && dbt test`
6. `streamlit run streamlit_app/app.py`
7. (Optional) `docker compose up airflow-init && docker compose up -d` for
   full orchestration via Airflow.

---

*Personal portfolio project. Not financial advice.*