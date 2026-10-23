export const API_URL = "https://remoteok.com/api"
export const USER_AGENT = "mdshahansha/automated-switch-apply/1.0 (remoteok-search-cli)"
export const PAGE_SIZE = 20

export class CLIError extends Error {
  constructor(message: string, public code: string) { super(message) }
}

export interface Job {
  id: string
  title: string
  company: string | null
  location: string | null
  date: string | null
  url: string
  description: string | null
  tags: string[]
  source: "Remote OK"
}

export interface Attribution {
  name: "Remote OK"
  url: string
  notice: string | null
}

export interface Feed { jobs: Job[]; attribution: Attribution }
export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>
export interface Runtime {
  fetchImpl?: FetchLike
  sleep?: (ms: number) => Promise<void>
  now?: () => number
  random?: () => number
  timeoutMs?: number
  out?: (text: string) => void
  err?: (text: string) => void
}

function text(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null
}

/** Only Remote OK HTTPS posting URLs are accepted; inputs are never fetched. */
export function normalizePostingURL(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim() || value.includes("\\")) return null
  try {
    const url = new URL(value, "https://remoteok.com")
    if (url.protocol !== "https:" || !["remoteok.com", "www.remoteok.com"].includes(url.hostname)
      || url.username || url.password || url.port) return null
    if (!/^\/remote-jobs\/(?:remote-[a-z0-9-]+-)?\d+\/?$/i.test(url.pathname)) return null
    url.hostname = "remoteok.com"
    url.pathname = url.pathname.replace(/\/$/, "")
    url.search = ""
    url.hash = ""
    return url.toString()
  } catch { return null }
}

export function detailID(input: string): string {
  if (/^\d+$/.test(input)) return input
  // Detail accepts an absolute same-host URL, not arbitrary relative paths.
  if (!/^https:\/\//i.test(input)) throw new CLIError("detail requires a numeric ID or HTTPS Remote OK posting URL", "BAD_ARG")
  const url = normalizePostingURL(input)
  if (!url) throw new CLIError("detail URL must be an HTTPS remoteok.com /remote-jobs/ posting URL", "BAD_ARG")
  return new URL(url).pathname.match(/(\d+)$/)![1]
}

export function htmlToText(html: string): string {
  const entities: Record<string, string> = {
    amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
    ndash: "–", mdash: "—", lsquo: "‘", rsquo: "’", ldquo: "“", rdquo: "”", hellip: "…", bull: "•",
  }
  return html
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1\s*>/gi, "")
    .replace(/<br\b[^>]*>/gi, "\n")
    .replace(/<li\b[^>]*>/gi, "\n- ")
    .replace(/<\/(?:p|div|h[1-6]|ul|ol|section|article)\s*>/gi, "\n\n")
    .replace(/<[^>]*>/g, "")
    .replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, entity: string) => {
      if (!entity.startsWith("#")) return entities[entity.toLowerCase()] ?? whole
      const codepoint = entity[1].toLowerCase() === "x" ? parseInt(entity.slice(2), 16) : Number(entity.slice(1))
      return codepoint > 0 && codepoint <= 0x10ffff && !(codepoint >= 0xd800 && codepoint <= 0xdfff)
        ? String.fromCodePoint(codepoint) : whole
    })
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/g, "")
    .replace(/[ \t]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
}

function nullableText(value: unknown): string | null {
  const raw = text(value)
  return raw ? htmlToText(raw) || null : null
}

export function parseFeed(value: unknown): Feed {
  if (!Array.isArray(value)) throw new CLIError("Remote OK API response must be a JSON array", "BAD_RESPONSE")
  const first = value[0]
  const attribution: Attribution = {
    name: "Remote OK", url: "https://remoteok.com", notice: first && typeof first === "object" ? text(first.legal) : null,
  }
  const jobs: Job[] = []
  const seen = new Set<string>()
  for (let index = 0; index < value.length; index++) {
    const row = value[index]
    if (!row || typeof row !== "object" || Array.isArray(row)) continue
    // The first record is legal/update metadata, never a vacancy.
    if (index === 0 && ("legal" in row || "last_updated" in row)) continue
    const id = typeof row.id === "number" && Number.isSafeInteger(row.id) && row.id > 0 ? String(row.id) : text(row.id)
    const title = nullableText(row.position)
    const url = normalizePostingURL(row.url)
    if (!id || !/^\d+$/.test(id) || !title || !url || seen.has(id)) continue
    if (new URL(url).pathname.match(/(\d+)$/)?.[1] !== id) continue
    let timestamp = typeof row.date === "string" ? Date.parse(row.date) : NaN
    if (!Number.isFinite(timestamp) && typeof row.epoch === "number") timestamp = row.epoch * 1000
    const date = Number.isFinite(timestamp) && !Number.isNaN(new Date(timestamp).valueOf()) ? new Date(timestamp).toISOString() : null
    jobs.push({
      id, title, company: nullableText(row.company), location: nullableText(row.location), date, url,
      description: nullableText(row.description),
      tags: Array.isArray(row.tags) ? [...new Set((row.tags as unknown[]).map(nullableText).filter((v): v is string => v !== null))] : [],
      source: "Remote OK",
    })
    seen.add(id)
  }
  return { jobs, attribution }
}

