# AIJobs: identity must be confirmed

Checked 2026-10-23 with an identifying research User-Agent; no credentials.

| Candidate service | Public evidence | Navigation and limits |
| --- | --- | --- |
| https://aijobs.ai/ | Home and `https://aijobs.ai/jobs?keyword=software` returned HTTP 200; titles included Software Engineer, Open Source AI at Backblaze. | Search form uses GET `/jobs?keyword=<text>`. Detail links use `/job/<slug>`, but https://aijobs.ai/robots.txt disallows `/job/`. https://aijobs.ai/terms-condition contained placeholder text. No documented public search API/feed verified. |
| https://www.aijobs.com/ | Home returned HTTP 200 with populated job cards. | Visible search starts at https://www.aijobs.com/jobs; details use `/jobs/<numeric-id>-<slug>`. https://www.aijobs.com/robots.txt disallows `/rss/` and specifies crawl-delay 1. https://www.aijobs.com/terms explicitly prohibits automated access and systematic downloading. Manual-only. |
| Old https://aijobs.net/ | Request to `https://aijobs.net/robots.txt` redirected to https://foorilla.com/hiring/ and returned HTML rather than robots text. | This is a different current destination; confirm the user's intended site before navigation or research. Do not assume rules or endpoints from either service above apply. |

These are alternative identities, not aliases. None is selected by this skill.
No CLI, credentials, API calls or automated listing collection is provided.
