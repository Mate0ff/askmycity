# Eval results

Ran all 20 questions from `eval_questions.md` against the live agent
(model: `openai/gpt-oss-120b` via Groq) after the robustness/correctness
fixes in this PR. 20/20 completed with zero tool-call errors.

## 1. How many 311 requests were filed in total?  _(expected: count)_

**Answer:** A total of **280,393** 311 service requests were filed between September 1 2025 and August 31 2026.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'end_date': '2026-08-31', 'start_date': '2025-09-01'})

*(280,393 matches the true row count exactly — confirms the end_date inclusivity fix.)*

## 2. How many requests are still open?  _(expected: count)_

**Answer:** There are **4,646** 311 service requests that are still open (i.e., have a status of Open, Duplicate (open), Work In Progress, or Pending) in the Sep 2025 – Aug 2026 dataset.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_status_desc': ['Open', 'Duplicate (open)', 'Work In Progress', 'Pending']}})

## 3. How many garbage-related requests ("ARR - Garbage") were filed?  _(expected: count)_

**Answer:** A total of **25,381** resident-reported 311 requests were filed under the "ARR - Garbage" category during the September 2025 – August 2026 period.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_type_desc': 'ARR - Garbage'}})

## 4. How many requests came in by phone vs. through the Spot311 app?  _(expected: comparison)_

**Answer:** Across the September 2025 – August 2026 period, 178,144 service requests were submitted by **Phone**, while 77,900 requests came in through the **Spot311 Interface**.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'group_by': 'sr_method_received_desc', 'sort_by': 'value'})

## 5. What are the top 10 most common request types?  _(expected: ranked-list)_

**Answer:**
1. ARR – Garbage – 25,381
2. DSD – Request Code Officer – 24,236
3. TPW – Parking Violation Enforcement – 22,963
4. ARR – Compost – 15,121
5. TPW – Traffic Signal – Maintenance – 13,464
6. ARR – Bulk – 12,852
7. ARR – Recycling – 12,223
8. APD – Vehicle Abatement Report – 9,516
9. Animal Protection – Loose Dog – 9,070
10. 311 CC – Other – 7,998

**Tool calls:** top_n({'agg': 'count', 'group_by': 'sr_type_desc', 'n': 10})

## 6. Which department receives the most requests?  _(expected: ranked-list)_

**Answer:** Austin Resource Recovery receives the most requests, with **86,350** filed between September 2025 and August 2026 (vs. 78,749 for the next-largest, Austin Transportation and Public Works).

**Tool calls:** top_n({'agg': 'count', 'group_by': 'sr_department_desc', 'n': 5}) — model's first attempt hallucinated a `sort_by` kwarg on `top_n` (not a valid param there), got a TypeError back, corrected on retry. Working as intended.

## 7. How many requests per month were filed over the year?  _(expected: trend)_

**Answer:** Monthly counts from Sep 2025 (25,791) through Aug 2026 (22,367), full breakdown grouped by `created_month`, chronologically ordered via `sort_by='group'`.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'group_by': 'created_month', 'sort_by': 'group'})

## 8. Show the trend of "TPW - Parking Violation Enforcement" requests month by month.  _(expected: trend)_

**Answer:** Steady rise from ~1,850/month in late 2025 to a high of 2,359 in August 2026.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_type_desc': 'TPW - Parking Violation Enforcement'}, 'group_by': 'created_month', 'sort_by': 'group'})

## 9. Which council district has the most requests?  _(expected: ranked-list)_

**Answer:** District 9, with **43,924** requests.

**Tool calls:** top_n({'agg': 'count', 'group_by': 'sr_location_council_district', 'n': 1})

## 10. Compare request volume between council district 1 and council district 9.  _(expected: comparison)_

**Answer:** District 9: 43,924 vs. District 1: 35,205 — about 8,700 more in district 9.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_location_council_district': ['1', '9']}, 'group_by': 'sr_location_council_district', 'sort_by': 'group'})

