export const ORIGIN = "https://himalayas.app"
export const SEARCH_URL = `${ORIGIN}/jobs/api/search`
export const USER_AGENT = "mdshahansha/automated-switch-apply/1.0 (himalayas-search-cli)"

export class PortalError extends Error {
  constructor(message: string, public code: string) { super(message) }
}

export type Format = "json" | "table" | "plain"
export interface Job {
  id: string | null
  title: string | null
  company: string | null
  location: string | null
  date: string | null
  url: string | null
  applicationLink: string | null
  description: string | null
  excerpt: string | null
  employmentType: string | null
  companySlug: string | null
  companyLogo: string | null
  locationRestrictions: string[] | null
  timezoneRestrictions: number[] | null
  seniority: string[] | null
  categories: string[] | null
  parentCategories: string[] | null
  minSalary: number | null
  maxSalary: number | null
  salaryPeriod: string | null
  currency: string | null
  pubDate: number | null
  expiryDate: number | null
  expiresAt: string | null
}

const record = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object" && !Array.isArray(value)
const str = (value: unknown): string | null =>
  typeof value === "string" && value.trim() ? value.trim() : null
const num = (value: unknown): number | null =>
  typeof value === "number" && Number.isFinite(value) ? value : null
const strings = (value: unknown): string[] | null =>
  Array.isArray(value) && value.every(x => typeof x === "string") ? value : null
const numbers = (value: unknown): number[] | null =>
  Array.isArray(value) && value.every(x => typeof x === "number" && Number.isFinite(x)) ? value : null

export function unixDate(value: unknown): string | null {
  const seconds = num(value)
  if (seconds === null || seconds < 0) return null
  const date = new Date(seconds * 1000)
  return Number.isNaN(date.getTime()) ? null : date.toISOString()
}

export function decodeEntities(text: string): string {
  const named: Record<string, string> = {
    amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
    ndash: "–", mdash: "—", rsquo: "’", lsquo: "‘", ldquo: "“", rdquo: "”", bull: "•",
  }
  return text.replace(/&(#x[\da-f]+|#\d+|[a-z]+);/gi, (full, entity: string) => {
    if (!entity.startsWith("#")) return named[entity.toLowerCase()] ?? full
    const code = entity[1]?.toLowerCase() === "x" ? parseInt(entity.slice(2), 16) : Number(entity.slice(1))
    return Number.isInteger(code) && code > 0 && code <= 0x10ffff && !(code >= 0xd800 && code <= 0xdfff)
      ? String.fromCodePoint(code) : full
  })
}

export function htmlToText(html: string): string {
  return decodeEntities(html
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<br\s*\/?\s*>/gi, "\n")
    .replace(/<li\b[^>]*>/gi, "\n• ")
    .replace(/<\/(p|div|h[1-6]|ul|ol|section|article)>/gi, "\n\n")
    .replace(/<[^>]*>/g, ""))
    .replace(/\r/g, "").replace(/[\t ]+\n/g, "\n").replace(/\n[\t ]+/g, "\n")
    .replace(/\n{3,}/g, "\n\n").trim()
}

