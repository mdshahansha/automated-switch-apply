"""Tests for tools/experience_fit.py - candidate-advocacy experience handling.

The scraper used to drop every posting asking 6+ years and to score any years
gap toward zero, so strongly aligned stretch roles never reached the user.
These pin the rule: a years mismatch is a factor, never a verdict on its own,
and the candidate's own years always come from verified employment dates.
"""
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from experience_fit import assess, parse_requirement, verified_total_years, years_answer  # noqa: E402

TODAY = date(2026, 11, 19)
STRONG_SKILLS = ["React", "Node", "TypeScript", "Java", "Spring", "Docker"]


class ScenarioA_FewerYearsStrongAlignment(unittest.TestCase):
    def test_stays_eligible_for_evaluation(self):
        desc = "We need 5+ years building React and Node.js services with TypeScript."
        r = assess(desc, "Senior Full Stack Engineer", STRONG_SKILLS, TODAY)
        self.assertNotEqual(r["decision"], "reject")
        self.assertEqual(r["decision"], "stretch")
        self.assertGreater(r["years_gap"], 0)


class ScenarioB_EightPlusYearsStronglyAligned(unittest.TestCase):
    def test_not_rejected_on_years_alone(self):
        desc = "Minimum 8+ years of experience required in Java, Spring Boot, React and microservices."
        r = assess(desc, "Java Full Stack Developer", STRONG_SKILLS, TODAY)
        self.assertNotEqual(r["decision"], "reject")
        self.assertEqual(r["requirement"]["strength"], "mandatory")
        # Years lower the score but a strong match keeps a floor.
        self.assertGreaterEqual(r["experience_score"], 12)

    def test_ten_plus_years_still_evaluated(self):
        r = assess("10+ years experience with React and Node", "Senior Software Engineer",
                   STRONG_SKILLS, TODAY)
        self.assertEqual(r["decision"], "stretch")

    def test_preferred_years_penalised_less_than_mandatory(self):
        must = assess("Must have 7 years of experience.", "Backend Engineer", STRONG_SKILLS, TODAY)
        pref = assess("7 years of experience preferred.", "Backend Engineer", STRONG_SKILLS, TODAY)
        self.assertEqual(pref["requirement"]["strength"], "preferred")
        self.assertGreaterEqual(pref["experience_score"], must["experience_score"])


class ScenarioC_YearsGapAndPoorSkills(unittest.TestCase):
    def test_rejected_on_overall_mismatch(self):
        desc = "8+ years in SAP ABAP and payroll consulting required."
        r = assess(desc, "SAP Payroll Consultant", [], TODAY)
        self.assertEqual(r["decision"], "reject")
        self.assertTrue(any("overall mismatch" in reason for reason in r["reasons"]))

    def test_relevant_title_but_zero_skills_with_gap_rejected(self):
        r = assess("8+ years experience required.", "Software Engineer", [], TODAY)
        self.assertEqual(r["decision"], "reject")


class ScenarioF_VerifiedYearsOnly(unittest.TestCase):
    def test_total_years_from_verified_dates(self):
        # CodingNinjas Jun 2023-Apr 2025 (23 months) + Osbee Jun 2025-Nov 2026 (18 months) = 41 months.
        self.assertEqual(verified_total_years(TODAY), 3.4)

    def test_answer_not_inflated_to_posting_requirement(self):
        assess("Minimum 8+ years required", "Software Engineer", STRONG_SKILLS, TODAY)
        self.assertEqual(years_answer(TODAY), "3.4")

    def test_may_2025_gap_not_counted(self):
        self.assertLess(verified_total_years(date(2025, 6, 30)), 2.0 + 0.2)


class RequirementParsing(unittest.TestCase):
    def test_range_uses_lower_bound(self):
        self.assertEqual(parse_requirement("3-5 years of experience")["min_years"], 3)

    def test_no_years_stated(self):
        r = parse_requirement("Build React apps with our team.")
        self.assertIsNone(r["min_years"])
        self.assertEqual(r["strength"], "unclear")

    def test_meeting_requirement_is_eligible(self):
        r = assess("2+ years of React experience", "React Developer", STRONG_SKILLS, TODAY)
        self.assertEqual(r["decision"], "eligible")
        self.assertEqual(r["experience_score"], 25)


class ScraperUsesAdvocacy(unittest.TestCase):
    """tools/scrape_24h.py must route years through experience_fit, not drop on them."""

    def test_score_keeps_eight_plus_strong_match(self):
        import scrape_24h  # noqa: PLC0415
        desc = ("Minimum 8+ years. React, Node.js, Express, TypeScript, MongoDB, Java, Spring Boot, "
                "Docker, AWS, REST APIs. Remote.")
        total, yrs, _mode, hits, _sal, fit = scrape_24h.score(desc, "Senior Full Stack Engineer", "India")
        self.assertEqual(yrs, 8)
        self.assertNotEqual(fit["decision"], "reject")
        self.assertGreaterEqual(total, 70)  # still clears the default --min-score


if __name__ == "__main__":
    unittest.main()
