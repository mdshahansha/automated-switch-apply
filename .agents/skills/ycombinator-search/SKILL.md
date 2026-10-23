---
name: ycombinator-search
version: 1.0.0
description: >
  Research Y Combinator startup jobs and Work at a Startup listings worldwide,
  including software engineering jobs in India and remote startup roles. Use for
  YC jobs, Work at a Startup, Y Combinator hiring, or startup engineer openings.
  This English-language source is a manual public-page workflow, not an API CLI.
context: fork
enabled: false
---

# Y Combinator / Work at a Startup

Manual public-page research is available; this source is disabled for automatic
CLI `/scrape` runs. No official public jobs API or stable search/pagination
contract was verified. Do not invent a CLI command or call internal app APIs.

Start with the public route matching the user's country or role:

- [India jobs](https://www.ycombinator.com/jobs/location/india)
- [Software engineering in India](https://www.ycombinator.com/jobs/role/software-engineer/india)
- [Remote software engineering](https://www.ycombinator.com/jobs/role/software-engineer/remote)
- [Work at a Startup job directory](https://www.workatastartup.com/jobs)

Use public pages or a primary-source web search such as
`site:ycombinator.com/companies/ "React" "India"` or
`site:ycombinator.com/companies/ "Node.js" "Remote"`, then open each result and
verify its title, company, current status, full location and work-authorization
restrictions. Link the canonical YC job page and mark missing dates unknown.
Preserve conflicting evidence: a live role titled “India” showed `Remote (US)`
and `US citizen/visa only`, so title or directory membership alone is insufficient.

Applications and personalized matching require the user's YC account. Hand off
login/application to the user; reading listings does not authorize submitting an
application or messaging a founder. If access is refused, stop at the public
source link instead of switching identities or bypassing protection.

Keep personal research small, acknowledge Y Combinator, and do not bulk-republish
listings. [Official terms](https://www.ycombinator.com/legal/#tou) restrict commercial
reuse. Verified routes and public HTML observations are recorded in
[url-reference.md](url-reference.md).
