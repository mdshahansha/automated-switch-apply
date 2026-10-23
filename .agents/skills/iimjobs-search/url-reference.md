# IIMJobs public URL reference

Verified 2026-10-23 using an honest tool-identifying User-Agent.

| Purpose | URL | Observation |
|---|---|---|
| Current official domain | https://www.iimjobs.com/ | Current official pages and terms. |
| Category | https://www.iimjobs.com/c/it-systems-jobs | HTTP 200 shell with no jobs under research UA; indexed public page showed current IT roles. |
| Location filter | https://www.iimjobs.com/c/it-systems-jobs?loc=Bangalore_Mumbai_Pune_Kolkata | Official indexed category URL. |
| Pagination | https://www.iimjobs.com/c/it-systems-jobs?loc=Mumbai_Bangalore_Pune_Delhi+NCR&page=7 | Observed official indexed search URL. |
| Actual software detail | https://www.iimjobs.com/j/salesforcecom-senior-software-engineering-manager-1727176 | HTTP 200 shell under research UA; indexed page: Salesforce India, Bangalore, 10–14 years. Recheck current availability. |
| Robots | https://www.iimjobs.com/robots.txt | HTTP 200; `Crawl-delay: 10`; public `/c`, `/k`, `/j` not disallowed in generic group. |
| Terms | https://www.iimjobs.com/terms | HTTP 200; robots/scraping excluded technologically; users must not circumvent those methods. |

Shapes: `/c/{category}-jobs`, `/k/{skill}-jobs`, `/j/{slug}-{numeric_id}`. `loc` and `page` are observed query parameters; use the UI for other filters rather than inventing values. No documented official public job-search API/feed found. Public indexed content is not proof of usable anonymous CLI responses. No CLI is included.