function retryDelay(header: string | null, attempt: number, now: number, random: number): number {
  let fromHeader = 0
  if (header) {
    const seconds = /^\d+(?:\.\d+)?$/.test(header.trim()) ? Number(header.trim()) : NaN
    fromHeader = Number.isFinite(seconds) ? seconds * 1000 : Math.max(0, Date.parse(header) - now)
    if (!Number.isFinite(fromHeader)) fromHeader = 0
  }
  // Never retry sooner than Retry-After. Stop instead of sleeping unboundedly.
  if (fromHeader > 30_000) throw new CLIError(`Remote OK requests waiting ${Math.ceil(fromHeader / 1000)} seconds; try later`, "RETRY_LATER")
  return Math.max(1000, fromHeader, 1000 + 250 * 2 ** attempt + Math.floor(random * 250))
}

export async function loadFeed(runtime: Runtime = {}): Promise<Feed> {
  const fetchImpl = runtime.fetchImpl ?? fetch
  const sleep = runtime.sleep ?? ((ms) => Bun.sleep(ms))
  for (let attempt = 0; attempt <= 2; attempt++) {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), runtime.timeoutMs ?? 15_000)
    let retryMs: number | null = null
    try {
      const response = await fetchImpl(API_URL, {
        headers: { "User-Agent": USER_AGENT, Accept: "application/json" },
        redirect: "error", signal: controller.signal,
      })
      if (response.status === 403) throw new CLIError("Remote OK refused access (403); no bypass or retry attempted", "HTTP_403")
      if (response.status === 429 || response.status >= 500 && response.status <= 599) {
        if (attempt === 2) throw new CLIError(`Remote OK returned HTTP ${response.status} after three attempts`, response.status === 429 ? "RATE_LIMITED" : "HTTP_ERROR")
        retryMs = retryDelay(response.headers.get("retry-after"), attempt, (runtime.now ?? Date.now)(), (runtime.random ?? Math.random)())
        await response.body?.cancel()
      } else {
        if (!response.ok) throw new CLIError(`Remote OK returned HTTP ${response.status}`, "HTTP_ERROR")
        let data: unknown
        try { data = JSON.parse(await response.text()) }
        catch (error) {
          if (controller.signal.aborted) throw error
          throw new CLIError("Remote OK returned invalid JSON", "BAD_RESPONSE")
        }
        return parseFeed(data)
      }
    } catch (error) {
      if (error instanceof CLIError) throw error
      if (controller.signal.aborted) throw new CLIError("Remote OK request timed out", "REQUEST_TIMEOUT")
      throw new CLIError(error instanceof Error ? error.message : String(error), "NETWORK_ERROR")
    } finally { clearTimeout(timer) }
    if (retryMs !== null) await sleep(retryMs)
  }
  throw new CLIError("Unable to retrieve Remote OK feed", "NETWORK_ERROR")
}

export function renderTable(jobs: Job[]): string {
  if (!jobs.length) return "No results in the current feed."
  return ["ID\tTITLE\tCOMPANY\tLOCATION\tDATE\tURL", ...jobs.map(j => [j.id, j.title, j.company ?? "—", j.location ?? "—", j.date ?? "—", j.url].map(v => v.replace(/\s+/g, " ")).join("\t"))].join("\n")
}

export function renderPlain(jobs: Job[], description = false): string {
  if (!jobs.length) return "No results in the current feed."
  return jobs.map(j => `${j.title}\n${j.company ?? "—"} · ${j.location ?? "—"} · ${j.date ?? "—"}\nID: ${j.id}\n${j.url}${description ? `\n\n${j.description ?? "Description not supplied."}` : ""}`).join("\n\n")
}

export function output(text: string, runtime: Runtime): void { (runtime.out ?? ((s) => process.stdout.write(s)))(text + "\n") }
export function writeError(error: unknown, runtime: Runtime): void {
  const message = error instanceof Error ? error.message : String(error)
  const code = error instanceof CLIError ? error.code : "INTERNAL_ERROR"
  ;(runtime.err ?? ((s) => process.stderr.write(s)))(JSON.stringify({ error: message, code }) + "\n")
}
