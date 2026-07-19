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