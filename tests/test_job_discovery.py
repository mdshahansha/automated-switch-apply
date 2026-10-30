"""Freshness, scoring, dedup and malformed-listing guards for job_discovery."""
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import job_discovery as jd  # noqa: E402

NOW = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
CFG = jd.load_config()


def job(**kw):
    base = dict(jobTitle="Full Stack Developer", companyName="Acme", location="Kolkata, India",
                canonicalJobUrl="https://example.test/1", sourceJobId="1", status="open",
                employmentType="Full-time",
                description="We need 2+ years with React, Node.js, Express, MongoDB, MySQL, REST APIs, "
                            "TypeScript and Git. " * 10)
    base.update(kw)
    platform = base.pop("platform", "greenhouse")
    return jd.finalize(jd.make_job(platform, **base), NOW, CFG)


class Freshness(unittest.TestCase):
    def c(self, raw):
        return jd.classify_freshness(raw, NOW, 24)

    def test_exact_inside_and_boundary(self):
        self.assertEqual(self.c("2026-10-26T02:00:00Z")[0], "confirmed_fresh")
        self.assertEqual(self.c("2026-10-25T12:00:00Z")[0], "confirmed_fresh")  # exactly 24h
        self.assertEqual(self.c("2026-10-25T11:59:59Z")[0], "stale")

    def test_timezone_offsets(self):
        # 17:00 IST on the 25th is 11:30 UTC: 24.5h old.
        self.assertEqual(self.c("2026-10-25T17:00:00+05:30")[0], "stale")
        # 08:00 EDT on the 25th is 12:00 UTC: exactly 24h.
        fresh, normalized, _ = self.c("2026-10-25T08:00:00-04:00")
        self.assertEqual((fresh, normalized), ("confirmed_fresh", "2026-10-25T12:00:00Z"))

    def test_epoch_ms(self):
        ms = int(datetime(2026, 10, 26, 1, tzinfo=timezone.utc).timestamp() * 1000)
        self.assertEqual(self.c(ms), ("confirmed_fresh", "2026-10-26T01:00:00Z", "exact"))

    def test_future_is_invalid(self):
        self.assertEqual(self.c("2026-10-27T00:00:00Z")[0], "invalid_future")

    def test_date_only_never_confirmed(self):
        self.assertEqual(self.c("2026-10-26")[0], "uncertain")
        self.assertEqual(self.c("2026-10-25")[0], "uncertain")
        self.assertEqual(self.c("2026-10-20")[0], "stale")

    def test_relative_and_missing(self):
        self.assertEqual(self.c("1 day ago")[0], "uncertain")
        self.assertEqual(self.c("3 hours ago"), ("uncertain", None, "relative"))
        self.assertEqual(self.c("5 days ago")[0], "stale")
        for raw in (None, "", "None", "garbage"):
            self.assertEqual(self.c(raw)[0], "date_unverified")

    def test_naive_datetime_uncertain(self):
        self.assertEqual(self.c("2026-10-26T05:00:00")[0::2], ("uncertain", "no_timezone"))