// IDs use company/job-slug, returned directly in each normalized search result.
// Validate the raw path too: URL() normalizes dot segments before pathname checks.
export function detailURL(input: string): { id: string; url: string; canonical: string } {
  const raw = input.trim()
  const bad = () => { throw new PortalError("Use a company/job-slug ID or an HTTPS Himalayas job URL", "BAD_ID") }
  if (!raw || /[\\\u0000-\u0020\u007f]/.test(raw)) return bad()
  let path = raw
  let isURL = false
  if (/^[a-z][a-z0-9+.-]*:/i.test(raw)) {
    let parsed: URL
    try { parsed = new URL(raw) } catch { return bad() }
    if (parsed.protocol !== "https:" || parsed.hostname !== "himalayas.app" || parsed.port || parsed.username || parsed.password || parsed.hash) return bad()
    const rawPath = raw.slice(raw.indexOf("://") + 3).replace(/^[^/]+/, "").split("?")[0]
    if (!rawPath || /%|(?:^|\/)\.{1,2}(?:\/|$)/.test(rawPath)) return bad()
    path = parsed.pathname
    isURL = true
    // The public Apply URL adds this optional source marker. Other queries are
    // unnecessary for a single-job identity and are rejected, never forwarded.
    for (const [key, value] of parsed.searchParams) {
      if (key !== "utm_source" || value !== "api") return bad()
    }
  }
  const match = path.match(isURL
    ? /^\/(?:jobs\/api\/)?companies\/([a-z0-9][a-z0-9-]*)\/jobs\/([a-z0-9][a-z0-9-]*)\/?$/i
    : /^([a-z0-9][a-z0-9-]*)\/([a-z0-9][a-z0-9-]*)$/i)
  if (!match) return bad()
  const id = `${match[1]}/${match[2]}`
  const canonical = `${ORIGIN}/companies/${match[1]}/jobs/${match[2]}`
  return { id, canonical, url: `${ORIGIN}/jobs/api/companies/${match[1]}/jobs/${match[2]}` }
}

export function parseJob(value: unknown): Job | null {
  if (!record(value)) return null
  let identity: ReturnType<typeof detailURL> | null = null
  if (typeof value.guid === "string") {
    try { identity = detailURL(value.guid) } catch { return null }
  }
  const places = strings(value.locationRestrictions)
  const desc = str(value.description)
  return {
    id: identity?.id ?? null, title: str(value.title) ? decodeEntities(str(value.title)!) : null,
    company: str(value.companyName) ? decodeEntities(str(value.companyName)!) : null,
    // An empty restrictions array means worldwide in the API; missing is unknown.
    location: places ? (places.length ? places.join(", ") : "Worldwide (API location field)") : null,
    date: unixDate(value.pubDate), url: identity?.canonical ?? null,
    applicationLink: str(value.applicationLink), description: desc ? htmlToText(desc) : null,
    excerpt: str(value.excerpt) ? htmlToText(str(value.excerpt)!) : null,
    employmentType: str(value.employmentType), companySlug: str(value.companySlug), companyLogo: str(value.companyLogo),
    locationRestrictions: places, timezoneRestrictions: numbers(value.timezoneRestrictions),
    seniority: strings(value.seniority), categories: strings(value.categories), parentCategories: strings(value.parentCategories),
    minSalary: num(value.minSalary), maxSalary: num(value.maxSalary), salaryPeriod: str(value.salaryPeriod), currency: str(value.currency),
    pubDate: num(value.pubDate), expiryDate: num(value.expiryDate), expiresAt: unixDate(value.expiryDate),
  }
}

export function parseSearch(value: unknown): { jobs: Job[]; fetchedCount: number; totalCount: number | null; updatedAt: string | null; skipped: number } {
  if (!record(value) || !Array.isArray(value.jobs)) throw new PortalError("API response is missing its jobs array", "INVALID_RESPONSE")
  const jobs: Job[] = []
  let skipped = 0
  for (const item of value.jobs) {
    const job = parseJob(item)
    if (!job?.id || !job.url || !job.title) { skipped++; continue }
    jobs.push(job)
  }
  return { jobs, fetchedCount: value.jobs.length, totalCount: num(value.totalCount), updatedAt: unixDate(value.updatedAt), skipped }
}

export type FetchLike = (url: string, init?: RequestInit) => Promise<Response>
export interface RequestOptions {
  fetcher?: FetchLike
  sleep?: (ms: number) => Promise<void>
  random?: () => number
  now?: () => number
  timeoutMs?: number
  retries?: number
}

