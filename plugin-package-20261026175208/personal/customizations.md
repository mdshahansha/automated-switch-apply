# Customizations Log - Mohammad Shahansha

Every customization made to this workspace for the candidate. Folder `personal/` is gitignored.
Last updated: 2026-10-26.

## Files in this folder
- `personal-candidate.md` - all application form answers (contact, DOB, CTC, education, notice, About text).
- `Mohammad_Shahansha_Resume.pdf` - default resume for uploads (correct email and dates).
- `md_shahansha_JFS.pdf`, `mohammad_shahansha_.pdf`, `mohammad_SHAHANSHA_rn.pdf`, `mohammadshahansha_be.pdf`,
  `mohammadshahansha_fse.pdf`, `mohammadshahansha_RJ.pdf`, `mohammadshahansha_se.pdf` - older role variants.
  They carry the old email and old dates (Osbee Nov 2024; CodingNinjas Jul 2023-Oct 2024); do not upload until fixed.
- `customizations.md` - this file.

## Application answers chosen by the candidate
- Notice period on forms: 15 days (contractual notice at Osbee: 30 days).
- Current CTC 8 LPA; expected 20+ LPA; on Naukri 15+ LPA.
- Location: any Indian city; remote, hybrid or onsite.
- Reason for leaving Osbee: greater opportunities, learning and growth.
- May 2025 gap: left unexplained.
- Years per skill: candidate asked for "4+" on all; not used until reconfirmed (total experience ~3y4m).

## Job search setup
- Platforms: LinkedIn, Naukri, Hirist only.
  - LinkedIn: `linkedin-search` CLI (only enabled CLI).
  - Naukri: `site:naukri.com` WebSearch queries (no CLI).
  - Hirist: `site:hirist.tech` WebSearch queries + public pages (browser-only skill, stays `enabled: false`).
- Disabled portals (`enabled: false`): freehire-search, himalayas-search, remoteok-search, weworkremotely-search.
- Query file edited: `.claude/skills/job-scraper/search-queries.md` (Search Sites + all query lines scoped to the three platforms; Hindi variants on Naukri).
- bun 1.4.4 installed globally (`npm install -g bun`) to run portal CLIs.
- First 24h scrape (2026-10-26): 20 jobs stored in `job_scraper/seen_jobs.json` (8 high, 7 medium, 5 low/expired).

## Applying rules
- Resume upload: `Mohammad_Shahansha_Resume.pdf`.
- Each final submit needs the candidate's yes.
- CAPTCHA/OTP: candidate solves; the assistant does not.
- Sign-in: candidate logs in; the assistant never types passwords.

## Profile and repo changes
- `01-candidate-profile.md`: added Monkster part-time role (Apr-Sep 2023) and pointer to private answers.
- `documents/applications/application_form_details.md`: earlier copy of form answers (notice updated to 15 days).
- `.gitignore`: added `personal/`; removed leftover merge markers.
- Merge conflict markers resolved (HEAD side kept) in 13 files, incl. `tools/rank_state.py`, `.claude/commands/rank.md`, three portal CLIs.

## Open items
- `tools/portal_jobs.py` and `tests/test_portal_jobs.py` were deleted outside the session; `tests/test_portal_search.py` fails to import. Restore or confirm.
- `/reset` test expects heading `## Ready-Made STAR Examples` in `07-interview-prep.md`.
- Missing: Class 10/12 school names and years, Monkster title, full street address.
- Nothing committed yet.

## Application pipeline (added 2026-10-26)
- Helper: `tools/job_pipeline.py` (commands: add, start, finish, status).
- Folders: `output/job_pipeline/<date>/` holds `queue.csv`, `in_progress.csv`, `completed.csv`;
  the whole day folder moves to `output/job_pipeline/done/<date>/` once queue and in_progress are empty.
- Columns: id, fit, title, company, location, exp_asked, link, portal, posted_date, stage, status,
  model_used, resume_used, queued_at, started_at, completed_at, notes.
- `output/job_pipeline/` is gitignored. Seeded 2026-10-26 with 15 jobs (8 high, 7 medium).

## Queue processing rules (candidate decisions, 2026-10-26)
- Work through all queued high and medium jobs, high fit first, one at a time.
- High fit: tailored CV + cover letter. Medium fit: default resume `personal/Mohammad_Shahansha_Resume.pdf`.
- Years-of-experience fields: real figures (React/Node/TypeScript/REST APIs: 3; Spring Boot and React Native in production: 1).
- External company sites needing an account: pause; candidate creates the account and signs in.
- Every final submit still needs the candidate's explicit yes.
