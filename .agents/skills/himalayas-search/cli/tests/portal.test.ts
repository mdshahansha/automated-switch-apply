import { describe, expect, test } from "bun:test"
import { detailURL, htmlToText, parseJob, parseSearch, requestJSON, retryDelay, USER_AGENT, unixDate, type FetchLike } from "../src/helpers.js"
import { buildSearchURL, searchJobs, type SearchOpts } from "../src/commands/search.js"
import { getDetail } from "../src/commands/detail.js"
import { parseArgs } from "../src/cli.js"
import { runCLI } from "./helpers.js"

const NOW = Date.parse("2026-10-23T12:00:00Z")
const job = (slug = "frontend-engineer", more: Record<string, unknown> = {}) => ({
  guid: `https://himalayas.app/companies/example/jobs/${slug}`,
  title: "Frontend &amp; Platform Engineer", companyName: "Example", companySlug: "example",
  locationRestrictions: ["India"], timezoneRestrictions: [5.5],
  description: "<p>Build React &amp; Node.js.</p><ul><li>Remote from India</li></ul>",
  applicationLink: `https://himalayas.app/companies/example/jobs/${slug}?utm_source=api`,
  pubDate: NOW / 1000 - 86400, expiryDate: NOW / 1000 + 86400,
  ...more,
})
const json = (value: unknown, status = 200, headers: Record<string, string> = {}) => new Response(JSON.stringify(value), { status, headers })
const options: SearchOpts = { query: "react", country: "IN", page: 1, format: "json" }
const fetcher = (response: Response): FetchLike => async () => response

describe("response parsing", () => {
  test("normalizes real API shape and keeps source apply URL and restrictions", () => {
    const parsed = parseJob(job())!
    expect(parsed.id).toBe("example/frontend-engineer")
    expect(parsed.title).toBe("Frontend & Platform Engineer")
    expect(parsed.description).toBe("Build React & Node.js.\n\n• Remote from India")
    expect(parsed.applicationLink).toEndWith("?utm_source=api")
    expect(parsed.locationRestrictions).toEqual(["India"])
    expect(parsed.timezoneRestrictions).toEqual([5.5])
    expect(parsed.date).toBe("2026-10-22T12:00:00.000Z")
    expect(parsed.minSalary).toBeNull()
    expect(parsed.employmentType).toBeNull()
  })
  test("missing values remain null; worldwide is only an explicit empty array", () => {
    const parsed = parseJob({ guid: job().guid, title: "Engineer" })!
    for (const key of ["company", "location", "date", "applicationLink", "expiryDate", "timezoneRestrictions", "seniority"] as const) expect(parsed[key]).toBeNull()
    expect(parseJob(job("world", { locationRestrictions: [] }))?.location).toBe("Worldwide (API location field)")
    expect(unixDate("2026-10-22")).toBeNull()
    expect(unixDate(Infinity)).toBeNull()
  })
  test("reports bad records and refuses unexpected whole-response schema", () => {
    const parsed = parseSearch({ jobs: [null, job(), job("bad", { guid: "https://evil.example/jobs/1" }), { title: "No identity" }] })
    expect(parsed.jobs).toHaveLength(1)
    expect(parsed.skipped).toBe(3)
    expect(parsed.fetchedCount).toBe(4)
    expect(parsed.totalCount).toBeNull()
    expect(() => parseSearch({ results: [] })).toThrow("jobs array")
  })
  test("HTML conversion preserves paragraphs, bullets and unicode entities", () => {
    expect(htmlToText('<style>hide</style><p>Node&#46;js &amp; React</p><p>A<br>B &#x1F680;</p><script>bad()</script>')).toBe("Node.js & React\n\nA\nB 🚀")
  })
})

