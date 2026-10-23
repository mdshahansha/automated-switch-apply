import { detailURL, parseJob, PortalError, renderJobs, requestJSON, unixDate, type Format, type RequestOptions } from "../helpers.js"

export async function getDetail(id: string, requestOptions: RequestOptions = {}) {
  const target = detailURL(id)
  const response = await requestJSON(target.url, requestOptions)
  if (response.status === 404 || response.status === 410) {
    const data = response.data !== null && typeof response.data === "object" ? response.data as Record<string, unknown> : null
    return { meta: { source: "Himalayas", status: response.status === 410 ? "closed" : "not_found", url: target.canonical, expiryDate: unixDate(data?.expiryDate) }, result: null }
  }
  const data = response.data !== null && typeof response.data === "object" ? response.data as Record<string, unknown> : null
  const job = parseJob(data?.job)
  if (!job?.id || !job.title || job.id !== target.id) throw new PortalError("Detail response is missing the requested job", "INVALID_RESPONSE")
  if (job.expiryDate !== null && job.expiryDate * 1000 <= (requestOptions.now ?? Date.now)()) {
    return { meta: { source: "Himalayas", status: "closed", url: target.canonical, expiryDate: job.expiresAt }, result: null }
  }
  return { meta: { source: "Himalayas", status: "open", url: target.canonical, expiryDate: job.expiresAt }, result: job }
}

export async function runDetail(id: string, format: Format): Promise<number> {
  const output = await getDetail(id)
  process.stdout.write((format === "json" ? JSON.stringify(output, null, 2) : output.result ? renderJobs([output.result], format) : `Job ${output.meta.status}: ${output.meta.url}`) + "\n")
  return 0
}
