---
name: otta-search
version: 1.0.0
description: >
  Research Otta jobs, now Welcome to the Jungle UK/US, and review public job
  links for software engineering or other roles. Use for Otta job search,
  Welcome to the Jungle jobs, or WTTJ tech vacancies in the source's English
  markets. Manual public-page review and user login handoff only; no public
  search API or unauthenticated search CLI is provided.
context: fork
enabled: false
---

# Otta / Welcome to the Jungle

Otta now redirects to [Welcome to the Jungle UK](https://uk.welcometothejungle.com/).
The `otta-search` name is retained as a recognizable alias. This source is
disabled for automatic CLI `/scrape`; its job directory requires account login.
No official public search API/feed was verified. Do not fabricate a CLI or use
private GraphQL/Apollo requests.

Open [Explore jobs](https://app.welcometothejungle.com/jobs) for the user to log in
and select their own preferences. In an explicitly authorized existing browser
session, use the visible site controls. Otherwise use public web discovery such
as `site:app.welcometothejungle.com/jobs "React" "Remote"`, then read each public
job URL. The public pages can be reviewed without claiming authenticated search
was performed.

Verify the live page's availability banner, applicant country, work location,
employer, requirements and application deadline. Search snippets can outlive a
job. A future JSON-LD `validThrough` also does not override a “Job no longer
available” banner. Remote from the US or Europe does not imply India eligibility.
Link the canonical WTTJ page, cite the source, and leave absent metadata unknown.

Hand off login and application submission to the user. Do not reuse credentials,
bypass account requirements, or treat listing review as permission to apply.
Personal excerpts are allowed under the [candidate terms](https://uk.welcometothejungle.com/terms-and-conditions/candidates)
with acknowledgement; commercial content reuse needs a licence. Public detail
routes, example fields and authentication evidence are in
[url-reference.md](url-reference.md).
