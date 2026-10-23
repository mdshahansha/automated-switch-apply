#!/usr/bin/env bun
import { CLIError, formatJobs, loadJobs, postingSlug, type Format, type Job } from "./helpers.js"
import { searchJobs, type SearchOpts } from "./commands/search.js"
import { detailJob } from "./commands/detail.js"

const HELP = `weworkremotely-cli — public RSS search (all filters are client-side)

USAGE
  bun run src/cli.ts search [--query|-q <text>] [--location|-l <text>]
      [--jobage <days>] [--page <n>] [--limit <n>] [--format json|table|plain]
  bun run src/cli.ts detail <slug|url> [--format json|table|plain]

Default format: json. Page: 1; fixed page size: 20; limit caps that page.
Location matches disclosed region/country text, not eligibility or headquarters.
Unknown dates are excluded when --jobage is set. Feed coverage is not exhaustive.
Detail searches the current feed only; missing entries return JSON null.
Source: We Work Remotely (posting links are retained for attribution).
`

interface Dependencies {
  load?: () => Promise<Job[]>
  stdout?: (text: string) => void
  stderr?: (text: string) => void
  now?: number
}

function parseArgs(argv: string[]) {
  const command = argv[0]
  if (!command) throw new CLIError("A command is required; use --help", "BAD_CMD")
  if (["--help", "-h"].includes(command) && argv.length === 1) return { help: true } as const
  if (!["search", "detail"].includes(command)) throw new CLIError(`Unknown command: ${command}`, "BAD_CMD")
  const allowed = new Set(command === "search" ? ["query", "location", "jobage", "page", "limit", "format"] : ["format"])
  const aliases: Record<string, string> = { q: "query", l: "location" }
  const flags: Record<string, string> = {}
  const positional: string[] = []
  let help = false
  for (let i = 1; i < argv.length; i++) {
    const token = argv[i]
    if (["--help", "-h"].includes(token)) { help = true; continue }
    if (token.startsWith("-")) {
      const name = token.replace(/^-{1,2}/, "")
      const key = aliases[name] ?? name
      if (!allowed.has(key)) throw new CLIError(`Unknown flag: ${token}`, "UNKNOWN_FLAG")
      if (flags[key] !== undefined) throw new CLIError(`Repeated flag: ${token}`, "BAD_ARG")
      const value = argv[++i]
      if (!value || value.startsWith("-") || !value.trim()) throw new CLIError(`${token} requires a non-empty value`, "BAD_ARG")
      flags[key] = value.trim()
    } else positional.push(token)
  }
  if (positional.length > (command === "detail" ? 1 : 0)) throw new CLIError("Unexpected positional argument", "BAD_ARG")
  if (help) return { help: true } as const
  const format = flags.format ?? "json"
  if (!["json", "table", "plain"].includes(format)) throw new CLIError("--format must be json|table|plain", "BAD_ARG")
  const integer = (key: string, fallback?: number) => {
    if (flags[key] === undefined) return fallback
    if (!/^[1-9]\d*$/.test(flags[key]) || !Number.isSafeInteger(Number(flags[key]))) {
      throw new CLIError(`--${key} must be a positive safe integer`, "BAD_ARG")
    }
    return Number(flags[key])
  }
  if (command === "detail") {
    if (!positional[0]) throw new CLIError("detail requires a posting slug or URL", "NO_ID")
    postingSlug(positional[0]) // reject arbitrary destinations before any network access
  }
  const opts: SearchOpts = { query: flags.query, location: flags.location,
    jobage: integer("jobage"), page: integer("page", 1)!, limit: integer("limit") }
  return { help: false, command, format: format as Format, input: positional[0], opts } as const
}

export async function main(argv = process.argv.slice(2), deps: Dependencies = {}): Promise<number> {
  const stdout = deps.stdout ?? ((text) => process.stdout.write(text))
  const stderr = deps.stderr ?? ((text) => process.stderr.write(text))
  try {
    const args = parseArgs(argv)
    if (args.help) { stdout(HELP); return 0 }
    const jobs = await (deps.load ?? loadJobs)()
    if (args.command === "search") {
      const payload = searchJobs(jobs, args.opts, deps.now)
      const summaries = payload.results.map((j) => ({ ...j, description: null }))
      stdout((args.format === "json" ? JSON.stringify(payload, null, 2) : formatJobs(summaries, args.format)) + "\n")
    } else {
      const job = detailJob(jobs, args.input!)
      stdout((args.format === "json" ? JSON.stringify(job, null, 2) : formatJobs(job ? [job] : [], args.format, true)) + "\n")
    }
    return 0
  } catch (error) {
    stderr(JSON.stringify({ error: error instanceof Error ? error.message : String(error),
      code: error instanceof CLIError ? error.code : "INTERNAL_ERROR" }) + "\n")
    return 1
  }
}

if (import.meta.main) process.exit(await main())
