"""
Run both extraction scripts and write their results into Supabase raw tables.

Each write appends a `loaded_at` timestamp and inserts as new rows rather
than overwriting — this deliberately keeps every historical snapshot,
because the project's core question ("how do bank rates move over time
relative to lending conditions") only works if past snapshots are kept.
Deduplication and "latest value" logic belongs in dbt staging models
(week 2), not here — raw tables are allowed to be messy.

Run this manually for now: python src/load_raw.py
Later (week 3), Airflow will call this on a schedule instead.
"""

import datetime

from extract_abs import fetch_data as fetch_abs_data
from extract_cdr_products import fetch_all_banks
from utils.db import get_engine, ensure_schema


def load_abs_cpi(engine) -> None:
    print("Fetching ABS CPI...")
    df = fetch_abs_data(
        dataflow_id="CPI",
        data_key="3.10001.10.50.M",
        start_period="2025",
        version="2.0.0",
    )
    df["loaded_at"] = datetime.datetime.utcnow()

    df.to_sql(
        "abs_cpi",
        engine,
        schema="raw",
        if_exists="append",
        index=False,
    )
    print(f"Wrote {len(df)} rows to raw.abs_cpi")


def load_cdr_products(engine) -> None:
    print("Fetching CDR bank products...")
    df = fetch_all_banks()
    if df.empty:
        print("[WARN] No CDR products retrieved — skipping write.")
        return

    df["loaded_at"] = datetime.datetime.utcnow()

    # additionalInformation and cardArt are nested dict/list columns — Postgres
    # via to_sql can't store these directly, so stringify them.
    for col in ["additionalInformation", "cardArt"]:
        if col in df.columns:
            df[col] = df[col].astype(str)

    df.to_sql(
        "cdr_products",
        engine,
        schema="raw",
        if_exists="append",
        index=False,
    )
    print(f"Wrote {len(df)} rows to raw.cdr_products")


if __name__ == "__main__":
    engine = get_engine()
    ensure_schema(engine, "raw")

    load_abs_cpi(engine)
    load_cdr_products(engine)

    print("\nDone. Check the 'raw' schema in your Supabase Table Editor.")