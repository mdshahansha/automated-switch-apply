# Himalayas public jobs API

Verified 2026-10-23 using the honest research User-Agent
`job-search-research/1.0 (personal, read-only access verification)`.
CLI verification uses `mdshahansha/automated-switch-apply/1.0 (himalayas-search-cli)`.

Primary sources:

- [API overview](https://himalayas.app/api)
- [Technical API reference](https://himalayas.app/docs/remote-jobs-api)
- [OpenAPI 3.1 schema](https://himalayas.app/docs/openapi.json)
- [API terms, section 113](https://himalayas.app/terms)
- [robots.txt](https://himalayas.app/robots.txt)

## Endpoints

| Endpoint | Purpose |
| --- | --- |
| `GET https://himalayas.app/jobs/api/search` | Filtered jobs, 1-based `page` |
| `GET https://himalayas.app/jobs/api/companies/:company/jobs/:slug` | Single job; 200 open, 410 closed, 404 unknown |
| `GET https://himalayas.app/jobs/api` | Full feed with opaque `cursor` and `limit` up to 20; not used by this CLI |
| `https://himalayas.app/jobs/rss` | Optional recent-jobs RSS; not used by this CLI |

Search query parameters supported by the CLI:

| API parameter | CLI flag | Values |
| --- | --- | --- |
| `q` | `--query`, `-q` | Free text |
| `country` | `--country`, `--location`, `-l` | ISO alpha-2, country name/slug/abbreviation |
| `worldwide` | `--worldwide true|false` | Boolean |
| `exclude_worldwide` | `--exclude-worldwide true|false` | Boolean; only useful with country |
| `timezone` | `--timezone` | Numeric UTC offset, `UTC-5`, `UTC+05:30` |
| `seniority` | `--seniority` | Comma-separated Entry-level, Mid-level, Senior, Manager, Director, Executive |
| `employment_type` | `--employment-type` | Comma-separated Full Time, Part Time, Contractor, Temporary, Intern, Volunteer, Other |
| `company` | `--company` | Comma-separated canonical company slugs |
| `sort` | `--sort` | relevant, recent, salaryAsc, salaryDesc, nameAToZ, nameZToA, jobs |
| `page` | `--page` | Positive integer, starts at 1 |

`--jobage` and `--limit` are local filters, not API parameters. Limits are per
selected page, not an automatic multi-page crawl. Search has no cursor; keep
requesting pages until the API returns no jobs. Pages can be short before the end;
`totalCount` is approximate and can be a day old. Dedupe `guid` across pages.
Browse-only `offset` is deprecated; prefer opaque `nextCursor` if adding full sync.

## Observed data structure

Search returned `{comments,updatedAt,offset,limit,totalCount,jobs}`. `updatedAt` is
Unix seconds; search `limit` was 20. `nextCursor` belongs to browse only.

| API field | Type / normalized behavior |
| --- | --- |
| `guid` | Canonical URL; supplies `url` and `id:company/job-slug` |
| `title`, `companyName` | Strings; entity decoding; missing -> null |
| `companySlug`, `companyLogo`, `employmentType`, `excerpt` | Optional strings |
| `locationRestrictions` | Country string array; empty explicitly means worldwide; missing stays null |
| `timezoneRestrictions` | Numeric UTC-offset array; missing stays null |
| `seniority`, `categories`, `parentCategories` | String arrays in observed data |
| `description` | HTML; normalized to readable text preserving paragraphs/bullets |
| `pubDate` | Last updated Unix seconds; normalized `date` ISO8601, never synthesized |
| `expiryDate` | Latest listed-through Unix seconds; normalized `expiresAt`; may close earlier |
| `minSalary`, `maxSalary` | Number or null; no currency conversion |
| `salaryPeriod`, `currency` | Strings; missing stays null |
| `applicationLink` | Apply URL; preserve unchanged including `?utm_source=api` |

Malformed records missing a valid identity or title are skipped and counted in
metadata. Unknown company/date/location/salary fields stay null. Expired jobs are
locally excluded; future dates are excluded when an age filter is used.

Detail returns `{job:{...same fields...}}`. A 410 body can include
`{ok:false,errors,expired:true,expiryDate}`. The CLI returns a null result for
404/410 and preserves their different meaning. It accepts only exact HTTPS
`himalayas.app` job paths, rejecting credentials, unrelated paths and hosts.

## Observed live cases

Search:
`https://himalayas.app/jobs/api/search?q=react&country=IN&exclude_worldwide=true&sort=recent&page=1`
returned India-restricted roles including **Writesonic — Frontend Engineer**,
`locationRestrictions:["India"]`, `timezoneRestrictions:[5.5]`.
`https://himalayas.app/jobs/api/companies/writesonic/jobs/frontend-engineer`
returned 200 with a readable React job description.

CLI live verification on the same date emitted 5/20 fetched results, zero malformed
records, and successfully read `writesonic/frontend-engineer` with the CLI's honest
User-Agent. `--country India` also returned an India-restricted React result;
`--country Mumbai` failed HTTP 400 with JSON stderr and exit 1. Country names are
supported; city input is not silently ignored.

The same query with worldwide matches included produced a Tabby role labeled
worldwide in location metadata, while its description said Europe only. Country
or worldwide metadata is evidence to review, not a guarantee of applicant eligibility.

## Access and attribution

The official API requires no key and explicitly supports personal integrations
and AI tools. Unkeyed search/browse requests share a public allowance; its exact
numeric limit is not specified. Optional account keys receive 60/minute and
10,000/day, but this CLI does not require or send credentials. Official public
detail limit: 60/minute. Honor `429` and `Retry-After`; cache data. Data updates
within 24 hours; single-job answers cache up to 10 minutes. The CLI bounds each
request to 20 seconds and makes at most three retries on 429/5xx. If Retry-After
exceeds 30 seconds it exits `RETRY_LATER` instead of retrying prematurely;
redirects and 403 are not retried.

The source requires visible Himalayas credit, unchanged Apply links, expiry
removal, and no passing listings to third-party job boards/aggregators, Google
Jobs or LinkedIn Jobs. These are API terms for personal and commercial use.
`robots.txt` permits general access but excludes apply and paginated HTML paths;
use the intended API rather than protected job HTML pages. No browser UA spoofing.