## 11. What's the median time to close a request?  _(expected: count)_

**Answer:** Median resolution time is **1 day** (matches DATA_DICTIONARY.md's noted median of ~1.0 day).

**Tool calls:** filter_and_aggregate({'agg': 'median', 'metric': 'resolution_days'})

## 12. Which request type takes the longest to resolve on average?  _(expected: ranked-list)_

**Answer:** "Park Maintenance – Cemeteries", median ~135 days to close.

**Tool calls:** filter_and_aggregate({'agg': 'median', 'group_by': 'sr_type_desc', 'metric': 'resolution_days', 'sort_by': 'value'})

## 13. Did animal-related requests ("Animal Protection - Loose Dog") spike in any particular month?  _(expected: trend)_

**Answer:** Fairly steady (657–884/month); the only notable peak was March 2026 (884), declining to 489 by August.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_type_desc': 'Animal Protection - Loose Dog'}, 'group_by': 'created_month', 'sort_by': 'group'})

## 14. How many requests were marked as duplicates?  _(expected: count)_

**Answer:** **8,719** (Duplicate (closed) + Duplicate (open)) — close to DATA_DICTIONARY.md's raw 8,572 + 172 = 8,744, difference from the 4 dropped CancelledTesting rows / status nuance; within expected range.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_status_desc': ['Duplicate (closed)', 'Duplicate (open)']}})

## 15. What share of requests are still unresolved (Open or Work In Progress)?  _(expected: count)_

**Answer:** ~1.6% of all requests remain unresolved (open/duplicate-open/WIP/pending).

**Tool calls:** two filter_and_aggregate calls (total count, then filtered count) — correctly composed a share from two tool calls.

## 16. Compare garbage/recycling/compost/bulk request volumes (the four ARR categories) against each other.  _(expected: comparison)_

**Answer:** Garbage 25,381 > Compost 15,121 > Bulk 12,852 > Recycling 12,223.

**Tool calls:** filter_and_aggregate({'agg': 'count', 'filters': {'sr_type_desc': ['ARR - Garbage', 'ARR - Recycling', 'ARR - Compost', 'ARR - Bulk']}, 'group_by': 'sr_type_desc', 'sort_by': 'value'})

## 17. What are the top 5 request categories in council district 3?  _(expected: ranked-list)_

**Answer:** DSD – Request Code Officer (3,429), TPW – Parking Violation Enforcement (3,118), ARR – Garbage (2,101), ARR – Compost (1,481), APD – Vehicle Abatement Report (1,455).

**Tool calls:** top_n({'agg': 'count', 'filters': {'sr_location_council_district': '3'}, 'group_by': 'sr_type_desc', 'n': 5})

## 18. How did total request volume in the first half of the window (Sep'25-Feb'26) compare to the second half (Mar'26-Aug'26)?  _(expected: comparison)_

**Answer:** First half: 130,872. Second half: 148,153 — a ~13% rise.

**Tool calls:** two filter_and_aggregate calls with disjoint date ranges.

## 19. Which ZIP code has the most requests?  _(expected: ranked-list)_

**Answer:** ZIP 78704, with 20,504 requests.

**Tool calls:** top_n({'agg': 'count', 'group_by': 'sr_location_zip_code', 'n': 1})

## 20. Show the monthly trend of requests received via E-Mail vs. Phone.  _(expected: trend)_

**Answer:** Full month-by-month table for both channels; Phone dominant every month (12k-17k) vs. E-Mail (under 500/month each).

**Tool calls:** two filter_and_aggregate calls, one per channel, grouped by `created_month`.

---

**Note on free-tier limits:** Groq's free tier caps at 200,000 tokens/day
per model. Running this 20-question eval a handful of times while
iterating (plus the app's normal usage) is enough to hit that daily cap —
worth keeping in mind for the live demo.
