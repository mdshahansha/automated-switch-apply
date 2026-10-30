---
name: randstad-india-search
version: 1.0.0
description: >
  Guide manual searches for Randstad India vacancies, including software and
  engineering jobs in Indian cities. Use for Randstad India jobs, Randstad
  vacancies, Randstad par naukri, or Randstad mein job khojo.
context: fork
enabled: false
---

# Randstad India job search

This is a manual navigation skill. It has no CLI and `/scrape` must skip it.
Public listings were reachable, but Randstad's terms restrict storing site
information in retrieval systems without prior written permission. Do not scrape
or treat this skill as permission to automate access or submit applications.

Read [url-reference.md](url-reference.md) before choosing a link. Open the official
[job search](https://www.randstad.in/jobs/) in the user's browser when requested.
Enter the role or skill and the requested city, then use the site's sector,
specialism, contract, and location filters. For example, search backend engineer
in Bengaluru, Java developer in Pune, or cloud engineer in Hyderabad. Confirm the
actual role, city, date and availability on the detail page; a category label
alone is not a match.

Report selected titles, employers where disclosed, locations, dates if shown,
and direct Randstad links. Do not infer the confidential client, salary, or
eligibility. Login or application steps remain with the user. Use the repository's
canonical `.claude/` workflows for ranking or application preparation.
