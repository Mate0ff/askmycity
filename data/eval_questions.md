# Eval questions

Natural-language questions for testing the query agent against `austin_311_2025-09_2026-08.csv.gz`.
Answer types: **count**, **trend** (time series/chart), **ranked-list** (top-N), **comparison**.

1. How many 311 requests were filed in total? — count
2. How many requests are still open? — count
3. How many garbage-related requests ("ARR - Garbage") were filed? — count
4. How many requests came in by phone vs. through the Spot311 app? — comparison
5. What are the top 10 most common request types? — ranked-list
6. Which department receives the most requests? — ranked-list
7. How many requests per month were filed over the year? — trend
8. Show the trend of "TPW - Parking Violation Enforcement" requests month by month. — trend
9. Which council district has the most requests? — ranked-list
10. Compare request volume between council district 1 and council district 9. — comparison
11. What's the median time to close a request? — count
12. Which request type takes the longest to resolve on average? — ranked-list
13. Did animal-related requests ("Animal Protection - Loose Dog") spike in any particular month? — trend
14. How many requests were marked as duplicates? — count
15. What share of requests are still unresolved (Open or Work In Progress)? — count
16. Compare garbage/recycling/compost/bulk request volumes (the four ARR categories) against each other. — comparison
17. What are the top 5 request categories in council district 3? — ranked-list
18. How did total request volume in the first half of the window (Sep'25-Feb'26) compare to the second half (Mar'26-Aug'26)? — comparison
19. Which ZIP code has the most requests? — ranked-list
20. Show the monthly trend of requests received via E-Mail vs. Phone. — trend
