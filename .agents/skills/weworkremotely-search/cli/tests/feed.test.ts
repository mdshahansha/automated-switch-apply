import { describe, expect, test } from "bun:test"
import { CLIError, FEED_URL, PAGE_SIZE, USER_AGENT, decodeEntities, fetchFeed, parseFeed, postingSlug, type Job } from "../src/helpers.js"
import { searchJobs } from "../src/commands/search.js"
import { detailJob } from "../src/commands/detail.js"
import { main } from "../src/cli.js"
import { runCLI } from "./helpers.js"

const xml = await Bun.file(new URL("./fixtures/jobs.xml", import.meta.url)).text()
const jobs = parseFeed(xml)
const now = Date.parse("2026-10-23T12:00:00Z")

describe("RSS parsing", () => {
  test("isolates malformed entries, rejects off-host links, and deduplicates", () => {
    expect(jobs).toHaveLength(4)
    expect(jobs.map((j) => j.id)).toContain("recovered-data-engineer")
    expect(jobs[0]).toMatchObject({ title: "React Engineer", company: "Example & Co", location: "Anywhere in the World",
      country: "India, Singapore", date: "2026-10-22T12:00:00.000Z", employmentType: "Full-Time" })
  })
  test("decodes XML and CDATA HTML without losing paragraphs or literal text", () => {
    expect(jobs[0].description).toBe("Build React & TypeScript.\n\nSecond paragraph with <literal> and 🚀.\n\n• First point\n\n• Second point")
    expect(jobs[1].description).toBe("Use Node.js & databases.\n\nKeep two paragraphs.\nAnd a line.")
    expect(decodeEntities("&#x1F680; &#128640; &#x110000; &nbsp;")).toBe("🚀 🚀   ")
  })
  test("missing and malformed fields remain explicit nulls", () => {
    expect(jobs[2]).toMatchObject({ company: null, location: null, date: null, description: null, expiresAt: null })
    expect(Object.keys(jobs[2])).toEqual(expect.arrayContaining(["id", "title", "company", "location", "date", "url"]))
  })
  test("non-feed responses fail clearly; empty feed is valid", () => {
    expect(() => parseFeed("<html>Access denied</html>")).toThrow(CLIError)
    expect(parseFeed("<rss><channel></channel></rss>")).toEqual([])
    expect(() => parseFeed("")).toThrow(CLIError)
  })
})

describe("local search and detail", () => {
  test("keyword and geography are explicit client-side substring filters", () => {
    expect(searchJobs(jobs, { query: "tYpEsCrIpT", location: "India", page: 1 }, now).results).toHaveLength(1)
    expect(searchJobs(jobs, { location: "California", page: 1 }, now).results).toHaveLength(0)
    expect(searchJobs(jobs, { location: "India", page: 1 }, now).results).toHaveLength(2)
  })
  test("age excludes unknown, old and future publication dates", () => {
    const future: Job = { ...jobs[0], id: "future", date: "2026-10-24T12:00:00Z" }
    expect(searchJobs([...jobs, future], { jobage: 2, page: 1 }, now).results).toHaveLength(2)
    expect(searchJobs(jobs, { page: 1 }, now).results).toHaveLength(4)
  })
  test("page and limit apply after filtering with fixed page boundaries", () => {
    const many = Array.from({ length: 45 }, (_, n) => ({ ...jobs[0], id: `example-${n}` }))
    const result = searchJobs(many, { page: 2, limit: 3 }, now)
    expect(result.meta).toMatchObject({ count: 3, page: 2, pageSize: PAGE_SIZE, total: 45 })
    expect(result.results.map((j) => j.id)).toEqual(["example-20", "example-21", "example-22"])
    expect(searchJobs(many, { page: 1, limit: 100 }, now).results).toHaveLength(20)
    expect(searchJobs(many, { page: 4 }, now).results).toEqual([])
  })
  test("detail uses exact feed membership and does not invent closed status", () => {
    expect(detailJob(jobs, jobs[0].url)).toEqual(jobs[0])
    expect(detailJob(jobs, jobs[0].id)).toEqual(jobs[0])
    expect(detailJob(jobs, "missing-example")).toBeNull()
    expect(jobs[0]).not.toHaveProperty("isActive")
  })
})

