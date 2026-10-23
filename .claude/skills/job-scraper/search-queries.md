# Search Queries for Job Scraper

<!-- SETUP: Customize these queries based on your skills, target roles, and location -->

## Installed portal CLIs (primary for `/scrape`)

`/scrape` discovers every portal skill under `.agents/skills/*/SKILL.md` and runs its CLI first. Shipped country-agnostic CLIs include `linkedin-search` and `freehire-search`; Danish demos and any skill you add with `/add-portal` are included the same way. You do **not** need a matching `site:` line below for those CLIs to run.

The `site:` query templates in this file are the **WebSearch fallback** — for portals without a CLI, company career pages, or when a CLI fails.

**Language scope:** write every query category in every language listed in your CLAUDE.md Languages table (typically 1-2, sometimes more). A posting requiring a language you have *not* declared, as a job condition, is excluded before scoring; a posting requiring a *higher level* than you declared in a language you *do* work in is flagged for your own judgment, not excluded — see `04-job-evaluation.md`'s Language Gate, the single source of truth for this rule. Translate each category's keywords rather than machine-translating word-for-word (e.g. "Frontend Developer" -> "Desarrollador Frontend", not a literal word-for-word translation) if you work in more than one language.

## Search Sites

Primary:
- **linkedin.com/jobs** - installed `linkedin-search` CLI, with India supplied explicitly as the location. Search remote-from-India roles separately.
- **freehire.me** - installed `freehire-search` CLI for technical roles; use its documented India and remote filters, then verify each employer's location eligibility.
- **naukri.com** - India-focused WebSearch fallback; no local CLI is installed.
- **Employer career pages** - WebSearch fallback and role verification for direct postings.

The candidate accepts any Indian city and any work mode, with a 30-day notice period. Salary is flexible with no numeric filter. Do not infer sponsorship or foreign work authorization from willingness to work remotely.

Secondary (company career pages via Google):
- Direct Google searches with `site:` filters for known target companies

## Query Categories

Queries are grouped by priority. Write **each category in every language from your Languages table** (see Language scope above). Combine each query with your location terms (e.g. your city, region, or metro area) where the site supports it.

**Organize by function, not job title.** The same underlying work carries different titles across companies and markets (a "Data Scientist" role at one employer may be posted as "Insights Analyst" or "Data Consultant" at another). Name each priority category after the function it covers, and list several plausible job titles as query variants within that category rather than betting an entire priority tier on one exact title string.

### Priority 1: Full-stack product engineering

These match your strongest and most desired career direction.

```
site:linkedin.com/jobs "Full Stack Engineer" React TypeScript India
site:linkedin.com/jobs "Full Stack Developer" Node.js India
site:naukri.com "Full Stack Developer" React India
"Software Engineer" React Node.js "remote India"
```

Hindi query variants (keep technology names and employer job titles intact):
```
"फुल स्टैक डेवलपर" React भारत नौकरी
"सॉफ्टवेयर इंजीनियर" Node.js भारत
```

### Priority 2: Backend APIs and Java/Spring Boot delivery

These match your domain expertise.

```
site:linkedin.com/jobs "Backend Engineer" Node.js India
site:linkedin.com/jobs "Java Developer" "Spring Boot" India
site:naukri.com "Java Full Stack Developer" India
"Backend Developer" TypeScript Redis "remote India"
```

Hindi query variants:
```
"बैकएंड डेवलपर" Node.js भारत नौकरी
"जावा डेवलपर" "Spring Boot" भारत
```

### Priority 3: React web and React Native mobile engineering

Additional search directions supported by the candidate's confirmed working stacks.

```
site:linkedin.com/jobs "React Native Developer" India
site:linkedin.com/jobs "Frontend Engineer" React TypeScript India
site:naukri.com "React Developer" India
"Mobile Engineer" "React Native" "remote India"
```

Hindi query variants:
```
"फ्रंटएंड डेवलपर" React भारत नौकरी
"मोबाइल ऐप डेवलपर" "React Native" भारत
```

### Priority 4: Broader software and international remote engineering

Wider net for software engineering roles and international employers that explicitly support remote work from India. Specialist AI, infrastructure, and lead/management roles need evidence of the required depth rather than a title-only match.

```
"Software Engineer" TypeScript "remote from India"
"Full Stack Engineer" "India" "worldwide"
site:boards.greenhouse.io "software engineer" "India" "remote"
site:jobs.lever.co "full stack" "India" "remote"
```

Hindi query variants:
```
"सॉफ्टवेयर इंजीनियर" "भारत से रिमोट"
"फुल स्टैक" "वर्क फ्रॉम होम" भारत
```

## Location Filter

When evaluating results, use the confirmed geographic scope:
- **Accept:** Any Indian city, remote/hybrid/onsite. The current role is in Kolkata, but the home city is not separately confirmed and must not limit searches.
- **Accept after verification:** International employers explicitly permitting remote work from India. Check country restrictions, hiring arrangement, and required time-zone overlap against the actual posting.
- **Flag:** A generic remote/worldwide label without clear India eligibility; jobs requiring a start sooner than the 30-day notice; unspecified shift/travel requirements that matter to the role.
- **Ask before including as a relocation target:** Onsite/hybrid work outside India. Overseas work authorization and relocation are not confirmed.
- **Salary:** No numeric minimum or currency amount supplied. Do not filter all jobs out for missing salary, or treat flexible expectations as authorization to answer a mandatory numeric field.

## Language Filter

Your working languages and levels are in CLAUDE.md's Languages table. When filtering scraped results, apply `04-job-evaluation.md`'s Language Gate: a posting requiring a language you haven't declared at all is excluded; a posting requiring a higher level than you declared in a language you do work in is not excluded, flag it clearly instead (see `job-scraper/SKILL.md`'s Step 3 "Quick Fit Assessment" for how the flag surfaces in `/scrape` output). Postings simply *written* in a language you don't work in, that don't require it on the job, are fine.

## Date Filter

Only include jobs posted within the last 14 days, or with an application deadline that has not yet passed. If a posting date cannot be determined, include it but flag as "date unknown".

## Adapting Queries

If the user specifies a focus area, select queries from the matching category and also generate 2-3 custom queries for that focus. For example:
- "/scrape [focus_area]" -> relevant category queries + custom focus-specific queries
