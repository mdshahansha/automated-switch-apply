---
name: remoteok-search
version: 1.0.0
description: >
  Search Remote OK's public feed for remote jobs worldwide and look up a posting by
  ID or Remote OK URL. Use for Remote OK jobs, RemoteOK software roles, Remote OK
  India remote jobs, रिमोट ओके पर नौकरी खोजें, or remoteok par naukri. Location is
  an optional client-side text filter; worldwide labels do not prove India eligibility.
context: fork
enabled: true
allowed-tools: Bash(bun run .agents/skills/remoteok-search/cli/src/cli.ts *)
---

# Remote OK search

Read the official, unauthenticated [Remote OK JSON feed](https://remoteok.com/api)
using the bundled Bun CLI. It has zero runtime dependencies. Each command reads
that feed once, excluding bounded retries; detail is a lookup in the current feed.
Read [url-reference.md](url-reference.md) for feed fields, attribution and access evidence.

## Commands

```bash
bun run .agents/skills/remoteok-search/cli/src/cli.ts search [flags]
bun run .agents/skills/remoteok-search/cli/src/cli.ts detail <id|Remote-OK-posting-url> [--format json|table|plain]
```

| Search flag | Meaning |
|---|---|
| `--query`, `-q` | Optional keywords; every word must occur in title, company or tags. |
| `--location`, `-l` | Optional case-insensitive location-text substring; client-side. |
| `--jobage` | Whole days ≥1; omit to retain all available dates. Unknown/future dates are excluded when set. |
| `--page` | 1-indexed fixed pages of 20 results after filtering; default 1. |
| `--limit`, `-n` | Cap within the selected page; default 20. Does not change page size. |
| `--format` | `json` (default), `table` or `plain`. |

All filtering and pagination occur locally in feed order. The API may expose only
a recent subset of jobs; results are not an exhaustive job-market search. Missing
detail returns JSON `null`, which means absent from this feed, not confirmed closed.
Upstream text may contain encoding artifacts or low-quality postings; review the
original listing. The CLI preserves upstream wording rather than correcting it.
Errors use stderr JSON `{ "error": "...", "code": "..." }` with exit code 1.

## Examples

```bash
# Broad engineering search; review each posting's location restrictions
bun run .agents/skills/remoteok-search/cli/src/cli.ts search -q engineer --limit 5 --format table

# React roles whose location text explicitly contains India
bun run .agents/skills/remoteok-search/cli/src/cli.ts search -q React -l India --format table

# Search Worldwide labels separately; verify India eligibility in the description
bun run .agents/skills/remoteok-search/cli/src/cli.ts search -q React -l Worldwide --format json

# Recent Java roles, second fixed-size page
bun run .agents/skills/remoteok-search/cli/src/cli.ts search -q Java --jobage 30 --page 2 --limit 5

# Use an ID returned by a current search; example ID may expire from the feed
bun run .agents/skills/remoteok-search/cli/src/cli.ts detail 1137557 --format plain
```

## Attribution and workflow

The official FAQ permits free public JSON/RSS feeds. Credit **Remote OK** and retain
each original posting link whenever sharing results; preserve the feed's legal notice
in JSON metadata. Do not use its logo without permission. [Official FAQ](https://remoteok.com/faq).

The CLI uses an honest tool-identifying User-Agent. Keep requests low-volume and
space commands at least one second apart. It times out requests, retries 429/5xx
at most twice, respects `Retry-After` up to 30 seconds, and stops for longer waits.
It never retries 403, fetches supplied posting URLs, or follows redirects.

A location text match is not a work-authorization decision. Do not silently include
Worldwide jobs as India-eligible. Read each description for country, timezone,
contracting and eligibility requirements. For fit evaluation, use `CLAUDE.md` and
the canonical methodology in `.claude/skills/job-application-assistant/`.

Search authorization does not authorize submitting applications, sending messages
or uploading documents. Open the original link for an application only within the
user's requested scope; the user handles sign-in/challenges through the normal UI.

| Output | Use |
|---|---|
| JSON | `{meta:{count,page,...},results:[...]}`; ID/title/company/location/date/URL always present; missing optional values are `null`. |
| Table | Compact tab-separated rows with original links and source credit. |
| Plain | Readable listing text; detail includes the description with paragraph breaks. |
