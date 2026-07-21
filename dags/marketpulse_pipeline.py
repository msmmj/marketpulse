from datetime import datetime
from airflow import DAG
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "maxson",
    "retries": 1,
}

with DAG(
    dag_id="marketpulse_pipeline",
    description="Extract ABS + CDR data, load to Supabase, run dbt models and tests",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2026, 7, 1),
    catchup=False,
    tags=["marketpulse", "portfolio"],
) as dag:

    extract_and_load = BashOperator(
        task_id="extract_and_load_raw",
        bash_command="cd /opt/airflow/src && python load_raw.py",
    )

    dbt_run = BashOperator(
        task_id="dbt_run",
        bash_command="cd /opt/airflow/marketpulse_dbt && /home/airflow/dbt_venv/bin/dbt run",
    )

    dbt_test = BashOperator(
        task_id="dbt_test",
        bash_command="cd /opt/airflow/marketpulse_dbt && /home/airflow/dbt_venv/bin/dbt test",
    )

    extract_and_load >> dbt_run >> dbt_test