describe("network boundary", () => {
  test("normal load requests only the official RSS once with an honest UA", async () => {
    const calls: Array<{ url: string; init?: RequestInit }> = []
    const request = (async (url: string | URL | Request, init?: RequestInit) => {
      calls.push({ url: String(url), init }); return new Response(xml)
    }) as typeof fetch
    expect(parseFeed(await fetchFeed({ fetch: request }))).toHaveLength(4)
    expect(calls).toHaveLength(1)
    expect(calls[0].url).toBe(FEED_URL)
    expect(new Headers(calls[0].init?.headers).get("User-Agent")).toBe(USER_AGENT)
    expect(calls[0].init?.redirect).toBe("error")
  })
  test("retries only transient statuses with bounded backoff; 404 is an error", async () => {
    let calls = 0
    const delays: number[] = []
    const request = (async () => new Response(++calls < 3 ? "busy" : xml, { status: calls < 3 ? 503 : 200 })) as unknown as typeof fetch
    await fetchFeed({ fetch: request, sleep: async (n) => { delays.push(n) }, random: () => 0 })
    expect(calls).toBe(3); expect(delays).toEqual([500, 1000])
    const missing = (async () => new Response("", { status: 404 })) as unknown as typeof fetch
    await expect(fetchFeed({ fetch: missing })).rejects.toThrow("404")
    const denied = (async () => new Response("", { status: 403 })) as unknown as typeof fetch
    await expect(fetchFeed({ fetch: denied })).rejects.toThrow("403")
  })
  test("honors numeric/date Retry-After and stops instead of waiting over 30 seconds", async () => {
    for (const [header, expected] of [["2", 2000], ["Fri, 23 Oct 2026 12:00:03 GMT", 3000]] as const) {
      let count = 0
      const delays: number[] = []
      const request = (async () => ++count === 1
        ? new Response("busy", { status: 429, headers: { "Retry-After": header } })
        : new Response(xml)) as unknown as typeof fetch
      await fetchFeed({ fetch: request, sleep: async (ms) => { delays.push(ms) }, now: () => now, random: () => 0 })
      expect(delays).toEqual([expected]); expect(count).toBe(2)
    }
    for (const header of ["31", "Fri, 23 Oct 2026 12:01:00 GMT"]) {
      let count = 0, sleeps = 0
      const request = (async () => { count++; return new Response("busy", { status: 503, headers: { "Retry-After": header } }) }) as unknown as typeof fetch
      try {
        await fetchFeed({ fetch: request, sleep: async () => { sleeps++ }, now: () => now })
        throw new Error("Expected RETRY_LATER")
      } catch (error) { expect((error as CLIError).code).toBe("RETRY_LATER") }
      expect(count).toBe(1); expect(sleeps).toBe(0)
    }
  })
  test("retry exhaustion and transport errors remain errors", async () => {
    let count = 0
    const request = (async () => { count++; return new Response("", { status: 429 }) }) as unknown as typeof fetch
    await expect(fetchFeed({ fetch: request, sleep: async () => {}, random: () => 0 })).rejects.toThrow("after retries")
    expect(count).toBe(7)
    const broken = (async () => { throw new Error("offline") }) as unknown as typeof fetch
    await expect(fetchFeed({ fetch: broken })).rejects.toThrow("offline")
  })
  test("rejects arbitrary destinations and URL ambiguities", () => {
    for (const input of ["https://evil.example/remote-jobs/role", "http://weworkremotely.com/remote-jobs/role",
      "https://user:secret@weworkremotely.com/remote-jobs/role", "https://weworkremotely.com:8080/remote-jobs/role",
      "https://weworkremotely.com/remote-jobs/role?x=1", "https://weworkremotely.com/remote-jobs/role#x",
      "https://weworkremotely.com/remote-jobs/a/../role", "https://weworkremotely.com/remote-jobs/%72ole",
      "https://weworkremotely.com/remote-jobs/role/", "../secret"]) {
      expect(() => postingSlug(input)).toThrow(CLIError)
    }
  })
})

describe("CLI", () => {
  async function invoke(args: string[]) {
    let stdout = "", stderr = "", loads = 0
    const exitCode = await main(args, { load: async () => { loads++; return jobs }, now,
      stdout: (s) => { stdout += s }, stderr: (s) => { stderr += s } })
    return { exitCode, stdout, stderr, loads }
  }
  test("JSON search/detail, text outputs and missing detail use one snapshot", async () => {
    const search = await invoke(["search", "-q", "React", "-l", "India", "--limit", "1"])
    expect(search.exitCode).toBe(0); expect(search.loads).toBe(1); expect(search.stderr).toBe("")
    expect(JSON.parse(search.stdout).results[0].title).toBe("React Engineer")
    expect(JSON.parse((await invoke(["detail", "absent-role"])).stdout)).toBeNull()
    expect((await invoke(["detail", jobs[0].url, "--format", "plain"])).stdout).toContain("\n\nSecond paragraph")
    expect((await invoke(["search", "--format", "table"])).stdout).toContain("We Work Remotely link")
    expect(JSON.parse((await invoke(["detail", jobs[0].id])).stdout).description).toContain("Build React")
  })
  test("optional search descriptions come from one feed load and preserve the default contract", async () => {
    const ordinary = await invoke(["search", "-q", "React"])
    expect(JSON.parse(ordinary.stdout).results[0]).not.toHaveProperty("description")
    const expanded = await invoke(["search", "-q", "React", "--include-description"])
    expect(expanded.exitCode).toBe(0); expect(expanded.loads).toBe(1)
    expect(JSON.parse(expanded.stdout).results[0].description).toBe(jobs[0].description)
    const repeated = await invoke(["search", "--include-description", "--include-description"])
    expect(repeated.exitCode).toBe(1); expect(repeated.loads).toBe(0)
  })
  test("bad input errors go to stderr before loading", async () => {
    for (const args of [[], ["oops"], ["detail"], ["search", "extra"], ["detail", "slug", "extra"],
      ["search", "--wat", "x"], ["search", "--query"], ["search", "-q", ""], ["search", "--location", " "],
      ["search", "--format", "yaml"], ["search", "--page", "0"], ["search", "--limit", "-1"],
      ["search", "--jobage", "1.5"], ["search", "--page", "1e2"], ["search", "--limit", "9007199254740992"],
      ["search", "-q", "one", "--query", "two"], ["detail", "https://evil.example/remote-jobs/role"]]) {
      const result = await invoke(args)
      expect(result.exitCode).toBe(1); expect(result.stdout).toBe(""); expect(result.loads).toBe(0)
      expect(JSON.parse(result.stderr)).toHaveProperty("code")
    }
  })
  test("process entrypoint has the same offline error and help contract", async () => {
    const error = await runCLI(["search", "--bogus"])
    expect(error.exitCode).toBe(1); expect(error.stdout).toBe(""); expect(JSON.parse(error.stderr).code).toBe("UNKNOWN_FLAG")
    const help = await runCLI(["--help"])
    expect(help.exitCode).toBe(0); expect(help.stderr).toBe(""); expect(help.stdout).toContain("client-side")
  })
})
