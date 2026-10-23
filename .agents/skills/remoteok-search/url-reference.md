# Remote OK feed reference

Research date: 2026-10-23. Official current domain: `remoteok.com`.

| Source | Evidence |
|---|---|
| https://remoteok.com/faq | “Feeds & sponsorship” documents unauthenticated JSON and RSS feeds, tag filters, and credit/link-back requirements for redistribution. |
| https://remoteok.com/api | Public JSON array. Record zero contains `last_updated` and `legal`, not a vacancy. Legal notice requests source credit and followable original job links; logo requires permission. |
| https://remoteok.com/robots.txt | Generic `Allow: /`, `Crawl-delay: 1`. `/api` is not disallowed. AJAX `action=get_jobs`, profiles and tracking/spam paths have restrictions; this CLI never uses them. |
| https://remoteok.com/remote-jobs.rss | Official documented RSS alternative; unused by CLI. |

## Implemented request boundary

Every search/detail command requests **only** `https://remoteok.com/api`, with:

```text
User-Agent: mdshahansha/automated-switch-apply/1.0 (remoteok-search-cli)
Accept: application/json
```

No credentials or runtime packages. Redirects fail instead of following another
destination. Detail inputs are numeric IDs or HTTPS `remoteok.com`/`www.remoteok.com`
posting URLs under `/remote-jobs/`; query/hash tracking is removed and the host
normalizes to `remoteok.com`. Inputs are resolved to IDs locally and never fetched.
External hosts, credentials, nondefault ports, encoded path tricks and non-posting
paths fail before a request. Feed records with invalid URL/ID/title are skipped.

## Feed fields

| Feed field | Output |
|---|---|
| `id` | Required numeric string `id`; numeric safe-integer values also accepted. |
| `position` | Required plain-text `title`. |
| `company`, `location` | Plain text, or `null` if absent/empty. |
| `date` / `epoch` | ISO date; epoch seconds are fallback; `null` if neither valid. |
| `url` | Required same-host posting URL; its trailing ID must match `id`. |
| `description` | Tags stripped, entities decoded, paragraph/list breaks retained; nullable. |
| `tags` | Plain-text string array, empty when missing. |
| First `legal` record | Preserved under `meta.attribution` for search and `attribution` for detail. Never a result. |

Search keywords require every whitespace-delimited word in title/company/tags.
Location is a case-insensitive literal substring of the supplied location field.
`--jobage` compares dates with the current time, excluding missing and future dates.
The CLI preserves feed order, filters first, selects a fixed 20-row page, then caps
that page with `--limit`. It never implies empty location means Worldwide or that
Worldwide implies India eligibility. The CLI does not use the optional upstream
tag query filters; all filters are explicitly client-side.

Transport: 15-second timeout per attempt, including body reading; maximum three
attempts for 429/5xx only, minimum one-second delay with jitter. Numeric or HTTP-date
`Retry-After` is respected. If it requests over 30 seconds, exit `RETRY_LATER` instead
of retrying early. HTTP 403 stops immediately. HTTP 404 at the fixed API endpoint is an error.
An absent detail ID returns `null`; no archive or arbitrary posting fallback fetch.

Synthetic offline fixtures under `cli/tests/fixtures/` model this schema without
copying live descriptions. Live verification results are recorded below after testing.

## Live verification, 2026-10-23

- `search -q engineer --limit 5 --format json`: exit 0, 41 matching feed records,
  5 emitted. Actual examples: Lemon.io Senior DevOps Engineer, ID `1137557`;
  DuckDuckGo Senior Backend Engineer, ID `1137551`. Missing location was `null`.
- `detail 1137557 --format json`: exit 0, Lemon.io Senior DevOps Engineer,
  posting date `2026-10-22T12:58:28+00:00`, full multi-paragraph description and source attribution.
  [Original posting](https://remoteok.com/remote-jobs/remote-senior-devops-engineer-lemon-io-1137557).
- Each live command used one successful API request. No raw posting fetch or
  alternate host was requested. Search and detail access were verified before enabling dispatch.
- Upstream data contained mojibake in some strings and one suspicious nonsense
  posting. These are source-quality limitations, not claims of verified employment
  opportunities. The final implementation retains upstream wording and does not
  repair encoding or infer authenticity, India eligibility, or worldwide location.
