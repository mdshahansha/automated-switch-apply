---
name: weworkremotely-search
version: 1.0.0
description: >
  Search We Work Remotely's public RSS for worldwide remote vacancies and look
  up a posting present in that feed. Use for WWR jobs, We Work Remotely roles,
  remote developer jobs on WWR, or WWR par remote naukri. Geography is checked
  from disclosed listing fields; remote does not imply India eligibility.
context: fork
enabled: false
allowed-tools: Bash(bun run .agents/skills/weworkremotely-search/cli/src/cli.ts *)
---

# We Work Remotely search

Search the official public RSS with Bun and zero runtime dependencies. No login,
API key or HTML scraping is needed. Every command loads the feed once; transient
429/5xx errors retry the same fixed endpoint with bounded backoff. `detail`
looks up an entry in the current feed and never fetches a user-supplied URL.
The CLI honors `Retry-After`; waits over 30 seconds return `RETRY_LATER`.
A missing feed endpoint is an error, while missing detail membership is null.

The [official RSS page](https://weworkremotely.com/remote-job-rss-feed) permits RSS
use with attribution links back to We Work Remotely. Preserve `source` and posting
URLs when presenting results; keep volume low. This does not grant bulk reuse,
redistribution, or permission to submit applications. Read
[url-reference.md](url-reference.md) for feed fields and access evidence.

## Commands

```bash
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts search [flags]
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts detail <slug|url> [--format json|table|plain]
```

All search filters run **client-side over the currently published feed**:

| Flag | Meaning |
| --- | --- |
| `--query`, `-q` | Case-insensitive substring in title, company, skills, category or description; optional. |
| `--location`, `-l` | Substring in the disclosed region or country fields; optional. Not a work-authorization or India-eligibility check. |
| `--jobage <days>` | Positive whole days since publication; missing, invalid or future dates are excluded when set. |
| `--page <n>` | Positive page number; fixed 20-result pages after filtering. Default 1. |
| `--limit <n>` | Positive cap on the selected page, at most 20. Default 20. |
| `--format` | `json` (default), `table` or `plain`. |

```bash
# Engineering roles anywhere in the current feed
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts search -q engineer --limit 5 --format table

# React mentions in roles posted in the last 14 days
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts search -q React --jobage 14 --format table

# Only listings whose disclosed geography mentions India
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts search -q developer -l India --format json

# Second page; feed coverage and local filtering can produce zero matches
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts search -q engineer --page 2 --limit 5

# Supply the exact slug or WWR posting URL from a search result
bun run .agents/skills/weworkremotely-search/cli/src/cli.ts detail proxify-ab-senior-backend-developer-node-js-nest-js-4 --format plain
```

JSON search output is `{ "meta": { "count", "page", ... }, "results": [...] }`;
each result always includes `id`, `title`, `company`, `location`, `date`, `url`.
Missing values are `null`. Detail returns a job object with readable description,
or JSON `null` if absent from the current feed. Absence does **not** mean closed.
Errors use stderr JSON `{ "error", "code" }` with exit code 1.

| Format | Use |
| --- | --- |
| `json` | Programmatic search results and structured detail. |
| `table` | Tab-separated titles, companies, geography, dates and source links. |
| `plain` | Human-readable summaries or paragraph-preserving detail. |

The feed is a limited snapshot, not the full historical board. Region labels such
as “Anywhere in the World” can coexist with a narrower country list: inspect
`country` and the description before recommending a role to someone in India.
Missing dates and employer details stay unknown. Follow canonical `.claude/`
workflows for candidate fit and preparation.
