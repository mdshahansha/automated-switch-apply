---
name: ai-job-search-workspace
description: Use when the user wants to search for jobs, rank or evaluate postings, tailor a CV or cover letter, track applications, research companies, upskill for a role, prepare for interviews, or manage this complete AI job-search workspace. Treat the bundled .claude workflow specifications and candidate-profile files as the source of truth.
---

# AI Job Search Workspace

This plugin packages the complete workspace located at the plugin root.

## Source of truth

- Read `CLAUDE.md` for the candidate profile and workspace-wide conventions.
- Read the relevant workflow under `.claude/commands/` before acting.
- Read the relevant supporting instructions under `.claude/skills/`.
- Use portal-specific search skills under `.agents/skills/` when searching job boards.
- Preserve the single-source-of-truth design; do not duplicate workflow rules in this file.

## Routing

Map requests to the canonical workflow files rather than inventing a parallel process:

- setup/reset and candidate configuration: `.claude/commands/setup.md` and `.claude/commands/reset.md`
- scrape/search: `.claude/commands/scrape.md` and `.claude/skills/job-scraper/`
- rank/evaluate: `.claude/commands/rank.md`
- applications and document tailoring: `.claude/commands/apply.md`, `cv/`, `cover_letters/`, and `templates/`
- company research: `.claude/commands/research.md` and `company_research/`
- upskilling: `.claude/commands/upskill.md` and `upskill/`
- interview preparation: `.claude/commands/interview.md` and the related `.claude/skills/`

Use the scripts in `tools/` and the tests in `tests/` where the canonical workflow calls for them. Keep personal data and generated artifacts scoped to the existing directories and follow the repository's security guidance.
