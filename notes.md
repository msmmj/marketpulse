# Development notes / decision log

## ABS CPI filtering (week 1)
Explored dimensions via `inspect_dimensions()`. Landed on data_key
`3.10001.10.50.M`:
- MEASURE=3: "Percentage change from previous year"
- INDEX=10001: "All groups CPI"
- TSEST=10: "Original" (not seasonally adjusted)
- REGION=50: "Australia"
- FREQ=M: Monthly

Exploration commands used to find these codes:
​```python
print(df[df['Index'].str.contains('all groups', case=False, na=False)][['INDEX', 'Index']].drop_duplicates())
print(df[df['Region'].str.contains('australia', case=False, na=False)][['REGION', 'Region']].drop_duplicates())

"""    
Code: 
print(df[df['Index'].str.contains('all groups', case=False, na=False)][['INDEX', 'Index']].drop_duplicates())
print(df[df['Region'].str.contains('australia', case=False, na=False)][['REGION', 'Region']].drop_duplicates())
print(df[['TSEST', 'Adjustment Type']].drop_duplicates())
print(df[['FREQ', 'Frequency']].drop_duplicates())

df_cpi = fetch_data(dataflow_id="CPI", data_key="3.10001.10.50.M", start_period="2025", version="2.0.0")
print(df_cpi[['TIME_PERIOD', 'OBS_VALUE']])
print(f"Rows: {len(df_cpi)}")
"""
## Airflow orchestration (week 3)
Built a Dockerized Airflow setup (LocalExecutor) running the full pipeline
as a DAG: extract_and_load_raw -> dbt_run -> dbt_test, scheduled daily.

Real issues hit and fixed, in order:
- dbt-core and Airflow have conflicting dependency trees (different
  required SQLAlchemy versions) - installing both in the same Python
  env broke Airflow's ORM models. Fixed by isolating dbt in its own
  virtualenv inside the image.
- SQLAlchemy version difference between local (2.0.x) and Airflow's
  bundled version (older) meant Connection.commit() wasn't available
  the same way - fixed by using engine.begin() instead, which works
  consistently across versions.
- dbt-postgres doesn't version in lockstep with dbt-core past 1.8 -
  adapters split into independent versioning. Left dbt-postgres
  unpinned so pip resolves a compatible version automatically.
- Airflow's webserver generated login redirects using "localhost"
  instead of the actual Codespaces URL - fixed with
  AIRFLOW__WEBSERVER__ENABLE_PROXY_FIX.
- A stray trailing hyphen in docker-compose.yaml
  (LocalExecutor- instead of LocalExecutor) silently broke the
  webserver's executor import.