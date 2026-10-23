// Only the published RSS endpoint is requested; supplied detail URLs are never fetched.
export const FEED_URL = "https://weworkremotely.com/remote-jobs.rss"
export const USER_AGENT = "mdshahansha/automated-switch-apply/1.0 (weworkremotely-search-cli)"
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
  region: string | null
  country: string | null
  state: string | null
  skills: string | null
  category: string | null
  employmentType: string | null
  expiresAt: string | null
  source: "We Work Remotely"
}

export type Format = "json" | "table" | "plain"

/** Accept only a slug or an exact public posting URL on the feed's host. */
export function postingSlug(input: string): string {
  const slugPattern = /^[a-z0-9]+(?:-[a-z0-9]+)*$/
  if (slugPattern.test(input)) return input
  let url: URL
  try { url = new URL(input) } catch { throw new CLIError("detail requires a WWR posting slug or HTTPS posting URL", "BAD_ARG") }
  const match = /^\/remote-jobs\/([a-z0-9]+(?:-[a-z0-9]+)*)$/.exec(url.pathname)
  if (url.protocol !== "https:" || url.hostname !== "weworkremotely.com" || url.port ||
      url.username || url.password || url.search || url.hash || !match ||
      input.includes("\\") || /%|\/\.\.?\//.test(input)) {
    throw new CLIError("detail URL must be https://weworkremotely.com/remote-jobs/<slug> without credentials, query or fragment", "BAD_ARG")
  }
  return match[1]
}

const entities: Record<string, string> = {
  amp: "&", lt: "<", gt: ">", quot: '"', apos: "'", nbsp: " ",
  ndash: "–", mdash: "—", lsquo: "‘", rsquo: "’", ldquo: "“", rdquo: "”",
  hellip: "…", bull: "•", middot: "·", copy: "©", reg: "®", trade: "™",
}

export function decodeEntities(value: string): string {
  return value.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (whole, entity: string) => {
    if (entity.startsWith("#")) {
      const cp = /^#x/i.test(entity) ? parseInt(entity.slice(2), 16) : Number(entity.slice(1))
      return Number.isInteger(cp) && cp > 0 && cp <= 0x10ffff && !(cp >= 0xd800 && cp <= 0xdfff)
        ? String.fromCodePoint(cp) : ""
    }
    return entities[entity.toLowerCase()] ?? whole
  })
}

function xmlValue(item: string, tag: string): string | null {
  const match = new RegExp(`<${tag}(?:\\s[^>]*)?>([\\s\\S]*?)</${tag}\\s*>`, "i").exec(item)
  if (!match) return null
  const raw = match[1].trim()
  // CDATA is literal XML content: do not entity-decode it at this layer.
  const value = /^<!\[CDATA\[([\s\S]*)\]\]>$/.exec(raw)
  return (value ? value[1] : decodeEntities(raw)).trim() || null
}

/** Convert decoded RSS HTML to text, preserving paragraphs and list boundaries. */
export function descriptionText(html: string): string | null {
  const value = decodeEntities(html
    .replace(/<(script|style)\b[^>]*>[\s\S]*?<\/\1>/gi, "")
    .replace(/<\s*br\b[^>]*>/gi, "\n")
    .replace(/<\/?(?:p|div|h[1-6]|ul|ol|section|blockquote)\b[^>]*>/gi, "\n\n")
    .replace(/<li\b[^>]*>/gi, "\n• ")
    .replace(/<\/li\s*>/gi, "\n")
    .replace(/<[^>]*>/g, ""))
    .replace(/\r/g, "")
    .replace(/[\t \u00a0]+/g, " ")
    .replace(/ *\n */g, "\n")
    .replace(/\n{3,}/g, "\n\n")
    .trim()
  return value || null
}

function isoDate(raw: string | null): string | null {
  if (!raw) return null
  const ms = Date.parse(raw)
  return Number.isFinite(ms) ? new Date(ms).toISOString() : null
}

