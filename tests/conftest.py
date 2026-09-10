"""Shared test fixtures — a small synthetic 311-style dataframe.

Deliberately independent of the researcher's real dataset so tool/agent
tests can run before the real data lands (see src/askmycity/schema.py).
"""

from __future__ import annotations

import pandas as pd
import pytest

from askmycity.schema import ColumnSpec, DatasetSchema


@pytest.fixture
def sample_schema() -> DatasetSchema:
    return DatasetSchema(
        dataset_name="Testville 311 requests (synthetic fixture)",
        row_description="one row per service request",
        date_col="created_date",
        categorical_cols=(
            ColumnSpec("category", "type of request", ("pothole", "noise", "graffiti")),
            ColumnSpec("neighborhood", "neighborhood name", ("north", "south")),
        ),
        numeric_metric_cols=(ColumnSpec("resolution_days", "days to close"),),
    )


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "created_date": pd.to_datetime(
                [
                    "2026-01-01",
                    "2026-01-05",
                    "2026-01-10",
                    "2026-02-01",
                    "2026-02-15",
                    "2026-02-20",
                ]
            ),
            "category": ["pothole", "pothole", "noise", "graffiti", "pothole", "noise"],
            "neighborhood": ["north", "south", "north", "north", "south", "south"],
            "resolution_days": [2, 5, 1, 10, 3, 4],
        }
    )
