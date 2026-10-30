# Otta / Welcome to the Jungle references

Verified 2026-10-23 using honest research User-Agent and official public sources.
Manual/browser-only: `enabled:false`; no unauthenticated search CLI.

| URL | Observed behavior |
| --- | --- |
| `https://otta.com/` | Redirect to `https://uk.welcometothejungle.com/` |
| `https://app.welcometothejungle.com/jobs` | Redirect to `https://app.welcometothejungle.com/login?redirect=%2F` |
| `https://app.welcometothejungle.com/jobs/_3I9P2Hv` | 200 public Planet job detail |
| `https://app.welcometothejungle.com/jobs/70ioEe_O` | 200 public Poppulo detail, closed banner despite future structured expiry |

The official [UK landing page](https://uk.welcometothejungle.com/) identifies Otta
Technology Ltd trading as Welcome to the Jungle and directs users to the app.
No official public search API/feed, search parameter schema, pagination contract
or numeric rate limit was found. An Apollo state marker in server HTML does not
grant permission to call its private GraphQL service.

Public job details embed schema.org `JobPosting` JSON-LD. The Planet Senior
Software Engineer (GMS App Team) example was open on verification, with:

```json
{
  "datePosted": "2026-08-25T18:01:48",
  "validThrough": "2026-11-06T12:14:33",
  "employmentType": "FULL_TIME",
  "jobLocationType": "TELECOMMUTE",
  "applicantLocationRequirements": [{"@type":"Country","value":"US"}]
}
```

It was US-only, not India eligible. `identifier.value` linked to the employer's
Greenhouse job. Preserve the canonical WTTJ page as the source. Public pages also
show employer, skills, salary, role requirements and an availability banner.
Always read that banner: tested Poppulo and ONE pages were closed although web
search snippets appeared current; Poppulo's `validThrough` was still in the future.

[Candidate terms](https://uk.welcometothejungle.com/terms-and-conditions/candidates)
describe account/preferences setup before job search, allow personal extracts
with source acknowledgement, restrict commercial reuse, and reserve content rights.
[UK robots](https://uk.welcometothejungle.com/robots.txt) has an empty general
disallow; [app robots](https://app.welcometothejungle.com/robots.txt) includes
Googlebot exclusions for onboarding/signup and a sitemap. Permissive robots is
not evidence of a public search API. Use visible public pages and user-driven
account access; stop on access refusal.
