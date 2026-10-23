---
name: himalayas-search
version: 1.0.0
description: >
  Search Himalayas public remote job listings worldwide or by an explicitly
  requested country, and read a specific Himalayas posting. Use for Himalayas
  jobs, remote developer jobs, work from home India, remote React jobs, or remote
  Node.js jobs, or भारत में रिमोट नौकरियां. The portal and CLI use English;
  country filtering is supported, not city matching.
context: fork
enabled: true
allowed-tools: Bash(bun run .agents/skills/himalayas-search/cli/src/cli.ts *)
---

# Himalayas Search

Search the official public JSON API without credentials. The CLI runs with Bun
and zero runtime dependencies. Use this source for remote roles, country and
timezone restrictions, salary metadata, and full job descriptions.

```bash
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q react --country IN --exclude-worldwide true --limit 5 --format table
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "node.js" --location India --timezone "UTC+05:30" --sort recent --format json
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q "full stack" --worldwide true --jobage 14 --format table
bun run .agents/skills/himalayas-search/cli/src/cli.ts search -q react --country IN --page 2 --limit 5 --format plain
bun run .agents/skills/himalayas-search/cli/src/cli.ts detail writesonic/frontend-engineer --format plain
```

Search flags:

| Flag | Meaning |
| --- | --- |
| `--query`, `-q` | Optional nonempty keyword string |
| `--country`, `--location`, `-l` | Country name or ISO alpha-2; cities unsupported |
| `--worldwide true|false` | Worldwide-friendly jobs only when true |
| `--exclude-worldwide true|false` | Exclude worldwide matches; true requires country |
| `--timezone` | UTC offset, e.g. `UTC+05:30` or `-5` |
| `--seniority` | Comma-separated `Entry-level,Mid-level,Senior,Manager,Director,Executive` |
| `--employment-type` | Comma-separated `Full Time,Part Time,Contractor,Temporary,Intern,Volunteer,Other` |
| `--company` | Comma-separated canonical company slugs from results |
| `--sort` | `relevant`, `recent`, `salaryAsc`, `salaryDesc`, `nameAToZ`, `nameZToA`, `jobs` |
| `--jobage` | Positive days; local last-updated-age filter, excludes unknown dates |
| `--page` | One 1-based API page, default 1; up to 20 jobs |
| `--limit`, `-n` | Client cap of 1–20 results within that page |
| `--format` | `json` default, `table`, or `plain` |

`detail <id|url>` accepts the returned `company/job-slug` ID, canonical Himalayas
job URL, API detail URL, or returned Apply URL. It supports all three formats.
Missing jobs return `result:null` with `not_found`; closed jobs use `closed`.
Other failures exit 1 with JSON `{error,code}` on stderr.

JSON search output is `{meta:{count,page,...},results:[...]}`. Every result includes
`id,title,company,location,date,url`; unknown values remain null. Restrictions,
salary, expiry, readable description, and unchanged `applicationLink` are retained.

Country eligibility is distinct from worldwide availability. A country query
includes worldwide matches unless `--exclude-worldwide true` is supplied. Preserve
`locationRestrictions` and `timezoneRestrictions`, then read the description before
calling a role India eligible: source metadata can conflict with the employer text.
No city, visa, work-authorization or guaranteed eligibility filter is offered.

`date` comes from `pubDate`, which means last updated; it is not proof of original
posting date. `--jobage` filters that timestamp locally. One API page is fetched per
command. For more, increment `--page`, dedupe IDs, and stop only when the API page
itself has no jobs. A short page or an empty page after local filters is inconclusive.
`meta.fetchedCount` and `meta.skippedMalformed` distinguish these cases.

Credit **Himalayas** with a visible source link when presenting results. Use the
returned `applicationLink` unchanged for Apply. Cache daily-refreshed data, remove
expired jobs, and avoid forwarding listings to third-party job boards/aggregators.
The CLI retries 429/5xx with bounded backoff and never retries 403. For schemas,
limits and official terms, read [url-reference.md](url-reference.md).
