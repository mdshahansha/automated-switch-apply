import { describe, expect, test } from "bun:test"
import fixture from "./fixtures/feed.json"
import { main } from "../src/cli.js"
import { filterJobs } from "../src/commands/search.js"
import { API_URL, CLIError, detailID, htmlToText, loadFeed, normalizePostingURL, parseFeed, USER_AGENT, type Runtime } from "../src/helpers.js"
import { runCLI } from "./helpers.js"

const now = Date.parse("2026-10-23T12:00:00Z")

function capture(data: unknown = fixture) {
  const requests: Array<{ url: string; init?: RequestInit }> = []
  let stdout = "", stderr = ""
  const runtime: Runtime = {
    now: () => now,
    fetchImpl: async (url, init) => { requests.push({ url, init }); return Response.json(data) },
    out: text => { stdout += text }, err: text => { stderr += text },
  }
  return { runtime, requests, stdout: () => stdout, stderr: () => stderr }
}

describe("feed normalization", () => {
  test("skips legal metadata and malformed postings, preserving attribution", () => {
    const feed = parseFeed(fixture)
    expect(feed.jobs.map(j => j.id)).toEqual(["1001", "1002", "1003", "1004"])
    expect(feed.attribution.name).toBe("Remote OK")
    expect(feed.attribution.notice).toContain("Synthetic legal notice")
    expect(feed.jobs[0].date).toBe("2026-10-22T12:00:00.000Z")
    expect(feed.jobs[3]).toMatchObject({ company: null, location: null, date: null, description: null, tags: [] })
    for (const job of feed.jobs) for (const key of ["id", "title", "company", "location", "date", "url"]) expect(Object.hasOwn(job, key)).toBe(true)
  })

  test("metadata never becomes a posting even if it has vacancy-shaped fields", () => {
    expect(parseFeed([{ ...fixture[1], legal: "Terms", last_updated: 1 }]).jobs).toEqual([])
  })

  test("accepts numeric IDs and epoch fallback; deduplicates IDs", () => {
    const row = { id: 42, position: "Engineer", epoch: 1_000_000, url: "/remote-jobs/remote-engineer-company-42" }
    const jobs = parseFeed([row, row]).jobs
    expect(jobs).toHaveLength(1)
    expect(jobs[0].id).toBe("42")
    expect(jobs[0].date).toBe(new Date(1_000_000_000).toISOString())
  })

  test("rejects an API envelope instead of quietly returning no matches", () => {
    expect(() => parseFeed({ jobs: fixture })).toThrow(CLIError)
  })

  test("retains disclosed salary bounds without inventing currency or period", () => {
    const base = { id: 42, position: "Engineer", url: "/remote-jobs/remote-engineer-company-42" }
    expect(parseFeed([{ ...base, salary_min: 90000, salary_max: 120000 }]).jobs[0])
      .toMatchObject({ salary_min: 90000, salary_max: 120000, salary_currency: null })
    expect(parseFeed([{ ...base, salary_min: 0, salary_max: "120000", currency: "EUR" }]).jobs[0])
      .toMatchObject({ salary_min: null, salary_max: null, salary_currency: "EUR" })
    expect(parseFeed([{ ...base, salary_min: -1, salary_max: Infinity }]).jobs[0])
      .toMatchObject({ salary_min: null, salary_max: null })
  })

  test("retains paragraphs, lists and decoded entities, removes executable markup", () => {
    expect(htmlToText('<p>A &amp; B</p><p>Next &#x2014; &#8217;</p><ul><li>One</li><li>Two</li></ul><script>bad()</script>'))
      .toBe("A & B\n\nNext — ’\n\n- One\n- Two")
    expect(htmlToText("a<br>b &nbsp; c &unknown; &#99999999;")).toBe("a\nb c &unknown; &#99999999;")
  })
})

describe("posting URL boundary", () => {
  test("normalizes only same-host posting URLs", () => {
    expect(normalizePostingURL("https://www.remoteok.com/remote-jobs/remote-react-role-1001/?ref=share#details"))
      .toBe("https://remoteok.com/remote-jobs/remote-react-role-1001")
    expect(normalizePostingURL("/remote-jobs/remote-engineer-42")).toBe("https://remoteok.com/remote-jobs/remote-engineer-42")
    expect(detailID("1001")).toBe("1001")
    expect(detailID("https://remoteok.com/remote-jobs/remote-react-role-1001")).toBe("1001")
  })

  test.each([
    "https://evil.test/remote-jobs/remote-role-42", "https://remoteok.com.evil.test/remote-jobs/remote-role-42",
    "http://remoteok.com/remote-jobs/remote-role-42", "https://u:p@remoteok.com/remote-jobs/remote-role-42",
    "https://remoteok.com:1234/remote-jobs/remote-role-42", "https://remoteok.com/api",
    "https://remoteok.com/remote-jobs/remote-role-%34%32", "file:///remote-jobs/remote-role-42",
    "https://remoteok.com/remote-jobs/remote-role-42/extra", "https://remoteok.com\\@evil.test/remote-jobs/remote-role-42",
  ])("rejects unsafe or non-posting input: %s", input => {
    expect(normalizePostingURL(input)).toBeNull()
    expect(() => detailID(input)).toThrow(CLIError)
  })
})

