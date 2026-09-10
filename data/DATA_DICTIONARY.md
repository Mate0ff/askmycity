# Data Dictionary — Austin 311 Public Data (cached slice)

**File:** `austin_311_2025-09_2026-08.csv.gz` (~7.3MB, gzip CSV, 280,397 rows)
**Source:** City of Austin Open Data Portal (Socrata), dataset [Austin 311 Public Data](https://data.austintexas.gov/Utilities-and-City-Services/Austin-311-Public-Data/xwdj-i9he), endpoint `data.austintexas.gov/resource/xwdj-i9he.json`. Fetched via `download_data.py`.
**Date range:** 2025-09-01 to 2026-08-31 (12 full calendar months — fixed window, not "trailing 12 months", so the cache is reproducible and never ends mid-month).
**License:** No explicit machine-readable license tag on this dataset in the Socrata catalog; the portal is governed by the City of Austin's general Open Data Terms of Use. I could not extract the exact clause text (the terms page is JS-rendered and blocked automated fetch) — **please have a human skim it before the repo goes public**: https://data.austintexas.gov/stories/s/City-of-Austin-Open-Data-Terms-of-Use/ranj-cccq/. City open-data portals are near-universally open for reuse, but this wasn't independently confirmed.

## Columns

| Column | Type | Meaning | Nulls |
|---|---|---|---|
| `sr_number` | string | Unique service request ID | 0 |
| `sr_type_desc` | string | Request category, e.g. "ARR - Garbage" (146 distinct values) | 0 |
| `sr_department_desc` | string | Owning department (31 distinct values — see quirks) | 0 |
| `sr_method_received_desc` | string | Intake channel: Phone, Spot311 Interface, Citizen Web Intake, E-Mail, etc. | 0 |
| `sr_status_desc` | string | Closed / Open / Duplicate (closed) / Duplicate (open) / Work In Progress / Pending / etc. | 0 |
| `sr_created_date` | datetime | When the request was filed | 0 |
| `sr_closed_date` | datetime | When resolved (null = still open or never closed) | 4,646 (1.7%) |
| `sr_location_zip_code` | float | ZIP code of the request location | 1,177 (0.4%) |
| `sr_location_council_district` | float (1-10) | Austin city council district — closest thing to a "neighborhood" field | 7,649 (2.7%) |
| `sr_location_lat` / `sr_location_long` | float | Coordinates | 322 each (0.1%) — plus see quirk below |

## Known quirks

- **Sentinel coordinate for "no location":** 887 rows (0.3%) share the exact placeholder `(3.442387, -105.983195)` — not a real Austin location, don't plot these. Filter with a bounding-box check (Austin ≈ lat 29-31, long -99 to -96) rather than trusting non-null lat/long alone.
- **Inconsistent department naming:** the same department appears under multiple strings, e.g. `"Austin Police"` vs `"Austin Police Department"`, and `"Transportation and Public Works"` vs `"Austin Transportation and Public Works"` — real messy categorical data, group/normalize before aggregating by department.
- **`sr_status_desc` is not binary open/closed:** includes `Duplicate (closed)`, `Duplicate (open)`, `Work In Progress`, `Pending`, `CancelledTesting` (4 rows, looks like test data leaking into prod). Decide how to bucket these before computing "% resolved".
- Resolution time (`sr_closed_date - sr_created_date`) for closed requests: median ~1.0 day, mean ~6.3 days, max ~365 days — long right tail, use median not mean when summarizing.
- No duplicate `sr_number` rows; no `sr_closed_date` earlier than `sr_created_date`.
