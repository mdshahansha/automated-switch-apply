# Hirist public URL reference

Verified 2026-10-23 using an honest tool-identifying User-Agent.

| Purpose | URL | Observation |
|---|---|---|
| Current official domain | https://www.hirist.tech/ | Current official terms and public job links use this domain. |
| Category | https://www.hirist.tech/c/backend-development-jobs | HTTP 200 shell; raw schema `numberOfItems:0`, no listing data under the research UA. |
| Skill | https://www.hirist.tech/k/python-jobs | Official navigation link; `/k/{skill}-jobs` shape. |
| Actual detail | https://www.hirist.tech/j/software-development-engineer-i-backend-architecture-1670645 | HTTP 200 shell under research UA. Indexed official page: Supersourcing, 2–3 years, multiple locations, posted 2026-09-11. Availability must be rechecked. |
| Robots | https://www.hirist.tech/robots.txt | HTTP 200; `Crawl-delay: 10`; `/c`, `/k`, `/j` not disallowed in generic group. |
| Terms | https://www.hirist.tech/terms | HTTP 200; says robots/scraping are technologically excluded and users must not circumvent those methods. |

Observed category filters: `minexp`, `maxexp`, `loc`, `page`. Example: https://www.hirist.tech/c/backend-development-jobs?maxexp=1&minexp=0 . Public detail shape: `/j/{slug}-{numeric_id}`; `jobPos` is observed tracking, not a search filter. Indexed content is not proof that an anonymous CLI can retrieve listings. No documented official public job-search API/feed was found. Do not use preproduction subdomains or private services exposed in page assets. This skill contains no CLI.
