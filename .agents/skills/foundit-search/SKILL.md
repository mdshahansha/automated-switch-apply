---
name: foundit-search
version: 1.0.0
description: >
  Guide manual Foundit India vacancy searches, including software, data and
  engineering roles. Use for Foundit jobs, Monster India jobs, Foundit par
  naukri, or Foundit mein job khojo. No automated search CLI is provided.
context: fork
enabled: false
---

# Foundit India manual search

This skill is manual-only and disabled for `/scrape`. An identifying automated
request was refused, and the site's robots rules restrict AI crawlers' search
paths. Do not retry with browser impersonation, proxies, hidden endpoints or
credentials to bypass those restrictions.

Read [url-reference.md](url-reference.md). When the user requests browser
navigation, use [Foundit India](https://www.foundit.in/) and its visible search
for the role and city. For example: software developer in Bengaluru, React in
Pune, or Java in Chennai. Refine using the site's experience, work-mode and date
filters. Inspect whether the posting is still accepting applications and whether
the company and location are actual job fields rather than search-page text.

Return selected titles, companies, locations, dates if shown, and direct Foundit
links. State when a result came only from a search-engine index and has not been
confirmed live. Leave sign-in and applications to the user. This skill does not
authorize scraping or submission; use canonical `.claude/` workflows for fit and
application preparation.
