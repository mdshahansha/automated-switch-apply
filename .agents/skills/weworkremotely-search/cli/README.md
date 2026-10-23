# We Work Remotely RSS CLI

Run with Bun; no runtime packages or credentials are required:

```bash
bun run src/cli.ts search -q engineer --limit 5 --format table
bun run src/cli.ts detail <slug-from-search> --format plain
```

Only the official all-jobs RSS is loaded. Query/location/age filtering and
20-result pages are client-side; the feed is not an exhaustive board search.
`--location` matches region/country text and does not prove work eligibility.
Detail matches a slug in that same feed; a missing entry returns JSON null and
does not imply closure. All errors are JSON on stderr, exit 1.

Keep the We Work Remotely attribution and direct posting links. The official
[RSS page](https://weworkremotely.com/remote-job-rss-feed) permits RSS use with
linkback; do not infer permission for bulk reuse or redistribution. The channel
TTL was 60 minutes. No posting HTML, images or arbitrary supplied URLs are fetched.
See [the endpoint reference](../url-reference.md) and [skill](../SKILL.md).

Development checks (dev dependencies only):

```bash
bun install
bun run typecheck
bun run test
```

Tests are offline, using a synthetic RSS fixture and mocked fetch. No default
test makes a live network request. Manual live smoke commands are shown above.
