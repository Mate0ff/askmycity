"""Fetch a manageable slice of the Austin 311 Public Data dataset and cache it locally.

Source: City of Austin Open Data Portal (Socrata), dataset "Austin 311 Public Data"
  https://data.austintexas.gov/Utilities-and-City-Services/Austin-311-Public-Data/xwdj-i9he
  SODA API endpoint: https://data.austintexas.gov/resource/xwdj-i9he.json

No API key/auth is required for this volume of read-only access. An optional Socrata
app token (free to register, raises the throttling ceiling) can be set via the
SOCRATA_APP_TOKEN env var, but the script works fine without one.

We pull one fixed, full-calendar-year window (Sep 2025 - Aug 2026) rather than "trailing
N months from today", so the cached file is reproducible and doesn't include a partial
in-progress month that would put a misleading dip at the end of every trend chart.

We also select only the columns useful for aggregate Q&A (category, department, status,
dates, and coarse location), dropping verbose/redundant fields the source table carries
(street address text, state-plane X/Y, map page/tile, a duplicate lat/long "point"
object) to keep the cached file well under the 20MB target.

Usage:
    py data/download_data.py
Output:
    data/austin_311_2025-09_2026-08.csv.gz  (~8MB, gzip-compressed CSV, git-committed)
"""

from __future__ import annotations

import gzip
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests

DATASET_ID = "xwdj-i9he"
BASE_URL = f"https://data.austintexas.gov/resource/{DATASET_ID}.json"

# Fixed 12 full calendar months. Chosen instead of "last 12 months from today" so the
# committed cache is reproducible and never ends mid-month.
START_DATE = "2025-09-01T00:00:00"
END_DATE = "2026-09-01T00:00:00"  # exclusive

COLUMNS = [
    "sr_number",
    "sr_type_desc",
    "sr_department_desc",
    "sr_method_received_desc",
    "sr_status_desc",
    "sr_created_date",
    "sr_closed_date",
    "sr_location_zip_code",
    "sr_location_council_district",
    "sr_location_lat",
    "sr_location_long",
]

PAGE_SIZE = 50_000
OUT_PATH = Path(__file__).parent / "austin_311_2025-09_2026-08.csv.gz"


def fetch_all() -> pd.DataFrame:
    headers = {}
    token = os.environ.get("SOCRATA_APP_TOKEN")
    if token:
        headers["X-App-Token"] = token

    where = f"sr_created_date >= '{START_DATE}' AND sr_created_date < '{END_DATE}'"
    frames = []
    offset = 0
    while True:
        params = {
            "$select": ",".join(COLUMNS),
            "$where": where,
            "$order": "sr_created_date,sr_number",
            "$limit": PAGE_SIZE,
            "$offset": offset,
        }
        print(f"Fetching rows {offset}..{offset + PAGE_SIZE} ...", file=sys.stderr)
        resp = requests.get(BASE_URL, params=params, headers=headers, timeout=60)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        frames.append(pd.DataFrame.from_records(batch))
        offset += PAGE_SIZE
        if len(batch) < PAGE_SIZE:
            break
        time.sleep(0.2)  # be polite to the unauthenticated rate limit

    if not frames:
        raise RuntimeError("No rows returned - check the date window / API status.")
    df = pd.concat(frames, ignore_index=True)

    # Ensure every expected column exists even if a page happened to omit an all-null one.
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA

    df["sr_created_date"] = pd.to_datetime(df["sr_created_date"])
    df["sr_closed_date"] = pd.to_datetime(df["sr_closed_date"])
    df["sr_location_council_district"] = pd.to_numeric(
        df["sr_location_council_district"], errors="coerce"
    ).astype("Int64")
    df["sr_location_lat"] = pd.to_numeric(df["sr_location_lat"], errors="coerce")
    df["sr_location_long"] = pd.to_numeric(df["sr_location_long"], errors="coerce")

    return df[COLUMNS]


def main() -> None:
    df = fetch_all()
    print(f"Fetched {len(df):,} rows.", file=sys.stderr)

    with gzip.open(OUT_PATH, "wt", newline="", encoding="utf-8", compresslevel=9) as f:
        df.to_csv(f, index=False)

    size_mb = OUT_PATH.stat().st_size / 1_048_576
    print(f"Wrote {OUT_PATH} ({size_mb:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
