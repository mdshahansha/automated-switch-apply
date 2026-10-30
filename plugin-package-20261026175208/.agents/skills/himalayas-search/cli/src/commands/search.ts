import { SEARCH_URL, PortalError, parseSearch, renderJobs, requestJSON, type Format, type RequestOptions } from "../helpers.js"

export interface SearchOpts {
  query?: string
  country?: string
  worldwide?: boolean
  excludeWorldwide?: boolean
  timezone?: string
  seniority?: string
  employmentType?: string
  company?: string
  sort?: string
  page: number
  limit?: number
  jobage?: number
  format: Format
}

export function buildSearchURL(options: SearchOpts): string {
  const params = new URLSearchParams({ page: String(options.page) })
  for (const [key, value] of Object.entries({ q: options.query, country: options.country, timezone: options.timezone, seniority: options.seniority, employment_type: options.employmentType, company: options.company, sort: options.sort })) {
    if (value !== undefined) params.set(key, value)
  }
  if (options.worldwide !== undefined) params.set("worldwide", String(options.worldwide))
  if (options.excludeWorldwide !== undefined) params.set("exclude_worldwide", String(options.excludeWorldwide))
  return `${SEARCH_URL}?${params}`
}

export async function searchJobs(options: SearchOpts, requestOptions: RequestOptions = {}) {
  // One selected API page per command. A short or post-filtered page does not
  // imply exhaustion; totalCount is approximate and may be a day old.
  const url = buildSearchURL(options)
  const response = await requestJSON(url, requestOptions)
  if (response.status !== 200) throw new PortalError(`Search endpoint returned HTTP ${response.status}`, `HTTP_${response.status}`)
  const parsed = parseSearch(response.data)
  const now = (requestOptions.now ?? Date.now)()
  const seen = new Set<string>()
  const unique = parsed.jobs.filter(job => {
    if (!job.id || seen.has(job.id)) return false
    seen.add(job.id)
    return true
  })
  const cutoff = options.jobage === undefined ? null : now - options.jobage * 86_400_000
  const filtered = unique.filter(job => {
    if (job.expiryDate !== null && job.expiryDate * 1000 <= now) return false
    return cutoff === null || (job.pubDate !== null && job.pubDate * 1000 >= cutoff && job.pubDate * 1000 <= now)
  })
  const results = options.limit === undefined ? filtered : filtered.slice(0, options.limit)
  return {
    meta: {
      count: results.length, page: options.page, source: "Himalayas", sourceUrl: url,
      pageSize: 20, fetchedCount: parsed.fetchedCount, totalCount: parsed.totalCount,
      updatedAt: parsed.updatedAt, skippedMalformed: parsed.skipped,
      pagination: "Request subsequent --page values until the API returns no jobs; a short or filtered page is not exhaustion. Deduplicate IDs across pages.",
      appliedFilters: { query: options.query ?? null, country: options.country ?? null, worldwide: options.worldwide ?? false, excludeWorldwide: options.excludeWorldwide ?? false, timezone: options.timezone ?? null, seniority: options.seniority ?? null, employmentType: options.employmentType ?? null, company: options.company ?? null, sort: options.sort ?? null, jobage: options.jobage ?? null, limit: options.limit ?? null },
      dateMeaning: "date/pubDate is last updated, not necessarily original posting time; --jobage filters this field locally and excludes unknown dates",
      eligibility: "Country/timezone fields are API metadata; check the full description for restrictions before treating a job as eligible.",
    }, results,
  }
}

export async function runSearch(options: SearchOpts): Promise<number> {
  const output = await searchJobs(options)
  process.stdout.write((options.format === "json" ? JSON.stringify(output, null, 2) : renderJobs(output.results, options.format)) + "\n")
  return 0
}
