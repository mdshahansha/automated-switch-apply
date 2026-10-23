import { afterEach, expect, test } from "bun:test";
import { apiFetch, htmlFetch } from "../src/helpers";

const originalFetch = globalThis.fetch;

afterEach(() => {
  globalThis.fetch = originalFetch;
});

for (const kind of ["api", "html"] as const) {
  test(`${kind} requests identify the repository and tool without a browser identity`, async () => {
    let sentHeaders = new Headers();
    globalThis.fetch = (async (_input: unknown, init?: RequestInit) => {
      sentHeaders = new Headers(init?.headers);
      return new Response(kind === "api" ? "{}" : "<p>Job</p>", {
        status: 200,
        headers: { "Content-Type": kind === "api" ? "application/json" : "text/html" },
      });
    }) as typeof fetch;

    if (kind === "api") await apiFetch("/api/jobs");
    else await htmlFetch("https://www.jobindex.dk/jobannonce/example");

    const agent = sentHeaders.get("User-Agent") ?? "";
    expect(agent).toContain("mdshahansha/automated-switch-apply/");
    expect(agent).toContain("jobindex-search-cli");
    expect(agent).not.toMatch(/Mozilla|Chrome|Safari|@/);
  });
}
