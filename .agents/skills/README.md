# Job portal skills

Portal skills use the candidate profile and workflows in `CLAUDE.md` and `.claude/`. They do not maintain a second candidate profile or authorize applications, account creation, messages, uploads, or recurring runs by themselves.

## Public API and feed CLIs

These skills have standalone Bun CLIs with `search` and `detail`. They are included in `/scrape` only when their `SKILL.md` has `enabled: true`. Each CLI documents its actual filters and data coverage; unsupported filters must not be silently dropped.

| Skill | Source | Coverage and limits |
|---|---|---|
| [linkedin-search](linkedin-search/SKILL.md) | Public LinkedIn listings | Existing personal-use tool; LinkedIn can restrict automated access. |
| [freehire-search](freehire-search/SKILL.md) | Public freehire REST API | Existing technical-role aggregator; country and remote facets. |
| [himalayas-search](himalayas-search/SKILL.md) | Official Himalayas JSON API | Remote search and individual job details; preserve country/timezone restrictions and source links. |
| [remoteok-search](remoteok-search/SKILL.md) | Official Remote OK JSON feed | Filter the current bounded feed locally; a missing job is not proof that it closed. |
| [weworkremotely-search](weworkremotely-search/SKILL.md) | Official We Work Remotely RSS | Filter current feed entries locally; preserve expiry and attribution. Feed coverage differs by category. |

The Danish examples, `jobbank-search`, `jobdanmark-search`, `jobindex-search`, and `jobnet-search`, remain installed and disabled for this candidate's India-focused search.

## Browser workflows

These skills are usable as instructions for normal browser navigation, portal filters, sign-in handoff, and reviewing user-supplied vacancy text. They have `enabled: false` because they have no verified anonymous search CLI and must not be dispatched as CLI integrations by `/scrape`. This flag does not claim the service has no vacancies or prevent the user from searching it normally.

| Skill | Site | Reason for browser workflow |
|---|---|---|
| [apna-search](apna-search/SKILL.md) | apna.co | Public pages respond, but the user agreement restricts automated collection. |
| [hirist-search](hirist-search/SKILL.md) | hirist.tech | Honest CLI requests returned empty shells; do not circumvent the portal's controls. |
| [iimjobs-search](iimjobs-search/SKILL.md) | iimjobs.com | Honest CLI requests returned empty shells; no public search API verified. |
| [instahyre-search](instahyre-search/SKILL.md) | instahyre.com | Profile-based opportunities; no working anonymous public search verified. |
| [indeed-india-search](indeed-india-search/SKILL.md) | in.indeed.com | Direct search was blocked; public detail paths and automated collection are restricted. |
| [randstad-india-search](randstad-india-search/SKILL.md) | randstad.in | Public pages exist, but storage/reuse restrictions prevent assuming scraper permission. |
| [cutshort-search](cutshort-search/SKILL.md) | cutshort.io | Automated collection restricted; the documented API is for approved employer workspaces. |
| [aijobs-search](aijobs-search/SKILL.md) | Confirm the exact site first | aijobs.ai, aijobs.com, and the former aijobs.net are distinct destinations. |
| [foundit-search](foundit-search/SKILL.md) | foundit.in | Direct access was blocked; search/crawler restrictions apply. |
| [protocoljobs-search](protocoljobs-search/SKILL.md) | protocoljobs.ai | Public detail pages work, but query search is not verified and private `/api/` routes are disallowed. |
| [ycombinator-search](ycombinator-search/SKILL.md) | ycombinator.com / workatastartup.com | Public jobs exist; no documented search API contract verified. Applications require an account. |
| [otta-search](otta-search/SKILL.md) | Welcome to the Jungle, formerly Otta | Otta redirects to the current service; matched search requires sign-in. |

Access observations were checked on 23 October 2026. Each skill's `url-reference.md` links its primary evidence and records current limits. Recheck before changing a browser workflow into a CLI. A successful HTTP response, indexed job, sitemap, or permissive robots file alone does not establish permission or a working search integration.

## Identifying HTTP requests

CLI requests identify both the actual repository and the specific tool:

```text
mdshahansha/automated-switch-apply/1.0 (<portal>-search-cli)
```

The six existing CLIs and three new public-feed/API CLIs use this form. The shared public-page GET helper uses the same repository identity with `(web-research)`. They do not send a Chrome, Safari, or generic `Mozilla/5.0` identity. No candidate email, phone, resume, authentication token, or browser cookie is included in the User-Agent.

The owner/project name is used without a contact URL because `/apply` discovers portal hosts from URL literals in CLI source. Adding `github.com` to a helper's User-Agent would incorrectly make GitHub look like a job portal. Normal browser workflows use an actual browser, not a CLI pretending to be one.

An identifying User-Agent does not grant access. Respect each source's documented API/feed rules, attribution, caching, expiry, request limits, and `Retry-After`; stop at authentication or access blocks. Do not introduce proxies, private endpoints, or browser-header spoofing to turn a failed integration into a claimed success.

## Search and application boundaries

- A remote or worldwide label does not establish that the employer hires in India. Read country, timezone, and description restrictions together and surface contradictions.
- Search output is a shortlist, not an application or employer acknowledgement. Only record a submission after a portal receipt or another verified success signal.
- Retain the original source URL and requisition ID across portals to avoid duplicate applications.
- Candidate facts and document rules remain in `.claude/skills/job-application-assistant/`; the shared orchestration remains in `.claude/skills/job-scraper/`.