/** Each item is independent: an incomplete/bad item cannot consume the next one. */
export function parseFeed(xml: string): Job[] {
  if (!/<rss\b/i.test(xml) || !/<channel\b/i.test(xml) || !/<\/rss\s*>/i.test(xml)) {
    throw new CLIError("Expected the public WWR RSS feed, received another response", "BAD_RESPONSE")
  }
  const results: Job[] = []
  const seen = new Set<string>()
  for (const chunk of xml.split(/<item(?:\s[^>]*)?>/i).slice(1)) {
    const end = chunk.indexOf("</item>")
    if (end < 0) continue
    const item = chunk.slice(0, end)
    const rawTitle = xmlValue(item, "title")
    if (!rawTitle) continue
    let id: string | undefined
    for (const candidate of [xmlValue(item, "link"), xmlValue(item, "guid")]) {
      if (!candidate || !candidate.startsWith("https://")) continue
      try { id = postingSlug(candidate); break } catch { /* malformed feed item */ }
    }
    if (!id || seen.has(id)) continue
    const split = rawTitle.indexOf(": ")
    const company = split > 0 ? rawTitle.slice(0, split).trim() || null : null
    const title = (split > 0 ? rawTitle.slice(split + 2) : rawTitle).trim()
    if (!title) continue
    const region = xmlValue(item, "region")
    const country = xmlValue(item, "country")
    const rawDescription = xmlValue(item, "description")
    results.push({
      id, title, company, location: region ?? country, date: isoDate(xmlValue(item, "pubDate")),
      url: `https://weworkremotely.com/remote-jobs/${id}`,
      description: rawDescription ? descriptionText(rawDescription) : null,
      region, country, state: xmlValue(item, "state"), skills: xmlValue(item, "skills"),
      category: xmlValue(item, "category"), employmentType: xmlValue(item, "type"),
      expiresAt: isoDate(xmlValue(item, "expires_at")), source: "We Work Remotely",
    })
    seen.add(id)
  }
  return results
}

export interface FetchDeps {
  fetch?: typeof fetch
  sleep?: (ms: number) => Promise<void>
  random?: () => number
  now?: () => number
}

/** One feed load per command; only transient failures retry that same fixed URL. */
export async function fetchFeed(deps: FetchDeps = {}): Promise<string> {
  const request = deps.fetch ?? fetch
  const sleep = deps.sleep ?? ((ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms)))
  for (let attempt = 0; attempt <= 6; attempt++) {
    let response: Response
    try {
      response = await request(FEED_URL, {
        headers: { "User-Agent": USER_AGENT, Accept: "application/rss+xml,application/xml;q=0.9,text/xml;q=0.8" },
        redirect: "error", signal: AbortSignal.timeout(15000),
      })
    } catch (error) {
      throw new CLIError(`Unable to load WWR RSS: ${error instanceof Error ? error.message : String(error)}`, "FETCH_FAILED")
    }
    if (response.status === 429 || response.status >= 500) {
      if (attempt === 6) throw new CLIError(`WWR RSS returned HTTP ${response.status} after retries`, "HTTP_ERROR")
      const retryAfter = response.headers.get("Retry-After")?.trim()
      let requestedDelay = 0
      if (retryAfter) {
        const milliseconds = /^\d+(?:\.\d+)?$/.test(retryAfter)
          ? Number(retryAfter) * 1000
          : Date.parse(retryAfter) - (deps.now ?? Date.now)()
        if (Number.isFinite(milliseconds)) requestedDelay = Math.max(0, milliseconds)
      }
      await response.body?.cancel()
      if (requestedDelay > 30000) {
        throw new CLIError("WWR requested a retry after more than 30 seconds; retry the command later", "RETRY_LATER")
      }
      await sleep(Math.max(requestedDelay,
        Math.min(500 * 2 ** attempt, 8000) + Math.floor((deps.random ?? Math.random)() * 300)))
      continue
    }
    if (!response.ok) throw new CLIError(`WWR RSS returned HTTP ${response.status}; no access bypass attempted`, "HTTP_ERROR")
    return response.text()
  }
  throw new CLIError("WWR RSS retries exhausted", "HTTP_ERROR")
}

export async function loadJobs(): Promise<Job[]> { return parseFeed(await fetchFeed()) }

export function formatJobs(jobs: Job[], format: Exclude<Format, "json">, detail = false): string {
  if (!jobs.length) return detail ? "Not found in the current We Work Remotely RSS feed." : "No matching jobs in the current We Work Remotely RSS feed."
  if (format === "table") {
    const columns = ["Title", "Company", "Location", "Posted", "We Work Remotely link"]
    const rows = jobs.map((j) => [j.title, j.company ?? "—", j.location ?? "—", j.date ?? "—", j.url])
    return [columns, ...rows].map((row) => row.map((v) => v.replace(/[\t\r\n]+/g, " ")).join("\t")).join("\n")
  }
  return jobs.map((j) => [j.title, `Company: ${j.company ?? "Unknown"}`, `Location: ${j.location ?? "Unknown"}`,
    `Posted: ${j.date ?? "Unknown"}`, `Source: We Work Remotely — ${j.url}`,
    ...(detail ? [`Countries listed: ${j.country ?? "Not supplied"}`, `Type: ${j.employmentType ?? "Unknown"}`,
      `Expires: ${j.expiresAt ?? "Unknown"}`, "", j.description ?? "No description supplied in the feed."] : []),
  ].join("\n")).join("\n\n")
}
