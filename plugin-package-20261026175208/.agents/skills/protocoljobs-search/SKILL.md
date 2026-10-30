---
name: protocoljobs-search
version: 1.0.0
description: >
  Guide manual Protocol Jobs searches for technology and professional roles in
  India, or navigate a supplied public Protocol job link. Use for ProtocolJobs,
  Protocol Jobs vacancies, Protocol par naukri, or Protocol mein job khojo.
context: fork
enabled: false
---

# Protocol Jobs manual search

This skill has no CLI and `/scrape` must skip it. Public detail pages and a
sitemap are readable, but a query-driven public search API was not verified.
The app explicitly disallows `/api/`; do not use it or infer permission to scrape
from the public sitemap. No application action is authorized by this skill.

Read [url-reference.md](url-reference.md). The official marketing site is
[protocoljobs.ai](https://protocoljobs.ai/), which links to the
[jobs dashboard](https://app.protocoljobs.ai/dashboard). In the user's browser,
search by role or company and use the visible domain, experience, posting-date
and location filters. Examples: backend engineer in Bengaluru, Java in Pune,
or software engineer in Hyderabad.

For a supplied public detail link, verify the title, employer, location,
experience and date. Keep Protocol's estimated salary distinct from an
employer-confirmed range. A reachable page can be expired; check the source
career page or expiry where visible before calling a job open. Report direct
links and missing data. Leave account-only match scores, contact unlocks and
applications to the user; use canonical `.claude/` workflows for preparation.
