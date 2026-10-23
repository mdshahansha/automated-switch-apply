#!/usr/bin/env bun
import { runSearch } from "./commands/search.js"
import { runDetail } from "./commands/detail.js"
import { CLIError, output, writeError, type Runtime } from "./helpers.js"

const HELP = `remoteok-cli — Remote OK public-feed search (read-only)

USAGE
  bun run src/cli.ts search [--query <text>] [flags]
  bun run src/cli.ts detail <numeric-id|https://remoteok.com/remote-jobs/...> [--format <fmt>]

SEARCH FLAGS (all filters run client-side over one current feed)
  --query, -q <text>     All words match title, company or tags; optional.
  --location, -l <text>  Location-text substring only; optional, not eligibility proof.
  --jobage <days>       Whole days >=1; omit for all available dates.
  --page <n>            1-indexed, fixed 20-result pages; default 1.
  --limit, -n <n>       Client-side cap within the selected page; default 20.
  --format <fmt>        json (default) | table | plain; also accepted by detail.
  --help, -h            Print usage.

Data source: Remote OK — https://remoteok.com/api
Credit Remote OK and retain original posting links when sharing.
Remote/worldwide labels do not establish India eligibility; check each posting.
`

const ALIASES: Record<string, string> = { q: "query", l: "location", n: "limit", h: "help" }
const ACCEPTED: Record<string, Set<string>> = {
  search: new Set(["query", "location", "jobage", "page", "limit", "format", "help"]),
  detail: new Set(["format", "help"]),
}

function positiveInt(name: string, value: string | undefined, fallback?: number): number | undefined {
  if (value === undefined) return fallback
  if (!/^\d+$/.test(value) || !Number.isSafeInteger(Number(value)) || Number(value) < 1)
    throw new CLIError(`--${name} must be a whole number of at least 1`, "BAD_ARG")
  return Number(value)
}

export async function main(argv: string[], runtime: Runtime = {}): Promise<number> {
  try {
    if (argv.length === 1 && ["--help", "-h"].includes(argv[0])) { output(HELP.trimEnd(), runtime); return 0 }
    const command = argv[0]
    if (!command) throw new CLIError("A command is required; use --help", "BAD_CMD")
    if (!Object.hasOwn(ACCEPTED, command)) throw new CLIError(`Unknown command '${command}'; use --help`, "BAD_CMD")
    const flags: Record<string, string> = {}
    const positional: string[] = []
    let help = false
    for (let index = 1; index < argv.length; index++) {
      const argument = argv[index]
      if (!argument.startsWith("-")) { positional.push(argument); continue }
      const match = argument.match(/^(?:--([a-z][a-z-]*)|-([a-z]))(?:=(.*))?$/)
      if (!match) throw new CLIError(`Invalid flag '${argument}'`, "UNKNOWN_FLAG")
      const name = ALIASES[match[1] ?? match[2]] ?? match[1] ?? match[2]
      if (!ACCEPTED[command].has(name)) throw new CLIError(`Unknown flag '${argument}' for ${command}`, "UNKNOWN_FLAG")
      if (name === "help") {
        if (match[3] !== undefined) throw new CLIError("--help does not take a value", "BAD_ARG")
        help = true; continue
      }
      if (Object.hasOwn(flags, name)) throw new CLIError(`--${name} supplied more than once`, "BAD_ARG")
      let value = match[3]
      if (value === undefined && argv[index + 1] !== undefined && !argv[index + 1].startsWith("-")) value = argv[++index]
      if (value === undefined || !value.trim()) throw new CLIError(`--${name} requires a non-empty value`, "BAD_ARG")
      flags[name] = value.trim()
    }
    if (positional.length > (command === "detail" ? 1 : 0)) throw new CLIError("Unexpected positional argument", "BAD_ARG")
    const format = flags.format ?? "json"
    if (!["json", "table", "plain"].includes(format)) throw new CLIError("--format must be json|table|plain", "BAD_ARG")
    const jobage = positiveInt("jobage", flags.jobage)
    const page = positiveInt("page", flags.page, 1)!
    const limit = positiveInt("limit", flags.limit, 20)!
    if (page > Math.floor(Number.MAX_SAFE_INTEGER / 20)) throw new CLIError("--page is too large", "BAD_ARG")
    if (help) { output(HELP.trimEnd(), runtime); return 0 }
    if (command === "search") {
      await runSearch({ query: flags.query, location: flags.location, jobage, page, limit, format: format as "json" | "table" | "plain" }, runtime)
    } else {
      if (!positional[0]) throw new CLIError("detail requires an ID or Remote OK posting URL", "NO_ID")
      await runDetail({ input: positional[0], format: format as "json" | "table" | "plain" }, runtime)
    }
    return 0
  } catch (error) { writeError(error, runtime); return 1 }
}

if (import.meta.main) process.exitCode = await main(process.argv.slice(2))
