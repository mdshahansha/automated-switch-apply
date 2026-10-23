# Protocol Jobs official surfaces

Checked 2026-10-23 with an identifying research User-Agent; no credentials.

- Official website: https://protocoljobs.ai/
- Official jobs app linked from that site: https://app.protocoljobs.ai/dashboard
- Marketing robots: https://protocoljobs.ai/robots.txt
- App robots: https://app.protocoljobs.ai/robots.txt
- Public sitemap: https://app.protocoljobs.ai/sitemap.xml
- Privacy policy: https://protocoljobs.ai/privacy-policy
- Detail pattern: `https://app.protocoljobs.ai/job/details?id=<24-hex-id>`.

The dashboard returned HTTP 200 with filter controls but no server-rendered
vacancy list. No query URL or documented public search API was verified. App
robots explicitly allows `/dashboard`, `/linkedin`, `/job/details`, and disallows
`/api/` plus private/account routes. No terms link was found in the inspected
public pages; absence is not consent to automate.

The sitemap returned HTTP 200 with public detail links and modification dates.
Example: https://app.protocoljobs.ai/job/details?id=6adb5d4760aedc7cff766418
returned a public Product Solution Engineer posting at HighLevel, posted
2026-10-23, full-time/remote, with `validThrough=2026-11-22`. Detail pages include
schema.org `JobPosting` title, description, employer, dates, location/work mode
and experience; salary can be an estimate supplied by Protocol.

Expiry matters: https://app.protocoljobs.ai/job/details?id=6aab9cc3dc3e4db3b1d70fba
still returned HTTP 200 with a Rippling software role whose structured expiry was
2026-10-17. A 200 response alone does not establish an active vacancy. These
observations support manual navigation, not a verified search CLI.