class Scoring(unittest.TestCase):
    def test_strong_match_is_high(self):
        j = job()
        self.assertEqual(j["relevanceCategory"], "high_match", j["scoreBreakdown"])
        self.assertTrue(j["matchReasons"])

    def test_keyword_in_unrelated_title_excluded(self):
        self.assertEqual(job(jobTitle="Sales Manager (React products)")["relevanceCategory"], "excluded")
        self.assertEqual(job(jobTitle="Accounts Payable Executive")["relevanceCategory"], "excluded")

    def test_seniority_and_internship_excluded(self):
        self.assertEqual(job(jobTitle="Principal Software Engineer")["relevanceCategory"], "excluded")
        self.assertEqual(job(jobTitle="Software Engineer Intern")["relevanceCategory"], "excluded")
        self.assertIn("requires 8+ years",
                      job(description="Must have 8+ years of Node.js and React.")["exclusionReasons"])

    def test_location_rules(self):
        self.assertIn("outside India", job(location="Berlin, Germany")["exclusionReasons"])
        self.assertIn("remote but India eligibility not explicit",
                      job(location="Remote", description="React Node")["exclusionReasons"])
        self.assertEqual(job(location="Remote - India", workMode="remote")["scoreBreakdown"]["location"], 15)
        # Boilerplate naming India must not qualify a role located elsewhere.
        self.assertIn("remote but India eligibility not explicit",
                      job(location="US", workMode="remote", description="We hire in India and US.")["exclusionReasons"])

    def test_foreign_stack_capped(self):
        j = job(jobTitle="Software Engineer", description="Golang, Python and C# services; Kubernetes. " * 10)
        self.assertLessEqual(j["scoreBreakdown"]["skills"], 5)
        self.assertEqual(job(jobTitle="Full Stack Engineer (.NET, React)")["scoreBreakdown"]["title"], 15)

    def test_first_experience_range_wins(self):
        self.assertEqual(jd.parse_years("4+ to 8 years overall; 1 year of Docker"), 4)

    def test_thresholds_configurable(self):
        cfg = dict(CFG, thresholds={"high": 101, "medium": 0, "minimumScore": 0})
        self.assertEqual(jd.score_job(job(), cfg)["relevanceCategory"], "medium_match")


class Dedup(unittest.TestCase):
    def test_cross_platform_exact_match_merged_with_sources(self):
        a = job()
        b = job(platform="lever", sourceJobId="x9", canonicalJobUrl="https://jobs.lever.co/acme/x9")
        out, dups = jd.deduplicate([a, b])
        self.assertEqual((len(out), dups), (1, 1))
        self.assertEqual({s["platform"] for s in out[0]["sources"]}, {"greenhouse", "lever"})

    def test_same_platform_distinct_ids_not_merged(self):
        out, dups = jd.deduplicate([job(), job(sourceJobId="2", canonicalJobUrl="https://example.test/2")])
        self.assertEqual((len(out), dups), (2, 0))

    def test_different_location_flagged_not_merged(self):
        a = job()
        b = job(platform="ashby", sourceJobId="z", location="Pune, India", canonicalJobUrl="https://a.test/z")
        out, dups = jd.deduplicate([a, b])
        self.assertEqual((len(out), dups), (2, 0))
        self.assertEqual(out[0]["possibleDuplicateOf"], [b["id"]])

    def test_rerun_same_id_is_idempotent(self):
        out, dups = jd.deduplicate([job(), job()])
        self.assertEqual((len(out), dups), (1, 1))


class Malformed(unittest.TestCase):
    def test_missing_fields_reported(self):
        self.assertEqual(jd.validate(jd.make_job("lever", jobTitle="X")), ["companyName", "canonicalJobUrl"])

    def test_zoho_parser_tolerates_junk(self):
        page = "https://t.zohorecruit.in/jobs/Careers"
        body = ('<input type="hidden" value="[{not json}]">'
                '<input type="hidden" value="[{"a":1}]">'
                '<input type="hidden" value="[{"Posting_Title":"React Developer","id":"7","City":"Kolkata",'
                '"Country":"India","Publish":true},{"Posting_Title":"Hidden","id":"8","Publish":false}]">')
        jobs = jd.parse_zoho(body, page)
        self.assertEqual([j["jobTitle"] for j in jobs], ["React Developer"])
        self.assertEqual(jobs[0]["canonicalJobUrl"], page + "/7")
        self.assertEqual(jd.finalize(jobs[0], NOW, CFG)["freshness"], "date_unverified")

    def test_sort_order(self):
        fresh = job(sourceJobId="a", canonicalJobUrl="https://e.test/a", postedAtRaw="2026-10-26T10:00:00Z")
        unv = job(sourceJobId="b", canonicalJobUrl="https://e.test/b")
        self.assertEqual(jd.sort_jobs([unv, fresh])[0]["id"], fresh["id"])


if __name__ == "__main__":
    unittest.main()
