"""
Tests for extract_abs.py using mocked HTTP responses (via `responses` library)
so CI doesn't depend on the live ABS API being reachable or unchanged.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import responses  # noqa: E402
from extract_abs import fetch_data, inspect_dimensions  # noqa: E402

MOCK_CSV_RESPONSE = (
    "DATAFLOW,MEASURE,Measure,REGION,Region,TIME_PERIOD,OBS_VALUE\n"
    "ABS:CPI(2.0.0),1,Percentage change from previous year,10,Australia,2025-Q1,3.4\n"
    "ABS:CPI(2.0.0),1,Percentage change from previous year,10,Australia,2025-Q2,3.1\n"
)


@responses.activate
def test_fetch_data_parses_labelled_csv():
    responses.add(
        responses.GET,
        "https://data.api.abs.gov.au/rest/data/ABS,CPI,2.0.0/all",
        body=MOCK_CSV_RESPONSE,
        status=200,
        content_type="text/csv",
    )

    df = fetch_data(dataflow_id="CPI", data_key="all", version="2.0.0")

    assert len(df) == 2
    assert df.iloc[0]["OBS_VALUE"] == 3.4
    assert df.iloc[0]["Region"] == "Australia"
    assert df.iloc[0]["TIME_PERIOD"] == "2025-Q1"


def test_inspect_dimensions_runs_without_error(capsys):
    import pandas as pd

    df = pd.DataFrame(
        {
            "MEASURE": [1, 1],
            "Measure": ["Percentage change", "Percentage change"],
            "OBS_VALUE": [3.4, 3.1],
        }
    )
    inspect_dimensions(df)
    captured = capsys.readouterr()
    assert "MEASURE" in captured.out
    assert "OBS_VALUE" in captured.out