# Remote OK CLI

Read-only Bun/TypeScript search over Remote OK's official public JSON feed.
Zero runtime dependencies; `bun install` adds only development types and TypeScript.

```bash
bun run src/cli.ts search -q engineer --limit 5 --format table
bun run src/cli.ts search -q React -l India --jobage 30
bun run src/cli.ts detail <id-from-search> --format plain
bun run src/cli.ts --help
bun install
bun run typecheck
bun run test
```

Search supports optional `--query/-q`, optional `--location/-l`, `--jobage`,
`--page`, `--limit/-n`, and `--format json|table|plain`. All filters run **locally**
over one current feed; no filter parameters are sent upstream. Pages contain 20
filtered results; limit caps only the selected page. API feed order is retained.

`detail` accepts an ID or same-host HTTPS `/remote-jobs/` URL and looks it up in the
same feed. It never fetches the supplied URL, follows redirects, or contacts employer
sites. An ID missing from the current feed returns JSON `null` with exit 0. This
does not establish that the role is closed. Errors are JSON on stderr with exit 1.

Every listing includes ID, title, company, location, date and URL. Missing optional
<<<<<<< HEAD
fields are `null`. Descriptions preserve paragraph/list breaks. Disclosed positive
`salary_min`/`salary_max` bounds are retained; absent currency and period stay
unknown, and zero feed placeholders are not reported as a salary. Output includes
=======
fields are `null`. Descriptions preserve paragraph/list breaks. Output includes
>>>>>>> origin/master
Remote OK attribution; preserve the source name, legal notice and original links
when sharing. See [official API/attribution evidence](../url-reference.md).

Location filtering is literal location-text matching, not geographic eligibility
inference. Worldwide/remote does not prove permission to work from India. Read the
original role's restrictions. The API may return only a recent subset of vacancies.

Requests identify this maintainer/tool honestly, time out after 15 seconds, and
retry 429/5xx at most twice with at least one second between attempts. `Retry-After`
is respected; waits over 30 seconds stop with `RETRY_LATER`. HTTP 403 is never retried.
Space separate invocations at least one second apart. There is no token, proxy,
browser impersonation, internal endpoint, or authentication fallback.

Tests are offline by default. They exercise synthetic feed fixtures, mock HTTP
responses, fixed page/filter semantics, actual executable argument failures,
URL boundaries, source metadata, timeout and retry behavior. They never contact
Remote OK. Run a separate low-volume live search/detail pair when revalidating access.