describe("identity and host boundaries", () => {
  test("accepts returned ID, canonical, API and apply URL forms", () => {
    for (const input of ["example/frontend-engineer", job().guid, `${job().guid}?utm_source=api`, "https://himalayas.app/jobs/api/companies/example/jobs/frontend-engineer"]) {
      expect(detailURL(input)).toEqual({ id: "example/frontend-engineer", canonical: job().guid, url: "https://himalayas.app/jobs/api/companies/example/jobs/frontend-engineer" })
    }
  })
  test("rejects unrelated hosts, credentials, protocols, paths and normalization tricks", () => {
    for (const input of [
      "https://evil.example/companies/example/jobs/frontend-engineer", "https://himalayas.app.evil.example/companies/example/jobs/frontend-engineer",
      "http://himalayas.app/companies/example/jobs/frontend-engineer", "https://user:pass@himalayas.app/companies/example/jobs/frontend-engineer",
      "https://himalayas.app:444/companies/example/jobs/frontend-engineer", "https://himalayas.app/companies/example/frontend-engineer",
      "https://himalayas.app/companies/x/../example/jobs/frontend-engineer", "https://himalayas.app/companies/%65xample/jobs/frontend-engineer",
      "https://himalayas.app/companies/example/jobs/front%2fend", "https://himalayas.app/companies/example/jobs/frontend-engineer#x",
      "https://himalayas.app/companies/example/jobs/frontend-engineer?url=https://evil.example", "//himalayas.app/companies/example/jobs/frontend-engineer",
      "example/jobs/frontend-engineer", "example/../frontend-engineer", "https://himalayas.app\\@evil.example/companies/example/jobs/frontend-engineer",
    ]) expect(() => detailURL(input)).toThrow()
  })
})

describe("search filters and pagination", () => {
  test("encodes supported API filters and an explicit selected page", () => {
    const url = new URL(buildSearchURL({ ...options, page: 3, excludeWorldwide: true, timezone: "UTC+05:30", employmentType: "Full Time,Contractor" }))
    expect(url.searchParams.get("q")).toBe("react")
    expect(url.searchParams.get("country")).toBe("IN")
    expect(url.searchParams.get("exclude_worldwide")).toBe("true")
    expect(url.searchParams.get("timezone")).toBe("UTC+05:30")
    expect(url.searchParams.get("employment_type")).toBe("Full Time,Contractor")
    expect(url.searchParams.get("page")).toBe("3")
    expect(url.searchParams.has("jobage")).toBe(false)
  })
  test("one page, deduplication, expiration, local age and cap work without inventing dates", async () => {
    let requests = 0
    const result = await searchJobs({ ...options, page: 4, jobage: 7, limit: 1 }, {
      now: () => NOW, fetcher: async () => { requests++; return json({ jobs: [job(), job(), job("old", { pubDate: NOW / 1000 - 8 * 86400 }), job("unknown", { pubDate: null }), job("closed", { expiryDate: NOW / 1000 - 1 }), job("next")] }) },
    })
    expect(requests).toBe(1)
    expect(result.meta.page).toBe(4)
    expect(result.meta.appliedFilters.jobage).toBe(7)
    expect(result.results.map(j => j.id)).toEqual(["example/frontend-engineer"])
  })
  test("unknown dates are retained without an age filter, location restrictions preserved", async () => {
    const result = await searchJobs(options, { now: () => NOW, fetcher: fetcher(json({ jobs: [job("unknown", { pubDate: null, locationRestrictions: [] })] })) })
    expect(result.results[0].date).toBeNull()
    expect(result.results[0].locationRestrictions).toEqual([])
    expect(result.meta.eligibility).toContain("check the full description")
  })
})

