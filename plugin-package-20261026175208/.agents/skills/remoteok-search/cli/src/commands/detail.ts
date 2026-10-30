import { detailID, loadFeed, output, renderPlain, renderTable, type Runtime } from "../helpers.js"

export interface DetailOpts { input: string; format: "json" | "table" | "plain" }

export async function runDetail(opts: DetailOpts, runtime: Runtime = {}): Promise<void> {
  const id = detailID(opts.input)
  const feed = await loadFeed(runtime)
  const job = feed.jobs.find(job => job.id === id)
  if (opts.format === "json") {
    output(JSON.stringify(job ? { ...job, attribution: feed.attribution } : null, null, 2), runtime)
  } else {
    output((opts.format === "table" ? renderTable(job ? [job] : []) : renderPlain(job ? [job] : [], true)) + "\n\nSource: Remote OK — https://remoteok.com\nKeep the original posting link when sharing.", runtime)
  }
}
