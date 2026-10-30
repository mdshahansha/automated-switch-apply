# Indeed India public URL reference

Verified 2026-10-23 with an honest tool-identifying User-Agent.

| Purpose | URL | Observation |
|---|---|---|
| Search | https://in.indeed.com/jobs?q=software+engineer&l=India | HTTP 403; stop, no access bypass. |
| Indexed SEO search | https://in.indeed.com/q-software-engineer-2026-jobs.html?vjk=5ff70e7390dfdfad | Official indexed software results; index availability does not verify current vacancy status. |
| Robots | https://in.indeed.com/robots.txt | HTTP 200; generic group disallows `/viewjob`, `/rss`, `/graphql`, internal APIs and most pagination variants. |
| Terms | https://in.indeed.com/legal?hl=en | Current Site Rules §21 restrict automated systems without permission and prohibit bypassing controls. Conditional crawl permission is limited to robots.txt. |
| Official integrations | https://docs.indeed.com/job-postings | Updated 2026-10-07: Job Sync API/XML publish jobs; Job Update API manages ATS-integrated postings; Publisher JavaScript Plugin serves publishing partners. |
| Developer access | https://docs.indeed.com/ | Partner Console access is provisioned by Indeed. No anonymous job-search CLI API established. |

Search shape `/jobs?q={encoded keywords}&l={encoded location}`. SEO shape `/q-{query}-l-{location}-jobs.html`. Known detail shape `/viewjob?jk={id}` was not probed because robots disallows it. No undocumented API, legacy RSS or third-party unlocker is used. Approved partner integrations are a separate provisioning task, not a substitute for this manual workflow. No CLI is included.