describe("requests and detail status", () => {
  test("honest UA, Accept, timeout signal and redirect rejection are sent", async () => {
    await requestJSON("https://himalayas.app/jobs/api/search", { fetcher: (async (url: string | URL | Request, init?: RequestInit) => {
      expect(String(url)).toBe("https://himalayas.app/jobs/api/search")
      expect(new Headers(init?.headers).get("User-Agent")).toBe(USER_AGENT)
      expect(new Headers(init?.headers).get("Accept")).toBe("application/json")
      expect(init?.redirect).toBe("error")
      expect(init?.signal).toBeInstanceOf(AbortSignal)
      return json({ jobs: [] })
    }) as FetchLike })
  })
  test("bounded retries honor Retry-After then recover; 403 is not retried", async () => {
    const delays: number[] = []
    let calls = 0
    await requestJSON("https://himalayas.app/jobs/api/search", { random: () => 0, sleep: async ms => { delays.push(ms) }, fetcher: async () => ++calls < 3 ? json({}, 429, { "Retry-After": "2" }) : json({ jobs: [] }) })
    expect(calls).toBe(3)
    expect(delays).toEqual([2000, 2000])
    calls = 0
    await expect(requestJSON("https://himalayas.app/jobs/api/search", { fetcher: async () => { calls++; return json({}, 403) } })).rejects.toMatchObject({ code: "HTTP_403" })
    expect(calls).toBe(1)
    expect(() => retryDelay("999999", 0, NOW, 0)).toThrow("retry later")
    expect(() => retryDelay(new Date(NOW + 60000).toUTCString(), 0, NOW, 0)).toThrow("retry later")
    expect(retryDelay(new Date(NOW + 5000).toUTCString(), 0, NOW, 0)).toBe(5000)
  })
  test("long Retry-After stops without a premature retry", async () => {
    let calls = 0
    let sleeps = 0
    await expect(requestJSON("https://himalayas.app/jobs/api/search", {
      fetcher: async () => { calls++; return json({}, 429, { "Retry-After": "120" }) },
      sleep: async () => { sleeps++ },
    })).rejects.toMatchObject({ code: "RETRY_LATER" })
    expect(calls).toBe(1)
    expect(sleeps).toBe(0)
  })
  test("exhausted 5xx retries and stalled requests fail explicitly", async () => {
    let calls = 0
    await expect(requestJSON("https://himalayas.app/jobs/api/search", { retries: 2, sleep: async () => {}, fetcher: async () => { calls++; return json({}, 503) } })).rejects.toMatchObject({ code: "HTTP_503" })
    expect(calls).toBe(3)
    await expect(requestJSON("https://himalayas.app/jobs/api/search", { timeoutMs: 5, fetcher: (async (_url: unknown, init?: RequestInit) => new Promise((_resolve, reject) => init?.signal?.addEventListener("abort", () => reject(new Error("aborted"))))) as FetchLike })).rejects.toMatchObject({ code: "TIMEOUT" })
  })
  test("404 and closed detail return null; successful detail validates identity", async () => {
    const missing = await getDetail("example/frontend-engineer", { fetcher: fetcher(json({}, 404)) })
    expect(missing.result).toBeNull()
    expect(missing.meta.status).toBe("not_found")
    await expect(searchJobs(options, { fetcher: fetcher(json({}, 404)) })).rejects.toMatchObject({ code: "HTTP_404" })
    const closed = await getDetail("example/frontend-engineer", { fetcher: fetcher(json({ expiryDate: NOW / 1000 }, 410)) })
    expect(closed.result).toBeNull()
    expect(closed.meta.status).toBe("closed")
    const open = await getDetail("example/frontend-engineer", { fetcher: fetcher(json({ job: job() })) })
    expect(open.result?.description).toContain("React & Node.js")
    const expired = await getDetail("example/frontend-engineer", { now: () => NOW, fetcher: fetcher(json({ job: job("frontend-engineer", { expiryDate: NOW / 1000 - 1 }) })) })
    expect(expired.result).toBeNull()
    expect(expired.meta.status).toBe("closed")
    await expect(getDetail("example/other", { fetcher: fetcher(json({ job: job() })) })).rejects.toMatchObject({ code: "INVALID_RESPONSE" })
  })
})

describe("CLI validation without network", () => {
  test("aliases, booleans, CSV and negative timezone survive parsing", () => {
    const parsed = parseArgs(["search", "-q", "React", "--location", "India", "--exclude-worldwide=true", "--timezone", "-5", "--seniority", "Senior, Mid-level", "--limit", "5"])
    expect(parsed.command).toBe("search")
    if (parsed.command === "search") {
      expect(parsed.options.country).toBe("India")
      expect(parsed.options.excludeWorldwide).toBe(true)
      expect(parsed.options.timezone).toBe("-5")
      expect(parsed.options.seniority).toBe("Senior,Mid-level")
    }
  })
  test("invalid flags and conflicting or missing values are JSON stderr with exit 1", async () => {
    for (const args of [[], ["bogus"], ["search", "--bogus", "x"], ["search", "-q"], ["search", "-q", ""], ["search", "--page", "1.5"], ["search", "--limit", "21"], ["search", "--jobage", "0"], ["search", "--worldwide"], ["search", "--worldwide", "yes"], ["search", "--exclude-worldwide", "true"], ["search", "--country", "IN", "-l", "US"], ["search", "--seniority", "Junior"], ["search", "--format", "csv"], ["search", "--timezone", "UTC+05:99"], ["detail"], ["detail", "one", "two"], ["detail", "https://evil.example/a/b"]]) {
      const result = await runCLI(args)
      expect(result.exitCode).toBe(1)
      expect(result.stdout).toBe("")
      const error = JSON.parse(result.stderr)
      expect(typeof error.error).toBe("string")
      expect(typeof error.code).toBe("string")
    }
  })
  test("help succeeds without live access", async () => {
    const result = await runCLI(["--help"])
    expect(result.exitCode).toBe(0)
    expect(result.stderr).toBe("")
    expect(result.stdout).toContain("--exclude-worldwide")
  })
})
