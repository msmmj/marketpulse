"""
Database connection helper. Reads DATABASE_URL from environment.

Usage:
    from utils.db import get_engine
    engine = get_engine()
    df.to_sql("raw_abs_cpi", engine, if_exists="append", index=False, schema="raw")
"""

import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()


def get_engine():
    """Return a SQLAlchemy engine built from DATABASE_URL in .env.

    Raises a clear error if DATABASE_URL isn't set, rather than failing
    with an opaque SQLAlchemy error later.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is not set. Copy .env.example to .env and fill it in."
        )
    return create_engine(db_url)


def ensure_schema(engine, schema_name: str = "raw") -> None:
    """Create the given schema if it doesn't already exist. Supabase's
    default Postgres project only has 'public' by default — this creates
    a dedicated 'raw' schema so raw ingested data is clearly separated
    from anything dbt builds later (staging/marts will live elsewhere).
    """
    with engine.connect() as conn:
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {schema_name}"))
        conn.commit()