describe("local search and detail", () => {
  test("keyword words match title/company/tags; location is a strict local text filter", () => {
    const jobs = parseFeed(fixture).jobs
    const base = { page: 1, limit: 20, format: "json" as const }
    expect(filterJobs(jobs, { ...base, query: "react example" }, now).map(j => j.id)).toEqual(["1001", "1003"])
    expect(filterJobs(jobs, { ...base, query: "react", location: "India" }, now).map(j => j.id)).toEqual(["1001"])
    // Worldwide is not silently included in an India text filter.
    expect(filterJobs(jobs, { ...base, location: "India" }, now).some(j => j.location === "Worldwide")).toBe(false)
  })

  test("age excludes unknown dates and future dates and includes the exact boundary", () => {
    const jobs = parseFeed(fixture).jobs
    expect(filterJobs(jobs, { page: 1, limit: 20, format: "json", jobage: 8 }, now).map(j => j.id)).toEqual(["1001", "1002", "1003"])
    expect(filterJobs(jobs, { page: 1, limit: 20, format: "json", jobage: 7 }, now).map(j => j.id)).toEqual(["1001", "1003"])
    expect(filterJobs(jobs, { page: 1, limit: 20, format: "json", jobage: 8 }, now - 20 * 86_400_000)).toEqual([])
  })

  test("fixed 20-result pages are applied after filtering, limit only caps that page", async () => {
    const rows = Array.from({ length: 25 }, (_, i) => ({ id: String(2001 + i), position: "Engineer", company: "Example", url: `https://remoteok.com/remote-jobs/remote-engineer-${2001 + i}` }))
    const c = capture([fixture[0], ...rows])
    expect(await main(["search", "-q", "Engineer", "--page", "2", "--limit", "2"], c.runtime)).toBe(0)
    const data = JSON.parse(c.stdout())
    expect(data.meta).toMatchObject({ count: 2, page: 2, pageSize: 20, total: 25 })
    expect(data.results.map((j: { id: string }) => j.id)).toEqual(["2021", "2022"])
    expect(c.requests).toHaveLength(1)
    expect(c.requests[0].url).toBe(API_URL)
  })

  test("search sends honest UA and all filters stay out of the request URL", async () => {
    const c = capture()
    expect(await main(["search", "--query=react", "-l", "India", "--jobage", "7", "-n", "1"], c.runtime)).toBe(0)
    expect(c.stderr()).toBe("")
    expect(c.requests[0].url).toBe("https://remoteok.com/api")
    expect(new Headers(c.requests[0].init?.headers).get("user-agent")).toBe(USER_AGENT)
    expect(c.requests[0].init?.redirect).toBe("error")
    const data = JSON.parse(c.stdout())
    expect(data.results.map((j: { id: string }) => j.id)).toEqual(["1001"])
    expect(data.meta.attribution.notice).toContain("Synthetic legal notice")
    expect(data.meta.filters.mode).toBe("client-side")
  })

  test("detail resolves ID from one feed request, never fetching even the supplied same-host URL", async () => {
    const c = capture()
    expect(await main(["detail", "https://remoteok.com/remote-jobs/remote-react-engineer-example-labs-1001", "--format", "plain"], c.runtime)).toBe(0)
    expect(c.requests.map(r => r.url)).toEqual([API_URL])
    expect(c.stdout()).toContain("Build React & TypeScript tools.\n\nSecond paragraph — collaborate.")
    expect(c.stdout()).toContain("Source: Remote OK")
  })

  test("a detail absent from the current feed is null, not an invented or arbitrary fetch", async () => {
    const c = capture()
    expect(await main(["detail", "999999"], c.runtime)).toBe(0)
    expect(JSON.parse(c.stdout())).toBeNull()
    expect(c.requests).toHaveLength(1)
  })

  test.each(["table", "plain"])("%s search retains attribution and original links", async format => {
    const c = capture()
    expect(await main(["search", "-q", "react", "--format", format], c.runtime)).toBe(0)
    expect(c.stdout()).toContain("Source: Remote OK")
    expect(c.stdout()).toContain("https://remoteok.com/remote-jobs/remote-react-engineer-example-labs-1001")
  })
})

