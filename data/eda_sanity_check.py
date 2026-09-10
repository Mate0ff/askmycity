"""Quick sanity check on the cached data slice. Run: py data/eda_sanity_check.py"""

import pandas as pd

df = pd.read_csv(
    "data/austin_311_2025-09_2026-08.csv.gz",
    parse_dates=["sr_created_date", "sr_closed_date"],
)

print(f"rows: {len(df):,}")
print(f"date range: {df.sr_created_date.min()} to {df.sr_created_date.max()}")
print(f"duplicate sr_number: {df.sr_number.duplicated().sum()}")
print("\nnull counts:\n", df.isna().sum().to_string())
print("\ntop 5 categories:\n", df.sr_type_desc.value_counts().head(5).to_string())
