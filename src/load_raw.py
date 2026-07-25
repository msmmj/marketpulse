"""
Run all extraction scripts and write their results into Supabase raw tables.

Each write appends a `loaded_at` timestamp and inserts as new rows rather
than overwriting — this deliberately keeps every historical snapshot,
because the project's core question ("how do bank rates move over time
relative to lending conditions") only works if past snapshots are kept.
Deduplication and "latest value" logic belongs in dbt staging models,
not here — raw tables are allowed to be messy.

Run this manually for now: python src/load_raw.py
In production this is called by the Airflow DAG (dags/marketpulse_pipeline.py).
"""

import datetime

from extract_abs import fetch_data as fetch_abs_data
from extract_cdr_products import fetch_all_banks
from extract_cdr_product_rates import fetch_all_product_rates
from utils.db import get_engine, ensure_schema


def load_abs_cpi(engine) -> None:
    print("Fetching ABS CPI...")
    df = fetch_abs_data(
        dataflow_id="CPI",
        data_key="3.10001.10.50.M",
        start_period="2025",
        version="2.0.0",
    )
    df["loaded_at"] = datetime.datetime.now(datetime.UTC)

    df.to_sql(
        "abs_cpi",
        engine,
        schema="raw",
        if_exists="append",
        index=False,
    )
    print(f"Wrote {len(df)} rows to raw.abs_cpi")


def load_cdr_products(engine):
    """Fetch and load product listings. Returns the raw products
    DataFrame (before stringification) so the caller can reuse it for
    rate extraction, rather than fetching the product list twice.
    """
    print("Fetching CDR bank products...")
    df = fetch_all_banks()
    if df.empty:
        print("[WARN] No CDR products retrieved — skipping write.")
        return df

    products_for_rates = df.copy()

    df["loaded_at"] = datetime.datetime.now(datetime.UTC)

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

    return products_for_rates


def load_cdr_product_rates(engine, products_df) -> None:
    """Fetch rate detail for every product and load into raw.cdr_product_rates.
    This makes one API call per product, so it's noticeably slower than
    the product list fetch — expect this step to take a while with 140-200+
    products across 4 banks.
    """
    if products_df is None or products_df.empty:
        print("[WARN] No products available — skipping rate extraction.")
        return

    print(
        f"Fetching rate detail for {len(products_df)} products (this takes a while)..."
    )
    df = fetch_all_product_rates(products_df)

    if df.empty:
        print("[WARN] No rate data retrieved — skipping write.")
        return

    df["loaded_at"] = datetime.datetime.now(datetime.UTC)

    df.to_sql(
        "cdr_product_rates",
        engine,
        schema="raw",
        if_exists="append",
        index=False,
    )
    print(f"Wrote {len(df)} rows to raw.cdr_product_rates")


if __name__ == "__main__":
    engine = get_engine()
    ensure_schema(engine, "raw")

    load_abs_cpi(engine)
    products = load_cdr_products(engine)
    load_cdr_product_rates(engine, products)

    print("\nDone. Check the 'raw' schema in your Supabase Table Editor.")
