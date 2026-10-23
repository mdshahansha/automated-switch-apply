import { loadFeed, output, PAGE_SIZE, renderPlain, renderTable, type Job, type Runtime } from "../helpers.js"

export interface SearchOpts {
  query?: string
  location?: string
  jobage?: number
  page: number
  limit: number
  format: "json" | "table" | "plain"
}

export function filterJobs(jobs: Job[], opts: SearchOpts, now = Date.now()): Job[] {
  const terms = (opts.query ?? "").toLocaleLowerCase().split(/\s+/).filter(Boolean)
  const location = opts.location?.toLocaleLowerCase()
  return jobs.filter(job => {
    const keywords = [job.title, job.company ?? "", ...job.tags].join(" ").toLocaleLowerCase()
    if (!terms.every(term => keywords.includes(term))) return false
    if (location && !(job.location ?? "").toLocaleLowerCase().includes(location)) return false
    if (opts.jobage !== undefined) {
      if (!job.date) return false
      const age = now - Date.parse(job.date)
      if (age < 0 || age > opts.jobage * 86_400_000) return false
    }
    return true
  })
}

export async function runSearch(opts: SearchOpts, runtime: Runtime = {}): Promise<void> {
  const feed = await loadFeed(runtime)
  const filtered = filterJobs(feed.jobs, opts, (runtime.now ?? Date.now)())
  const start = (opts.page - 1) * PAGE_SIZE
  const results = filtered.slice(start, start + PAGE_SIZE).slice(0, opts.limit)
  if (opts.format === "json") {
    output(JSON.stringify({ meta: {
      count: results.length, page: opts.page, pageSize: PAGE_SIZE, total: filtered.length,
      source: "Remote OK", sourceUrl: "https://remoteok.com/api", attribution: feed.attribution,
      filters: { query: opts.query ?? null, location: opts.location ?? null, jobage: opts.jobage ?? null, mode: "client-side" },
    }, results }, null, 2), runtime)
  } else {
    output((opts.format === "table" ? renderTable(results) : renderPlain(results)) + "\n\nSource: Remote OK — https://remoteok.com\nKeep the original posting links when sharing.", runtime)
  }
}
