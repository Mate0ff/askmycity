"""Tests for the Austin-311-specific load/clean step in data.py, against a
tiny synthetic CSV (not the real cached dataset) so these stay fast and
independent of the actual data's contents.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from askmycity.data import DatasetNotReadyError, load_dataset

CSV_HEADER = (
    "sr_number,sr_type_desc,sr_department_desc,sr_method_received_desc,"
    "sr_status_desc,sr_created_date,sr_closed_date,sr_location_zip_code,"
    "sr_location_council_district\n"
)


@pytest.fixture
def synthetic_csv(tmp_path: Path) -> Path:
    rows = [
        "1,ARR - Garbage,Austin Police,Phone,Closed,2026-01-01,2026-01-03,78701.0,3.0",
        "2,ARR - Garbage,Austin Police Department,Phone,Open,2026-01-05,,78701.0,3.0",
        "3,TPW - Pothole,Watershed Protection,E-Mail,Closed,2026-01-10,2026-01-11,,7.0",
        "4,Loose Dog,Austin Animal Services,Phone,CancelledTesting,2026-01-12,,78702.0,",
    ]
    path = tmp_path / "sample.csv"
    path.write_text(CSV_HEADER + "\n".join(rows) + "\n")
    return path


def test_load_dataset_missing_file_raises(tmp_path: Path):
    with pytest.raises(DatasetNotReadyError):
        load_dataset(path=tmp_path / "nope.csv.gz")


def test_department_aliases_merged(synthetic_csv):
    df = load_dataset(path=synthetic_csv)
    # "Austin Police" and "Austin Police Department" both normalize to the
    # same canonical spelling.
    police_rows = df[df["sr_number"] == 1].iloc[0], df[df["sr_number"] == 2].iloc[0]
    assert police_rows[0]["sr_department_desc"] == police_rows[1]["sr_department_desc"]
    assert df[df["sr_number"] == 3].iloc[0]["sr_department_desc"] == "Austin Watershed Protection"


def test_cancelled_testing_rows_dropped(synthetic_csv):
    df = load_dataset(path=synthetic_csv)
    assert 4 not in set(df["sr_number"])
    assert len(df) == 3


def test_zip_and_district_are_clean_strings(synthetic_csv):
    df = load_dataset(path=synthetic_csv)
    row = df[df["sr_number"] == 1].iloc[0]
    assert row["sr_location_zip_code"] == "78701"
    assert row["sr_location_council_district"] == "3"
    # Missing zip/district become a real NA, not the literal string "nan".
    missing_zip_row = df[df["sr_number"] == 3].iloc[0]
    assert pd.isna(missing_zip_row["sr_location_zip_code"])


def test_resolution_days_and_created_month_derived(synthetic_csv):
    df = load_dataset(path=synthetic_csv)
    closed_row = df[df["sr_number"] == 1].iloc[0]
    assert closed_row["resolution_days"] == 2
    open_row = df[df["sr_number"] == 2].iloc[0]
    assert pd.isna(open_row["resolution_days"])
    assert set(df["created_month"]) == {"2026-01"}
