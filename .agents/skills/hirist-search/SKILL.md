---
name: hirist-search
version: 1.0.0
description: >
  Guide manual searches and job lookups on Hirist (hirist.tech), India technology roles. Use for Hirist jobs, Hirist developer vacancies, हिरिस्ट पर नौकरी खोजें, or hirist par naukri. Provides verified category/skill links; no automated search CLI.
context: fork
enabled: false
---

# Hirist search guidance

This is a manual/browser navigation skill. It has no verified CLI and is disabled for `/scrape` CLI dispatch. Read [url-reference.md](url-reference.md) for verified routes and access evidence before looking up a job.

Honest tool-identifying requests received HTTP 200 shells without job data, although indexed pages contain listings. [Terms](https://www.hirist.tech/terms) prohibit circumventing measures excluding robots and scraping. Do not change identity, call internal APIs, or route around those measures.

## Use

1. Open [the verified starting page](https://www.hirist.tech/c/backend-development-jobs) in a normal browser, or give the user the link. Follow the page's available public UI; stop if login, a challenge or a block prevents reading.
2. Use the browser location and experience filters. Public routes support categories and skills; see the reference for observed query parameters. A 200 shell is not a successful search or evidence of zero vacancies.
3. Report roles only from accessible current pages or user-provided text. Preserve the original job link and identify unverified availability or missing fields. Do not claim an indexed snippet proves the role is still open.
4. For fit assessment and application preparation, load `CLAUDE.md` and the canonical methodology under `.claude/skills/job-application-assistant/`; do not duplicate or invent candidate facts.
5. If application access requires an account, the user signs in through the normal interface. Searching does not authorize applying, sending messages or uploading personal documents. Submit/send only when the user requests that action; stop for the user's own authentication or challenge interaction when needed.

## Useful links

- [Backend development](https://www.hirist.tech/c/backend-development-jobs)
- [Python jobs](https://www.hirist.tech/k/python-jobs)
- [Java jobs](https://www.hirist.tech/k/java-jobs)

Do not add private API calls, proxy/unlocker services, browser impersonation, CAPTCHA handling or credential extraction to this skill. A blocked or empty response is an access limitation, not permission to bypass it.
