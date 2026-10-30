#!/usr/bin/env bun
import { runSearch, type SearchOpts } from "./commands/search.js"
import { runDetail } from "./commands/detail.js"
import { PortalError, writeError, type Format } from "./helpers.js"

const HELP = `himalayas-cli — public remote-jobs search and detail

USAGE
  bun run src/cli.ts search [flags]
  bun run src/cli.ts detail <company/job-slug|Himalayas-job-url> [--format json|table|plain]

SEARCH FLAGS
  --query, -q <text>        Keywords (optional; when present cannot be empty)
  --country, --location, -l <country>  ISO alpha-2 or country name (not a city)
  --worldwide <true|false>  Only worldwide-friendly jobs (default false)
  --exclude-worldwide <true|false>  Exclude worldwide matches; requires country
  --timezone <offset>      e.g. UTC+05:30 or -5
  --seniority <values>     Comma separated: Entry-level,Mid-level,Senior,Manager,Director,Executive
  --employment-type <values>  Full Time,Part Time,Contractor,Temporary,Intern,Volunteer,Other
  --company <slugs>        Comma-separated canonical company slugs
  --sort <value>           relevant|recent|salaryAsc|salaryDesc|nameAToZ|nameZToA|jobs
  --jobage <days>          Local last-updated-age filter; unknown dates excluded
  --page <n>               One 1-based API page, up to 20 jobs (default 1)
  --limit, -n <n>          Client-side result cap for that page (1..20)
  --format <value>         json (default)|table|plain

Source: Himalayas. Preserve applicationLink for Apply and link to Himalayas.
Country metadata is not a guarantee of eligibility; review the full description.
`

const SEARCH_FLAGS = new Set(["query", "country", "worldwide", "exclude-worldwide", "timezone", "seniority", "employment-type", "company", "sort", "jobage", "page", "limit", "format"])
const ALIASES: Record<string, string> = { q: "query", l: "country", location: "country", n: "limit" }

function fail(message: string): never { throw new PortalError(message, "BAD_ARG") }

export function parseArgs(argv: string[]): { command: "help" } | { command: "search"; options: SearchOpts } | { command: "detail"; id: string; format: Format } {
  if (argv.length === 1 && (argv[0] === "--help" || argv[0] === "-h")) return { command: "help" }
  const command = argv[0]
  if (!command) fail("A search or detail command is required; use --help")
  if (command !== "search" && command !== "detail") throw new PortalError(`Unknown command: ${command}`, "BAD_CMD")
  const flags: Record<string, string> = {}
  const positional: string[] = []
  let help = false
  for (let index = 1; index < argv.length; index++) {
    const token = argv[index]
    if (token === "--help" || token === "-h") { help = true; continue }
    if (!token.startsWith("-")) { positional.push(token); continue }
    const parts = token.replace(/^--?/, "").split("=")
    const name = ALIASES[parts[0]] ?? parts[0]
    if (!(command === "search" ? SEARCH_FLAGS : new Set(["format"])).has(name)) throw new PortalError(`Unknown flag: --${name}`, "UNKNOWN_FLAG")
    if (flags[name] !== undefined) fail(`Duplicate flag: --${name}`)
    if (parts.length > 2) fail(`Invalid value for --${name}`)
    const value = parts.length === 2 ? parts[1] : argv[++index]
    // Numeric timezone offsets may start with a minus; other flags cannot be
    // consumed as values, even when misspelled.
    if (value === undefined || (value.startsWith("-") && !(name === "timezone" && /^-\d+(?:\.\d+)?$/.test(value))) || !value.trim()) fail(`--${name} requires a non-empty value`)
    flags[name] = value.trim()
  }
  if (help) return { command: "help" }
  const format = flags.format ?? "json"
  if (!["json", "table", "plain"].includes(format)) fail("--format must be json|table|plain")
  if (command === "detail") {
    if (positional.length !== 1) fail("detail requires exactly one company/job-slug ID or job URL")
    return { command, id: positional[0], format: format as Format }
  }
  if (positional.length) fail("search does not accept positional arguments; use --query")
  const integer = (name: string, maximum = Number.MAX_SAFE_INTEGER): number | undefined => {
    const raw = flags[name]
    if (raw === undefined) return undefined
    const value = Number(raw)
    if (!/^\d+$/.test(raw) || !Number.isSafeInteger(value) || value < 1 || value > maximum) fail(`--${name} must be a whole number from 1 to ${maximum}`)
    return value
  }
  const bool = (name: string): boolean | undefined => {
    const raw = flags[name]
    if (raw === undefined) return undefined
    if (raw !== "true" && raw !== "false") fail(`--${name} must be true|false`)
    return raw === "true"
  }
  const csv = (name: string, values: string[]): string | undefined => {
    const raw = flags[name]
    if (raw === undefined) return undefined
    const list = raw.split(",").map(s => s.trim())
    if (list.some(s => !values.includes(s))) fail(`--${name} must use: ${values.join(", ")}`)
    return [...new Set(list)].join(",")
  }
  const worldwide = bool("worldwide")
  const excludeWorldwide = bool("exclude-worldwide")
  if (excludeWorldwide && !flags.country) fail("--exclude-worldwide true requires --country or --location")
  if (worldwide && excludeWorldwide) fail("--worldwide true conflicts with --exclude-worldwide true")
  if (flags.company && !flags.company.split(",").every(s => /^[a-z0-9][a-z0-9-]*$/.test(s.trim()))) fail("--company requires canonical company slugs separated by commas")
  if (flags.timezone && !/^(?:UTC)?[+-]?\d{1,2}(?:(?:\.\d{1,2})|(?::\d{2}))?$/i.test(flags.timezone)) fail("--timezone must be a numeric UTC offset, e.g. UTC+05:30")
  if (flags.timezone) {
    const raw = flags.timezone.replace(/^UTC/i, "")
    const [hours, minutes] = raw.split(":")
    const offset = minutes === undefined ? Number(hours) : Math.sign(Number(hours) || (raw.startsWith("-") ? -1 : 1)) * (Math.abs(Number(hours)) + Number(minutes) / 60)
    if (Math.abs(offset) > 14 || (minutes !== undefined && Number(minutes) >= 60)) fail("--timezone offset must be within -14..14 hours with valid minutes")
  }
  const sort = flags.sort
  if (sort && !["relevant", "recent", "salaryAsc", "salaryDesc", "nameAToZ", "nameZToA", "jobs"].includes(sort)) fail("Unsupported --sort value")
  return { command, options: { query: flags.query, country: flags.country, worldwide, excludeWorldwide,
    timezone: flags.timezone, seniority: csv("seniority", ["Entry-level", "Mid-level", "Senior", "Manager", "Director", "Executive"]),
    employmentType: csv("employment-type", ["Full Time", "Part Time", "Contractor", "Temporary", "Intern", "Volunteer", "Other"]),
    company: flags.company?.split(",").map(s => s.trim()).join(","), sort, page: integer("page") ?? 1,
    limit: integer("limit", 20), jobage: integer("jobage", 36500), format: format as Format } }
}

export async function main(argv = process.argv.slice(2)): Promise<number> {
  try {
    const args = parseArgs(argv)
    if (args.command === "help") { process.stdout.write(HELP); return 0 }
    return args.command === "search" ? await runSearch(args.options) : await runDetail(args.id, args.format)
  } catch (error) { writeError(error); return 1 }
}

if (import.meta.main) process.exitCode = await main()
