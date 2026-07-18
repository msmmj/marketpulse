"""
Extract data from the ABS Data API (SDMX-based REST service).

No API key required for the base Data API (beta). Docs:
https://www.abs.gov.au/about/data-services/application-programming-interfaces-apis/data-api-user-guide

This uses the format=csvfilewithlabels response format (ABS's own documented
approach), which returns a CSV with a dimension-code column immediately
followed by a human-readable label column for each dimension (e.g. MEASURE,
"Measure", REGION, "Region"...). This avoids parsing raw SDMX-JSON, which
requires manually cross-referencing codelists — the labelled CSV format
gives you readable values directly.
"""

import os
import io
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ABS_API_BASE = os.environ.get("ABS_API_BASE", "https://data.api.abs.gov.au/rest")


def fetch_data(
    dataflow_id: str,
    data_key: str = "all",
    start_period: str | None = None,
    end_period: str | None = None,
    agency: str = "ABS",
    version: str | None = None,
) -> pd.DataFrame:
    """Fetch observations for a dataflow as a labelled CSV, returned as a
    tidy pandas DataFrame with both code and human-readable label columns.

    Args:
        dataflow_id: e.g. "CPI", "LEND_HOUSING"
        data_key: dimension filter string (dot-separated codes), or "all"
        start_period / end_period: e.g. "2024", "2024-Q1"
        version: dataflow version, e.g. "2.0.0" for the current CPI series.
            Leave as None to get the latest version automatically.

    IMPORTANT: start with data_key="all" and a narrow start_period/end_period
    (e.g. just the last 1-2 periods) to inspect what dimension label columns
    exist and what values they take, BEFORE filtering to a specific series.
    Requesting "all" across all history returns a very large response.
    """
    version_str = f",{version}" if version else ""
    url = f"{ABS_API_BASE}/data/{agency},{dataflow_id}{version_str}/{data_key}"
    params = {"format": "csvfilewithlabels"}
    if start_period:
        params["startPeriod"] = start_period
    if end_period:
        params["endPeriod"] = end_period

    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()

    return pd.read_csv(io.StringIO(resp.text))


def inspect_dimensions(df: pd.DataFrame) -> None:
    """Print every column and its unique values (or a count, if there are
    too many to usefully print) — use this to figure out which codes to
    filter on before building a narrow data_key.
    """
    for col in df.columns:
        unique_vals = df[col].unique()
        if len(unique_vals) <= 30:
            print(f"\n{col} ({len(unique_vals)} unique values):")
            print(unique_vals)
        else:
            print(f"\n{col}: {len(unique_vals)} unique values (too many to list)")


if __name__ == "__main__":
    df = fetch_data(
        dataflow_id="CPI",
        data_key="3.10001.10.50.M",
        start_period="2025",
        version="2.0.0",
    )
    print(df.sort_values("TIME_PERIOD"))
    print(f"\nRows retrieved: {len(df)}")

"""    
print(df[df['Index'].str.contains('all groups', case=False, na=False)][['INDEX', 'Index']].drop_duplicates())
print(df[df['Region'].str.contains('australia', case=False, na=False)][['REGION', 'Region']].drop_duplicates())
print(df[['TSEST', 'Adjustment Type']].drop_duplicates())
print(df[['FREQ', 'Frequency']].drop_duplicates())

df_cpi = fetch_data(dataflow_id="CPI", data_key="3.10001.10.50.M", start_period="2025", version="2.0.0")
print(df_cpi[['TIME_PERIOD', 'OBS_VALUE']])
print(f"Rows: {len(df_cpi)}")
"""