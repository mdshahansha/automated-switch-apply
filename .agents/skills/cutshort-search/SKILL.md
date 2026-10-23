---
name: cutshort-search
version: 1.0.0
description: >
  Guide manual searches for Cutshort technology and startup vacancies in India.
  Use for Cutshort jobs, Cutshort developer roles, Cutshort par naukri, or
  Cutshort mein job khojo. This skill has no automated job-search CLI.
context: fork
enabled: false
---

# Cutshort job search

Manual navigation only; `/scrape` must skip this skill. Cutshort's terms prohibit
automated website access and systematic data collection. Its official employer
API is not a public vacancy-search service. Do not scrape, use hidden APIs, or
treat this skill as application authorization.

Read [url-reference.md](url-reference.md), then use the official
[jobs page](https://cutshort.io/jobs) in the user's browser when requested. Search
for the supplied role or skill, choose the requested Indian city or remote, and
review experience and salary filters shown by the site. Useful starting points
include backend developer in Bengaluru, React in Pune, and Java in Hyderabad.
Open each promising job and verify its experience range, work mode, salary period,
posting date, and whether it is an agency or direct-company listing.

Return concise matches with title, company, location, experience and direct
Cutshort link. Preserve salary as displayed and distinguish missing data. Leave
sign-in and applications to the user. Follow canonical `.claude/` workflows for
candidate evaluation and preparation.
