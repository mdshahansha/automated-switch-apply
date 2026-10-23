---
name: aijobs-search
version: 1.0.0
description: >
  Clarify which AIJobs website the user means, then guide manual AI, machine
  learning and data-job searches worldwide, including India. Use for AIJobs
  vacancies, AIJobs par naukri, or AIJobs job search; the brand is ambiguous.
context: fork
enabled: false
---

# AIJobs manual search

**Ask for the exact website URL first.** AIJobs can mean distinct services:
[aijobs.ai](https://aijobs.ai/), [aijobs.com](https://www.aijobs.com/), or the old
`aijobs.net` address, which redirected to [Foorilla](https://foorilla.com/hiring/)
when checked. Do not pick one or combine their results without clarification.
This skill has no CLI; `/scrape` must skip it.

After the user identifies the site, read [url-reference.md](url-reference.md).
Use that site's visible job search in the user's browser when requested, with
the supplied role, city/country and remote preferences. Examples include AI
engineer in Bengaluru, machine learning engineer in India, or international
remote data roles that explicitly permit work from India. Confirm geography and
work authorization in the actual posting; a remote label does not establish
India eligibility.

Report title, company, location, posting date if available, and a direct link to
the confirmed site. Mark missing dates or uncertainty. Respect each site's access
rules, leave authentication and applications to the user, and use canonical
`.claude/` workflows for ranking or document preparation. This skill does not
grant scraping or application permission.
