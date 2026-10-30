---
name: indeed-india-search
version: 1.0.0
description: >
  Guide manual searches and job lookups on Indeed India (in.indeed.com). Use for Indeed India jobs, Indeed developer vacancies, इंडीड पर नौकरी खोजें, or indeed India par naukri. Provides verified public search links; no automated scrape CLI.
context: fork
enabled: false
---

# Indeed India search guidance

This is a manual/browser navigation skill. It has no verified CLI and is disabled for `/scrape` CLI dispatch. Read [url-reference.md](url-reference.md) for verified routes and access evidence before looking up a job.

The public search returned HTTP 403 under an honest tool-identifying User-Agent. [Robots](https://in.indeed.com/robots.txt) disallows `/viewjob`, RSS and several internal routes. [Site Rules](https://in.indeed.com/legal?hl=en), section 21, restrict automated systems and bypassing access controls. Stop at blocks; do not use browser impersonation or unofficial APIs.

## Use

1. Open [the verified starting page](https://in.indeed.com/jobs?q=software+engineer&l=India) in a normal browser, or give the user the link. Follow the page's available public UI; stop if login, a challenge or a block prevents reading.
2. Build links with URL-encoded `q` keywords and `l` location. Use the normal page UI for recency and other filters. Indexed snippets can help identify a link but do not verify live vacancy availability or usable CLI access.
3. Report roles only from accessible current pages or user-provided text. Preserve the original job link and identify unverified availability or missing fields. Do not claim an indexed snippet proves the role is still open.
4. For fit assessment and application preparation, load `CLAUDE.md` and the canonical methodology under `.claude/skills/job-application-assistant/`; do not duplicate or invent candidate facts.
5. If application access requires an account, the user signs in through the normal interface. Searching does not authorize applying, sending messages or uploading personal documents. Submit/send only when the user requests that action; stop for the user's own authentication or challenge interaction when needed.

## Useful links

- [Software engineer jobs in India](https://in.indeed.com/jobs?q=software+engineer&l=India)
- [React jobs in Bengaluru](https://in.indeed.com/jobs?q=React&l=Bengaluru)

Do not add private API calls, proxy/unlocker services, browser impersonation, CAPTCHA handling or credential extraction to this skill. A blocked or empty response is an access limitation, not permission to bypass it.