describe("transport and errors", () => {
  test("429 obeys Retry-After, retries at most twice, succeeds without losing metadata", async () => {
    let calls = 0
    const delays: number[] = []
    const feed = await loadFeed({ fetchImpl: async () => ++calls === 1 ? new Response(null, { status: 429, headers: { "Retry-After": "2" } }) : Response.json(fixture), sleep: async ms => { delays.push(ms) }, random: () => 0 })
    expect(calls).toBe(2)
    expect(delays).toEqual([2000])
    expect(feed.jobs).toHaveLength(4)
  })

  test("Retry-After HTTP dates are respected", async () => {
    let calls = 0
    const delays: number[] = []
    await loadFeed({ now: () => now, random: () => 0, sleep: async ms => { delays.push(ms) }, fetchImpl: async () => ++calls === 1 ? new Response(null, { status: 503, headers: { "Retry-After": new Date(now + 5000).toUTCString() } }) : Response.json([]) })
    expect(delays).toEqual([5000])
  })

  test("long Retry-After stops without violating the requested wait", async () => {
    let calls = 0, sleeps = 0
    await expect(loadFeed({ fetchImpl: async () => { calls++; return new Response(null, { status: 429, headers: { "Retry-After": "120" } }) }, sleep: async () => { sleeps++ } })).rejects.toMatchObject({ code: "RETRY_LATER" })
    expect(calls).toBe(1)
    expect(sleeps).toBe(0)
  })

  test("403 never retries or switches identity; structured error stays on stderr", async () => {
    const c = capture()
    let calls = 0
    c.runtime.fetchImpl = async () => { calls++; return new Response(null, { status: 403 }) }
    expect(await main(["search"], c.runtime)).toBe(1)
    expect(c.stdout()).toBe("")
    expect(JSON.parse(c.stderr()).code).toBe("HTTP_403")
    expect(calls).toBe(1)
  })

  test("5xx retries are bounded; a missing fixed API endpoint is an error", async () => {
    let calls = 0
    await expect(loadFeed({ fetchImpl: async () => { calls++; return new Response(null, { status: 503 }) }, sleep: async () => {}, random: () => 0 })).rejects.toMatchObject({ code: "HTTP_ERROR" })
    expect(calls).toBe(3)
    let missingCalls = 0
    await expect(loadFeed({ fetchImpl: async () => { missingCalls++; return new Response(null, { status: 404 }) } })).rejects.toMatchObject({ code: "HTTP_ERROR" })
    expect(missingCalls).toBe(1)
  })

  test("invalid JSON is reported, not converted to empty search results", async () => {
    await expect(loadFeed({ fetchImpl: async () => new Response("<html>blocked</html>") })).rejects.toMatchObject({ code: "BAD_RESPONSE" })
  })

  test("request timeout aborts and is reported without retry", async () => {
    let calls = 0
    await expect(loadFeed({ timeoutMs: 5, fetchImpl: async (_url, init) => {
      calls++
      return new Promise<Response>((_resolve, reject) => init!.signal!.addEventListener("abort", () => reject(new Error("aborted")), { once: true }))
    } })).rejects.toMatchObject({ code: "REQUEST_TIMEOUT" })
    expect(calls).toBe(1)
  })
})

describe("CLI validation stays offline", () => {
  test.each([
    [], ["wat"], ["search", "--unknown", "x"], ["search", "extra"], ["detail"], ["detail", "1", "extra"],
    ["search", "-q"], ["search", "-q", ""], ["search", "--location", " "], ["search", "--format", "csv"],
    ["search", "--page", "0"], ["search", "--page", "1.5"], ["search", "--page", "1e2"],
    ["search", "--limit", "-1"], ["search", "--jobage", "Infinity"], ["search", "--jobage", "true"],
    ["search", "--page", "9007199254740992"], ["search", "-q", "react", "--query", "java"],
    ["detail", "https://evil.test/remote-jobs/remote-role-42"], ["detail", "42", "--query", "react"],
  ])("invalid invocation emits JSON stderr, no stdout or request: %j", async (...args: string[]) => {
    const c = capture()
    expect(await main(args, c.runtime)).toBe(1)
    expect(c.stdout()).toBe("")
    expect(JSON.parse(c.stderr())).toMatchObject({ error: expect.any(String), code: expect.any(String) })
    expect(c.requests).toHaveLength(0)
  })

  test("actual executable emits stderr JSON and exit 1 for unknown flag", async () => {
    const result = await runCLI(["search", "--bogus"])
    expect(result.exitCode).toBe(1)
    expect(result.stdout).toBe("")
    expect(JSON.parse(result.stderr).code).toBe("UNKNOWN_FLAG")
  })

  test("actual executable help is successful and performs no search", async () => {
    const result = await runCLI(["--help"])
    expect(result.exitCode).toBe(0)
    expect(result.stderr).toBe("")
    expect(result.stdout).toContain("client-side")
  })
})
