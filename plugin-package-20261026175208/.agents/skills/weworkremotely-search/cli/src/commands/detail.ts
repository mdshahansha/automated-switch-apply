import { postingSlug, type Job } from "../helpers.js"

/** Feed membership only; absence does not mean a posting is closed. */
export function detailJob(jobs: Job[], input: string): Job | null {
  const id = postingSlug(input)
  return jobs.find((job) => job.id === id) ?? null
}
