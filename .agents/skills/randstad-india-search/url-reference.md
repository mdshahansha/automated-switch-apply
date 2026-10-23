# Randstad India public navigation

Checked 2026-10-23 with an identifying research User-Agent; no credentials.

- Official domain: https://www.randstad.in/
- Search: https://www.randstad.in/jobs/
- Verified category/location listing: https://www.randstad.in/jobs/s-it/s2-software-and-application-developers/re-karnataka/ci-bengaluru-urban/
- Example linked detail: https://www.randstad.in/jobs/backend-engineer_bengaluru_a6d4155b-3593-46ff-89a3-83cb85180b2e/
- Robots: https://www.randstad.in/robots.txt
- Terms: https://www.randstad.in/terms-conditions/ (also linked as `/terms-and-conditions/`).

Listing URLs combine `/jobs/` with facets such as `s-<sector>`,
`s2-<specialism>`, `re-<region>` and `ci-<city>`. Details use
`/jobs/<title>_<city>_<uuid>/`. Follow existing links instead of inventing slugs.
No verified keyword query parameter or documented public job-search API/feed is
provided by this skill.

The verified software listing returned HTTP 200 with readable jobs, public detail
links and JSON-LD. Robots generally permits listing/detail pages but blocks
several filter combinations, redirects and application routes. Technical access
does not override the terms: the intellectual-property clause restricts storing
or including information in a public or private retrieval system without written
permission. This skill therefore remains manual-only and disabled for `/scrape`.
