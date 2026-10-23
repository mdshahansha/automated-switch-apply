---
name: apna-search
version: 1.0.0
description: >
  Guide manual searches and job lookups on Apna (apna.co), India. Use for Apna jobs, Apna software vacancies, अपना पर नौकरी खोजें, अपना जॉब, or apna par naukri. Provides verified search links and browser guidance; no automated search CLI.
context: fork
enabled: false
---

# Apna search guidance

This is a manual/browser navigation skill. It has no verified CLI and is disabled for `/scrape` CLI dispatch. Read [url-reference.md](url-reference.md) for verified routes and access evidence before looking up a job.

The public software search returned complete HTML, but the [User Agreement](https://apna.co/user-agreement), sections 7.1(d)–(e), prohibits automated monitoring/copying and systematic retrieval into collections. Do not implement or run a scraper under this skill.

## Use

1. Open [the verified starting page](https://apna.co/jobs/software-engineer-jobs) in a normal browser, or give the user the link. Follow the page's available public UI; stop if login, a challenge or a block prevents reading.
2. Use the page filters for date posted, salary, work mode and work type. Do not invent query parameters; verified routes use role and city slugs.
3. Report roles only from accessible current pages or user-provided text. Preserve the original job link and identify unverified availability or missing fields. Do not claim an indexed snippet proves the role is still open.
4. For fit assessment and application preparation, load `CLAUDE.md` and the canonical methodology under `.claude/skills/job-application-assistant/`; do not duplicate or invent candidate facts.
5. If application access requires an account, the user signs in through the normal interface. Searching does not authorize applying, sending messages or uploading personal documents. Submit/send only when the user requests that action; stop for the user's own authentication or challenge interaction when needed.

## Useful links

- [Software engineer jobs](https://apna.co/jobs/software-engineer-jobs)
- [Backend developer jobs in Bengaluru](https://apna.co/jobs/backend-software-developer-jobs-in-bengaluru)

Do not add private API calls, proxy/unlocker services, browser impersonation, CAPTCHA handling or credential extraction to this skill. A blocked or empty response is an access limitation, not permission to bypass it.
