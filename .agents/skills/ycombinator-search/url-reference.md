# Y Combinator / Work at a Startup references

Verified 2026-10-23 with honest research User-Agent and primary public pages.
Manual/browser-only: `enabled:false`; no CLI scaffold or undocumented API.

| Verified URL | Observation |
| --- | --- |
| `https://www.workatastartup.com/jobs` | 200 public directory |
| `https://www.ycombinator.com/jobs/location/india` | 200 India directory |
| `https://www.ycombinator.com/jobs/role/software-engineer/india` | 200 software role + India directory |
| `https://www.ycombinator.com/jobs/role/software-engineer/remote` | 200 remote software directory |
| `https://www.ycombinator.com/companies/litellm/jobs/8ya5TlZ-forward-deployed-engineer-india` | 200 public detail example |

`/jobs/role/software-engineer/location/india` was tested and returned 404; use the
verified route above. No official public jobs API, query parameter contract,
pagination contract or numeric request limit was found. Directory pages are not
an exhaustive guarantee that every displayed job is eligible in their named country.

Public server HTML embeds escaped JSON in a `data-page` attribute. On the Work at
a Startup jobs page it had `component:jobs/public/pages/JobsV2Page`, with
`props.jobs`, `props.totalJobsCount`, `props.initialQuery` and role links.
Observed `jobs` fields: `id,title,jobType,location,roleType,salary,companyName,
companySlug,companyBatch,companyOneLiner,companyLogoUrl,companyLastActiveAt,applyUrl`.
This is a public HTML implementation detail, not a supported API contract.

The YC detail page used `component:WaasShowJobPage`, `props.job`, including
`id,title,url,applyUrl,location,type,role,roleSpecificType,salaryRange,equityRange,
minExperience,visa,skills,companyName,description,interview_process`.
The live LiteLLM example was titled Forward Deployed Engineer - India, while
location was `Remote (US)` and visa `US citizen/visa only`. Eligibility therefore
requires clarification; do not advertise it as India-eligible on title alone.
Relative descriptions like “2 months” are not exact original posting dates.

Application links led to `account.ycombinator.com/authenticate`; do not automate
login, submission or founder outreach as part of this search skill.

[YC robots](https://www.ycombinator.com/robots.txt) allows public jobs and disallows
`/companies?*` queries among other paths. [Work at a Startup robots](https://www.workatastartup.com/robots.txt)
has an empty general disallow. [Official terms](https://www.ycombinator.com/legal/#tou)
restrict commercial use and reuse without authorization. No official API permission
was identified; these observations support low-volume personal public-page review.
