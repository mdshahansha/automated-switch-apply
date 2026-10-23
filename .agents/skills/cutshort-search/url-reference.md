# Cutshort public navigation and access

Checked 2026-10-23 with an identifying research User-Agent; no credentials.

- Canonical domain: https://cutshort.io/ (confirmed by https://cutshort.io/llms.txt).
- Jobs: https://cutshort.io/jobs
- Verified listing: https://cutshort.io/jobs/software-development-jobs
- City listing example: https://cutshort.io/jobs/software-development-jobs-in-pune
- Example linked detail: https://cutshort.io/job/Full-Stack-Software-Engineer-Provenir-I1i8FXO2
- Robots: https://cutshort.io/robots.txt
- Terms: https://cutshort.io/terms
- Official developer docs: https://cutshort.io/a/devdocs redirects to https://developers.cutshort.io/introduction

Public listing patterns are `/jobs/<skill>-jobs`,
`/jobs/<skill>-jobs-in-<city>`, and `/jobs/remote-<skill>-jobs`; details use
`/job/<slug>-<id>`. Follow site-generated links. No arbitrary free-text query
parameter is verified here.

The software-development listing returned HTTP 200 with populated descriptions
and public detail links. Robots blocks profiles, apply routes and some query
variants. Terms updated September 7, 2026 explicitly prohibit automated service
access and systematic or automated collection; do not infer consent from public
HTML or `llms.txt`.

The documented API requires an approved employer and API key. Its `GET /jobs`
lists the authenticated workspace's jobs; candidate-search endpoints search
people for employers. It does not supply public job-seeker search, and this
skill does not access it. No suitable public vacancy feed was verified.
