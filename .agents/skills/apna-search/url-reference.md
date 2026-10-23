# Apna public URL reference

Verified 2026-10-23 with `CodexJobSearchResearch/1.0 (OpenAI Codex; read-only public-page access test)`.

| Purpose | Verified URL / pattern | Observation |
|---|---|---|
| Software search | https://apna.co/jobs/software-engineer-jobs | HTTP 200; complete HTML; page title reported 308 vacancies that day. Counts change. |
| Role and city | https://apna.co/jobs/backend-software-developer-jobs-in-bengaluru | Public indexed search page; browser filters include recency, salary and work mode. |
| Detail | https://apna.co/job/noida/systems-integration-advisor-1337580004 | Official indexed detail; NTT DATA, Systems Integration Advisor / Backend Developer. |
| Alternate detail | https://www.apna.co/job/1780163885 | Official indexed numeric-ID route; NTT DATA software/API role. |
| Robots | https://apna.co/robots.txt | HTTP 200. Generic group disallows `/*.infra.apna.co/`; advertises `/api/sitemap-index.xml`. |
| Candidate terms | https://apna.co/user-agreement | HTTP 200. Sections 7.1(d)–(e) prohibit automated monitoring/copying and systematic retrieval compiling collections. |

Search shapes are `/jobs/{role}-jobs` and `/jobs/{role}-jobs-in-{city}`; detail shapes include `/job/{city}/{slug}-{id}` and `/job/{id}`. Use observed links rather than guessing slugs. No supported public job-search API was found. A sitemap is not an API or permission. Do not use staging/infra domains exposed by search engines. Technical HTTP access does not override the terms. No search CLI is verified or included.
