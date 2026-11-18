import { PAGE_SIZE, type Job } from "../helpers.js"

export interface SearchOpts {
  query?: string
  location?: string
  jobage?: number
  page: number
  limit?: number
  includeDescription?: boolean
}

export function searchJobs(jobs: Job[], opts: SearchOpts, now = Date.now()) {
  const query = opts.query?.toLocaleLowerCase()
  const location = opts.location?.toLocaleLowerCase()
  const filtered = jobs.filter((job) => {
    // All filters are local to the published feed, not server-side portal search.
    if (query && ![job.title, job.company, job.skills, job.category, job.description].join(" ").toLocaleLowerCase().includes(query)) return false
    // Match disclosed geography only; a global remote label does not imply India eligibility.
    if (location && ![job.region, job.country].join(" ").toLocaleLowerCase().includes(location)) return false
    if (opts.jobage !== undefined) {
      if (!job.date) return false
      const age = now - Date.parse(job.date)
      if (age < 0 || age > opts.jobage * 86400000) return false
    }
    return true
  })
  const start = (opts.page - 1) * PAGE_SIZE
  const results = filtered.slice(start, start + Math.min(opts.limit ?? PAGE_SIZE, PAGE_SIZE))
  return { meta: { count: results.length, page: opts.page, pageSize: PAGE_SIZE, total: filtered.length,
    source: "We Work Remotely", sourceUrl: "https://weworkremotely.com/remote-jobs.rss", filters: "client-side" },
    results: results.map(({ description, ...job }) => opts.includeDescription ? { ...job, description } : job) }
}
