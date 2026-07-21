# Extends the official Airflow image with this project's dependencies.
#
# IMPORTANT: dbt-core and Airflow have conflicting dependency trees
# (different required SQLAlchemy versions, among others). Installing
# both into the same Python environment breaks Airflow's internal
# database models. The fix is to install dbt into its own isolated
# virtual environment inside the image, rather than alongside
# Airflow's own packages.

FROM apache/airflow:2.9.3-python3.12

USER airflow

# Only install what our scripts need that Airflow doesn't already
# provide (Airflow already ships compatible SQLAlchemy + psycopg2 via
# its own postgres provider — reinstalling those is what caused the
# conflict). Use Airflow's own constraints file to keep everything
# else compatible with what Airflow expects.
RUN pip install --no-cache-dir requests pandas python-dotenv \
    --constraint "https://raw.githubusercontent.com/apache/airflow/constraints-2.9.3/constraints-3.12.txt"

# dbt gets its own isolated virtual environment, completely separate
# from Airflow's Python packages. Pinned to match the dbt version used
# on the local development machine (1.12.x) — dbt 1.8 vs 1.12 have
# different schema.yml test argument syntax (the `arguments:` nesting),
# so mismatched versions between local dev and this container cause
# confusing, version-specific failures.
RUN python -m venv /home/airflow/dbt_venv && \
    /home/airflow/dbt_venv/bin/pip install --no-cache-dir dbt-core==1.12.* dbt-postgres