# Himalayas CLI

Official public JSON search/detail, no credentials or runtime packages required.
Run with Bun from the repository root:

```bash
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q react --country IN --exclude-worldwide true --limit 5 --format table
bun run .agents/skills/himalayas-search/cli/src/cli.ts detail writesonic/frontend-engineer --format plain
```

Use `--help` for all flags. `--location` aliases country, not city. All listings
are remote; no onsite/hybrid filter is supported. Country queries include
worldwide matches by default. Set `--exclude-worldwide true` deliberately and
review the full description before treating India eligibility as confirmed.

One API page, up to 20 jobs, is fetched per command. `--page` selects a 1-based
page; `--limit` caps that page client-side. `--jobage` filters last-updated age
locally and excludes unknown dates. A filtered empty page does not establish feed
exhaustion. JSON is `{meta:{count,page,...},results:[...]}`; all required fields
`id,title,company,location,date,url` exist, using null for missing metadata.
Detail JSON is `{meta:{source,status,url,...},result:job|null}`. 404 and 410 return
null with `not_found`/`closed`; other errors use JSON stderr and exit 1.

Development in this directory:

```bash
bun install
bun run typecheck
bun run test
```

Tests use synthetic fixtures, mocked fetch and CLI argument failures. They make
no live requests by default. Live verification is an explicit search followed by
detail on a returned ID, using the first two commands above or another current ID.

Requests identify `mdshahansha/automated-switch-apply/1.0 (himalayas-search-cli)`,
time out after 20 seconds, reject redirects, and retry 429/5xx at most three times
with bounded exponential backoff/jitter and `Retry-After`. A server delay over
30 seconds exits `RETRY_LATER`; it is never shortened. 403 is not retried.
No optional API key is consumed. Credit Himalayas and retain its applicationLink.
Official limits, schema and terms are linked in [url-reference.md](../url-reference.md).
