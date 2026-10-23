# We Work Remotely public RSS

Verified 2026-10-23 without authentication. The CLI uses only
https://weworkremotely.com/remote-jobs.rss (RSS 2.0, HTTP 200). No server-side
query, location, date or pagination parameters are used: filters and fixed
20-result pages operate on one fetched snapshot. The feed's channel `ttl` was 60
minutes; avoid repeatedly polling it.

Primary access references:

- https://weworkremotely.com/remote-job-rss-feed — official feed page explicitly permits using RSS with attribution links back to We Work Remotely.
- https://weworkremotely.com/robots.txt — public feed/posting surfaces were not disallowed; private account/admin/manage routes are restricted.
- https://weworkremotely.com/terms-and-conditions — general terms still apply; RSS permission is not a blanket bulk collection or redistribution licence.

The identifying User-Agent is
`mdshahansha/automated-switch-apply/1.0 (weworkremotely-search-cli)`.
The only requested destination is the fixed HTTPS feed URL. Redirects are
rejected; 403/auth errors are reported without bypass. Transient 429/5xx errors
retry that same endpoint with exponential backoff/jitter (up to six retries).
Numeric/date `Retry-After` is honored. A requested delay over 30 seconds produces
`RETRY_LATER` so the caller can try later; it never retries early. A feed-endpoint
404 is an HTTP error, not an empty job list.

## Observed item fields

| RSS field | Normalized field |
| --- | --- |
| `title` (`Company: Role`) | Split first `: ` into `company` and `title`; absent company is null. |
| `link`, fallback `guid` | Validated exact HTTPS WWR posting URL and slug `id`. |
| `region`, fallback `country` | `location`; raw region/country/state also retained. State is not substituted for remote eligibility. |
| `pubDate` | ISO UTC `date`, null when invalid/missing. |
| `description` | Readable text with paragraphs/list boundaries; XML-escaped HTML and CDATA supported. |
| `category`, `type`, `skills` | `category`, `employmentType`, `skills` or null. |
| `expires_at` | ISO UTC `expiresAt` or null; no invented active/closed flag. |

Malformed items without a title or valid source URL are skipped independently;
duplicate source slugs are deduplicated. Search omits the long description, while
detail includes it. No external logo, employer website or application link is
fetched. Output retains WWR attribution and posting links.

`detail <slug|url>` loads the same public feed, matches an exact posting slug, and
returns null when missing. Only `https://weworkremotely.com/remote-jobs/<slug>`
with no credentials, query, fragment or alternate host is accepted. A supplied
URL never becomes a network destination. Missing feed membership establishes
neither deletion nor closure.

Observed example: https://weworkremotely.com/remote-jobs/proxify-ab-senior-backend-developer-node-js-nest-js-4
— Proxify AB, Senior Backend Developer (Node.js / Nest.js), region Anywhere in
the World, publication 2026-10-19, expiry 2026-11-18. Feed coverage and availability
change; this is a parsing example, not a permanent recommendation.
