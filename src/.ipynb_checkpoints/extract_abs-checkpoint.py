"""
Extract data from the ABS Data API (SDMX-based REST service).

No API key required for the base Data API (beta). Docs:
https://www.abs.gov.au/about/data-services/application-programming-interfaces-apis/data-api-user-guide

IMPORTANT: SDMX-JSON has a specific nested structure (dimensions + observations
indexed by position, not by name). The parser below is written to match the
documented structure but has NOT been tested against a live response in this
environment (network access here is restricted). Run this locally, print the
raw JSON first (see `if __name__ == "__main__"` block), and adjust the parser
if the real shape differs from what's assumed here.
"""

import os
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

ABS_API_BASE = os.environ.get("ABS_API_BASE", "https://data.api.abs.gov.au/rest")


def fetch_dataflow_structure(dataflow_id: str, agency: str = "ABS") -> dict:
    """Fetch the Data Structure Definition (DSD) for a dataflow, including
    referenced codelists. Use this FIRST to work out valid dimension codes
    before constructing a data query — don't guess the dataKey.
    """
    url = f"{ABS_API_BASE}/datastructure/{agency}/{dataflow_id}"
    resp = requests.get(url, params={"references": "children"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_data(
    dataflow_id: str,
    data_key: str = "all",
    start_period: str | None = None,
    end_period: str | None = None,
    agency: str = "ABS",
) -> pd.DataFrame:
    """Fetch observations for a dataflow and return a tidy pandas DataFrame.

    Args:
        dataflow_id: e.g. "CPI", "LEND_HOUSING"
        data_key: dimension filter string, e.g. "1.2.1.4.A", or "all" for everything
        start_period / end_period: e.g. "2023", "2023-Q1"
    """
    url = f"{ABS_API_BASE}/data/{agency},{dataflow_id}/{data_key}"
    params = {"format": "jsondata"}
    if start_period:
        params["startPeriod"] = start_period
    if end_period:
        params["endPeriod"] = end_period

    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    return _parse_sdmx_json(payload)


def _parse_sdmx_json(payload: dict) -> pd.DataFrame:
    """Flatten SDMX-JSON into a tidy DataFrame.

    SDMX-JSON structure (2.1):
      payload["data"]["structures"][0]["dimensions"]["series"] -> list of series dims
      payload["data"]["structures"][0]["dimensions"]["observation"] -> time periods
      payload["data"]["dataSets"][0]["series"] -> dict keyed by series index
         each series has "observations" -> dict keyed by obs index -> [value, ...]

    This is a best-effort implementation based on the documented SDMX-JSON
    spec. Print `payload` locally on first run to confirm the real shape
    before trusting this output.
    """
    try:
        structures = payload["data"]["structures"][0]
        series_dims = structures["dimensions"]["series"]
        obs_dims = structures["dimensions"]["observation"]
        datasets = payload["data"]["dataSets"][0]["series"]
    except (KeyError, IndexError) as e:
        raise ValueError(
            f"Unexpected SDMX-JSON shape, adjust parser. Missing key: {e}. "
            "Print the raw payload to inspect its actual structure."
        )

    time_values = [v["id"] for v in obs_dims[0]["values"]]

    rows = []
    for series_key, series_val in datasets.items():
        # series_key looks like "0:1:2" -> index into each series dimension's values
        dim_indices = [int(i) for i in series_key.split(":")]
        dim_labels = {}
        for dim, idx in zip(series_dims, dim_indices):
            dim_labels[dim["id"]] = dim["values"][idx]["name"]

        for obs_key, obs_val in series_val["observations"].items():
            time_period = time_values[int(obs_key)]
            row = dict(dim_labels)
            row["time_period"] = time_period
            row["value"] = obs_val[0]
            rows.append(row)

    return pd.DataFrame(rows)


if __name__ == "__main__":
    # Quick manual check: fetch the last 8 quarters of CPI data.
    # Run this locally first and inspect the printed output before wiring
    # it into a database write.
    df = fetch_data(dataflow_id="CPI", data_key="all", start_period="2023")
    print(df.head(20))
    print(f"\nRows retrieved: {len(df)}")