export function retryDelay(header: string | null, attempt: number, now: number, random: number): number {
  const seconds = header && /^\d+(?:\.\d+)?$/.test(header.trim()) ? Number(header) * 1000 : NaN
  const date = header ? Date.parse(header) : NaN
  if (seconds > 30_000) throw new PortalError("Server requests a retry wait longer than 30 seconds; retry later", "RETRY_LATER")
  const retryAfter = Number.isFinite(seconds) ? seconds : Number.isFinite(date) ? date - now : 0
  if (retryAfter > 30_000) throw new PortalError("Server requests a retry wait longer than 30 seconds; retry later", "RETRY_LATER")
  return Math.max(0, retryAfter, Math.min(30_000, 500 * 2 ** attempt + random * 250))
}

export async function requestJSON(url: string, options: RequestOptions = {}): Promise<{ status: number; data: unknown }> {
  const target = new URL(url)
  if (target.origin !== ORIGIN || target.username || target.password || target.hash ||
      !/^\/jobs\/api(?:\/search|\/companies\/[a-z0-9][a-z0-9-]*\/jobs\/[a-z0-9][a-z0-9-]*)?$/.test(target.pathname)) {
    throw new PortalError("Only the official Himalayas jobs API is supported", "BAD_URL")
  }
  const fetcher = options.fetcher ?? fetch
  const sleep = options.sleep ?? (ms => new Promise(resolve => setTimeout(resolve, ms)))
  const retries = options.retries ?? 3
  for (let attempt = 0; ; attempt++) {
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), options.timeoutMs ?? 20_000)
    let response: Response
    let body: string
    try {
      response = await fetcher(url, { headers: { "User-Agent": USER_AGENT, Accept: "application/json" }, redirect: "error", signal: controller.signal })
      body = await response.text()
    } catch (error) {
      throw new PortalError(controller.signal.aborted ? "Himalayas request timed out" : `Himalayas request failed: ${error instanceof Error ? error.message : String(error)}`, controller.signal.aborted ? "TIMEOUT" : "NETWORK_ERROR")
    } finally { clearTimeout(timeout) }
    if ((response.status === 429 || response.status >= 500) && attempt < retries) {
      await sleep(retryDelay(response.headers.get("retry-after"), attempt, (options.now ?? Date.now)(), (options.random ?? Math.random)()))
      continue
    }
    if (response.status === 404) return { status: 404, data: null }
    if (response.status === 410) {
      let data: unknown = null
      try { data = JSON.parse(body) } catch { /* Closed status remains authoritative. */ }
      return { status: 410, data }
    }
    if (!response.ok) throw new PortalError(`Himalayas returned HTTP ${response.status}`, `HTTP_${response.status}`)
    let data: unknown
    try { data = JSON.parse(body) } catch { throw new PortalError("Himalayas returned invalid JSON", "INVALID_RESPONSE") }
    return { status: response.status, data }
  }
}

export function writeError(error: unknown): void {
  process.stderr.write(JSON.stringify({ error: error instanceof Error ? error.message : String(error), code: error instanceof PortalError ? error.code : "INTERNAL_ERROR" }) + "\n")
}

export function renderJobs(jobs: Job[], format: Format): string {
  if (format === "plain") return jobs.length ? jobs.map(j => `${j.title ?? "—"}\n${j.company ?? "—"} | ${j.location ?? "Unknown location"}\nUpdated: ${j.date ?? "Unknown"}\nID: ${j.id ?? "—"}\n${j.url ?? "—"}\nApply: ${j.applicationLink ?? "—"}\n\n${j.description ?? j.excerpt ?? "No description supplied"}`).join("\n\n") : "No results."
  const cell = (value: string | null, width: number) => (value ?? "—").replace(/[\r\n\t]/g, " ").slice(0, width).padEnd(width)
  return ["TITLE".padEnd(40) + " COMPANY".padEnd(29) + " LOCATION".padEnd(30) + " ID", ...jobs.map(j => `${cell(j.title, 40)} ${cell(j.company, 28)} ${cell(j.location, 29)} ${j.id ?? "—"}`)].join("\n")
}
