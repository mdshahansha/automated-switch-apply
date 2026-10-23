# Instahyre access reference

Verified 2026-10-23 with an honest tool-identifying User-Agent.

| Purpose | URL | Observation |
|---|---|---|
| Official site | https://www.instahyre.com/ | HTTP 520 in direct request and web fetch. |
| Robots | https://www.instahyre.com/robots.txt | HTTP 200; sitemap plus an empty generic User-agent group. Does not establish terms permission. |
| Sitemap | https://www.instahyre.com/sitemap.xml | HTTP 520. |
| Terms probe | https://www.instahyre.com/terms/ | HTTP 520; current terms could not be verified. This is not proof of a supported terms route. |
| Matching | https://help.instahyre.com/en/article/explore-matching-opportunities-1s98q42/ | Official help: Opportunities tab matches resume, preferences and experience; View opens full vacancy. |
| Overview | https://help.instahyre.com/en/article/what-is-instahyre-1ufln5/ | Official help describes a profile-based curated job service. |
| Shared jobs | https://help.instahyre.com/en/article/manage-your-job-openings-1kno1ld/ | Official help confirms jobs can be shared via direct links, but supplies no stable URL pattern. |

No actual anonymous software search/detail response or public search API/feed could be verified. Do not present guessed `/software-engineer-jobs/` or `/job-*` paths as supported endpoints. Use the homepage, user-provided share link and normal account UI. A successful robots request does not establish job access. No CLI is included.
