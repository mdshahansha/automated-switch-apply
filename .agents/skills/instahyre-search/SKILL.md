---
name: instahyre-search
version: 1.0.0
description: >
  Guide manual job matching and user-provided vacancy lookups on Instahyre, India technology hiring. Use for Instahyre jobs, Instahyre opportunities, इंस्टाहायर पर नौकरी खोजें, or instahyre par naukri. Uses the account Opportunities workflow; no verified public search CLI.
context: fork
enabled: false
---

# Instahyre search guidance

This is a manual/browser navigation skill. It has no verified CLI and is disabled for `/scrape` CLI dispatch. Read [url-reference.md](url-reference.md) for verified routes and access evidence before looking up a job.

Public homepage, sitemap and terms probes returned HTTP 520. No anonymous search response, stable public search route, or terms permission was verified. Stop at blocks and use the normal user account workflow; do not invent a scraper or infer permission from robots.txt.

## Use

1. Open [the verified starting page](https://www.instahyre.com/) in a normal browser, or give the user the link. Follow the page's available public UI; stop if login, a challenge or a block prevents reading.
2. Have the user review their Opportunities tab and profile preferences. Official help says matching uses resume, preferences and work experience. The user may supply a vacancy share link or text for evaluation; no stable share-link URL pattern has been verified.
3. Report roles only from accessible current pages or user-provided text. Preserve the original job link and identify unverified availability or missing fields. Do not claim an indexed snippet proves the role is still open.
4. For fit assessment and application preparation, load `CLAUDE.md` and the canonical methodology under `.claude/skills/job-application-assistant/`; do not duplicate or invent candidate facts.
5. If application access requires an account, the user signs in through the normal interface. Searching does not authorize applying, sending messages or uploading personal documents. Submit/send only when the user requests that action; stop for the user's own authentication or challenge interaction when needed.

## Useful links

- [Instahyre](https://www.instahyre.com/)
- [Official Opportunities guide](https://help.instahyre.com/en/article/explore-matching-opportunities-1s98q42/)
- [Official profile guidance](https://help.instahyre.com/en/article/profile-tips-and-best-practices-jullgg/)

Do not add private API calls, proxy/unlocker services, browser impersonation, CAPTCHA handling or credential extraction to this skill. A blocked or empty response is an access limitation, not permission to bypass it.
