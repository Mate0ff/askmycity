"""Loads the cached Austin 311 dataset into a pandas DataFrame, applying the
small set of cleanups documented in data/DATA_DICTIONARY.md so the agent's
tools see tidy columns:

- `sr_department_desc`: minority spelling variants of the same department
  (see DATA_DICTIONARY.md "Known quirks") are mapped to the majority
  spelling, e.g. "Austin Police" + "Austin Police Department" -> whichever
  spelling is more common in the data.
- `sr_location_zip_code` / `sr_location_council_district`: cast from float
  to a clean string (no trailing ".0") so exact-match tool filters work.
- `resolution_days`: derived — days between sr_created_date and
  sr_closed_date, null for requests not yet closed.
- `created_month`: derived — sr_created_date's month as "YYYY-MM", for
  chronological group_by (trend) questions.
- 4 `CancelledTesting` rows are dropped — the data dictionary flags these as
  test data that leaked into the production dataset, not real requests.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import ACTIVE_SCHEMA, DatasetSchema

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
REAL_DATA_FILE = DATA_DIR / "austin_311_2025-09_2026-08.csv.gz"

# Minority spelling -> majority spelling, per data/DATA_DICTIONARY.md.
_DEPARTMENT_ALIASES = {
    "Austin Police": "Austin Police Department",
    "Transportation and Public Works": "Austin Transportation and Public Works",
    "Watershed Protection": "Austin Watershed Protection",
    "Austin Energy Department": "Austin Energy",
    "Development Services Department": "Austin Development Services",
    "Animal Services Office": "Austin Animal Services",
    "Public Health": "Austin Public Health",
    "Parks & Recreation Department": "Austin Parks and Recreation",
    "Austin Fire Department": "Austin Fire",
    "(Tara) Financial Services Depart": "Austin Financial Services",
    "311-Client and Information Servi": "311-Client and Information Services",
    "Housing": "Austin Housing",
}

_TEST_STATUS_VALUES = ("CancelledTesting",)


class DatasetNotReadyError(FileNotFoundError):
    """Raised when the cached dataset hasn't been checked into data/ yet."""


def _zip_or_district_to_str(series: pd.Series) -> pd.Series:
    # float -> "78701" (not "78701.0"); missing stays a real NA (groupable
    # as its own bucket) rather than becoming the literal string "nan".
    return series.apply(lambda x: str(int(x)) if pd.notna(x) else None)


def load_dataset(
    path: Path | None = None, schema: DatasetSchema = ACTIVE_SCHEMA
) -> pd.DataFrame:
    """Load and clean the cached Austin 311 dataset.

    Raises DatasetNotReadyError if the cached file isn't present — callers
    (the Streamlit app, notably) should catch this and show a friendly
    "waiting on data" message rather than crash.
    """
    target = path or REAL_DATA_FILE
    if not target.exists():
        raise DatasetNotReadyError(
            f"Expected dataset at {target}, but it doesn't exist yet. "
            "See data/DATA_DICTIONARY.md / data/download_data.py."
        )

    df = pd.read_csv(target, parse_dates=["sr_created_date", "sr_closed_date"])

    df = df[~df["sr_status_desc"].isin(_TEST_STATUS_VALUES)].copy()

    df["sr_department_desc"] = df["sr_department_desc"].replace(_DEPARTMENT_ALIASES)
    df["sr_location_zip_code"] = _zip_or_district_to_str(df["sr_location_zip_code"])
    df["sr_location_council_district"] = _zip_or_district_to_str(
        df["sr_location_council_district"]
    )

    df["resolution_days"] = (df["sr_closed_date"] - df["sr_created_date"]).dt.days
    df["created_month"] = df[schema.date_col].dt.strftime("%Y-%m")

    return df
