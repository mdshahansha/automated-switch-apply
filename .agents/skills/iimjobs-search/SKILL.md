---
name: iimjobs-search
version: 1.0.0
description: >
  Guide manual searches and vacancy lookups on IIMJobs (iimjobs.com), India professional, management and technology leadership roles. Use for IIMJobs jobs, IIM Jobs search, आईआईएमजॉब्स पर नौकरी, or iimjobs par naukri. No automated search CLI.
context: fork
enabled: false
---

# IIMJobs search guidance

This is a manual/browser navigation skill. It has no verified CLI and is disabled for `/scrape` CLI dispatch. Read [url-reference.md](url-reference.md) for verified routes and access evidence before looking up a job.

Honest tool-identifying requests received HTTP 200 shells without job data; indexed pages show actual roles. [Terms](https://www.iimjobs.com/terms) prohibit circumventing measures excluding robots and scraping. Do not switch identity, call internal APIs, or work around those measures.

## Use

1. Open [the verified starting page](https://www.iimjobs.com/c/it-systems-jobs) in a normal browser, or give the user the link. Follow the page's available public UI; stop if login, a challenge or a block prevents reading.
2. Use location, industry and experience filters in the browser. IIMJobs emphasizes professional and management roles, so inspect seniority before treating a listing as a software IC match. A 200 shell does not establish an empty job market.
3. Report roles only from accessible current pages or user-provided text. Preserve the original job link and identify unverified availability or missing fields. Do not claim an indexed snippet proves the role is still open.
4. For fit assessment and application preparation, load `CLAUDE.md` and the canonical methodology under `.claude/skills/job-application-assistant/`; do not duplicate or invent candidate facts.
5. If application access requires an account, the user signs in through the normal interface. Searching does not authorize applying, sending messages or uploading personal documents. Submit/send only when the user requests that action; stop for the user's own authentication or challenge interaction when needed.

## Useful links

- [IT and systems jobs](https://www.iimjobs.com/c/it-systems-jobs)
- [IT and systems in major cities](https://www.iimjobs.com/c/it-systems-jobs?loc=Bangalore_Mumbai_Pune_Kolkata)

Do not add private API calls, proxy/unlocker services, browser impersonation, CAPTCHA handling or credential extraction to this skill. A blocked or empty response is an access limitation, not permission to bypass it.
