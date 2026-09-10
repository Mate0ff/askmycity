"""Loads the cached civic dataset into a pandas DataFrame.

TODO(researcher-handoff): point REAL_DATA_FILE at the cached CSV/parquet the
researcher lands under data/, and update ACTIVE_SCHEMA in schema.py to match
its real columns and data/DATA_DICTIONARY.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from .schema import ACTIVE_SCHEMA, DatasetSchema

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"

# Filled in once the researcher's dataset lands (see TODO above).
REAL_DATA_FILE: Path | None = None


class DatasetNotReadyError(FileNotFoundError):
    """Raised when the cached dataset hasn't been checked into data/ yet."""


def load_dataset(
    path: Path | None = None, schema: DatasetSchema = ACTIVE_SCHEMA
) -> pd.DataFrame:
    """Load the cached dataset, parsing the schema's date column.

    Raises DatasetNotReadyError with a pointer to the data dictionary if no
    file has been wired up yet — callers (the Streamlit app, notably) should
    catch this and show a friendly "waiting on data" message rather than
    crash.
    """
    target = path or REAL_DATA_FILE
    if target is None:
        raise DatasetNotReadyError(
            "No dataset wired up yet. Once the cached file lands under data/, "
            "set askmycity.data.REAL_DATA_FILE (or pass `path=`) and see "
            "data/DATA_DICTIONARY.md for column definitions."
        )
    if not target.exists():
        raise DatasetNotReadyError(f"Expected dataset at {target}, but it doesn't exist yet.")

    df = pd.read_csv(target)
    if schema.date_col in df.columns:
        df[schema.date_col] = pd.to_datetime(df[schema.date_col], errors="coerce")
    return df
