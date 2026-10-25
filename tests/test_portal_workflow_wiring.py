"""/scrape and /apply reach the portal registry through tools/portal_search.py.

The runner is only useful if the commands call it. These checks pin the call
sites and the safety wording, so a later edit cannot silently drop them.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRAPE = (ROOT / ".claude" / "skills" / "job-scraper" / "SKILL.md").read_text(encoding="utf-8")
APPLY = (ROOT / ".claude" / "commands" / "apply.md").read_text(encoding="utf-8")


class ScrapeWiringTests(unittest.TestCase):
    def test_allowed_tools_permit_the_runner(self):
        frontmatter = SCRAPE.split("\n---", 1)[0]
        self.assertIn("Bash(python3 tools/portal_search.py:*)", frontmatter)
        self.assertIn("Bash(python tools/portal_search.py:*)", frontmatter)

    def test_arguments_are_resolved_before_the_legacy_search(self):
        self.assertLess(SCRAPE.index("### Step 0.5: Portal selection"), SCRAPE.index("### Step 1: Search"))
        for command in ("portal_search.py resolve", "portal_search.py status", "portal_search.py links",
                        "portal_search.py search", "portal_search.py import"):
            with self.subTest(command=command):
                self.assertIn(command, SCRAPE)

    def test_no_selector_keeps_the_old_behavior(self):
        self.assertIn("With no portal or group name, `/scrape` behaves exactly as before.", SCRAPE)

    def test_registry_jobs_are_not_stored_twice(self):
        self.assertIn("Do not also pass these jobs to `scrape_state.py store`.", SCRAPE)


class ApplyWiringTests(unittest.TestCase):
    def test_host_check_uses_the_registry_helper(self):
        self.assertIn('python3 tools/portal_search.py host "<posting URL>"', APPLY)

    def test_destination_step_follows_recording_and_gates_submission(self):
        self.assertLess(APPLY.index("### Step 6b: Record the Application"),
                        APPLY.index("### Step 6c: Application Destination"))
        step = APPLY[APPLY.index("### Step 6c"):APPLY.index("### Application-Form Fields")]
        for phrase in ("ask once", "never ask again for the same approval", "solve a CAPTCHA",
                       "Never type passwords", "create an account", "application_record.py next", "stays `drafted`",
                       "only after the user reports a confirmation", "Never invent one"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, step)
        for method in ("employer_link", "portal_account", "unknown"):
            with self.subTest(method=method):
                self.assertRegex(step, re.escape(f"`{method}`"))


if __name__ == "__main__":
    unittest.main()
