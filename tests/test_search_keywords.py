"""Tests for tools/search_keywords.py and tools/search_keywords.json.

The keyword list used to be a hard-coded QUERIES list inside the scraper. It is
now a card file: every keyword independently searchable, grouped by category,
individually enabled/disabled, with jobs found by several cards merged once.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from search_keywords import (  # noqa: E402
    KeywordConfigError, enabled_cards, get_card, load_cards, merge_discoveries)

EXPECTED = {
    "general": ["Software Engineer", "Senior Software Engineer", "Software Engineer II", "SDE 1", "SDE 2",
                "Software Developer", "Senior Software Developer", "Application Developer",
                "Product Engineer", "Member of Technical Staff"],
    "full-stack": ["Full Stack Engineer", "Full Stack Developer", "Senior Full Stack Developer",
                   "Java Full Stack Developer", "MERN Stack Developer", "MEAN Stack Developer"],
    "backend": ["Backend Engineer", "Backend Developer", "Senior Backend Engineer", "Node.js Developer",
                "NestJS Developer", "REST API Developer"],
    "java": ["Java Developer", "Senior Java Developer", "Java Spring Boot Developer",
             "Java Microservices Developer", "Java Backend Developer", "Spring Boot Engineer", "J2EE Developer"],
    "frontend": ["Frontend Engineer", "Frontend Developer", "UI Developer", "React Developer",
                 "React.js Developer", "Senior React Developer", "Next.js Developer", "TypeScript Developer",
                 "JavaScript Developer", "Angular Developer"],
    "mobile": ["React Native Developer", "React Native Engineer", "Mobile App Developer"],
    "skill-combos": ["React Node.js", "React Spring Boot", "Java React", "Node.js AWS",
                     "Spring Boot Microservices", "Microservices Kafka", "Docker Kubernetes Java", "Go Developer"],
}


class ScenarioE_AllFiftyKeywords(unittest.TestCase):
    def setUp(self):
        self.cards = load_cards()

    def test_exactly_fifty_cards(self):
        self.assertEqual(len(self.cards), 50)

    def test_each_keyword_in_its_category(self):
        for category, keywords in EXPECTED.items():
            got = [c["keyword"] for c in self.cards if c["category"] == category]
            self.assertEqual(got, keywords, category)

    def test_each_card_independently_searchable(self):
        for c in self.cards:
            self.assertEqual(get_card(self.cards, c["id"])["keyword"], c["keyword"])
            self.assertTrue(c["keyword"].strip())

    def test_go_developer_present_but_paused_by_exclusion_list(self):
        go = get_card(self.cards, "go-developer")
        self.assertFalse(go["enabled"])
        self.assertIn("excluded", go["disabled_reason"])
        self.assertNotIn(go, enabled_cards(self.cards))

    def test_enabled_and_category_selection(self):
        self.assertEqual(len(enabled_cards(self.cards)), 49)
        self.assertEqual(len(enabled_cards(self.cards, "mobile")), 3)


class ScenarioD_DuplicateJobAcrossKeywords(unittest.TestCase):
    def test_deduplicated_with_metadata(self):
        a = {"id": "react-nodejs", "keyword": "React Node.js"}
        b = {"id": "full-stack-developer", "keyword": "Full Stack Developer"}
        job = {"id": "123", "title": "Full Stack Developer", "company": "Acme"}
        other = {"id": "456", "title": "Backend Engineer", "company": "Beta"}
        merged = merge_discoveries([(a, [job]), (b, [dict(job), other]), (a, [dict(job)])])
        self.assertEqual(len(merged), 2)
        m = next(j for j in merged if j["id"] == "123")
        self.assertEqual(m["discovered_by"], ["react-nodejs", "full-stack-developer"])
        self.assertEqual(m["discovered_keywords"], ["React Node.js", "Full Stack Developer"])
        self.assertEqual(m["title"], "Full Stack Developer")

    def test_input_jobs_not_mutated(self):
        job = {"id": "1"}
        merge_discoveries([({"id": "x", "keyword": "X"}, [job])])
        self.assertNotIn("discovered_by", job)


class ConfigValidation(unittest.TestCase):
    def _load(self, doc):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "k.json"
            p.write_text(json.dumps(doc), encoding="utf-8")
            return load_cards(p)

    def test_duplicate_keyword_rejected(self):
        doc = {"categories": [{"id": "a", "label": "A", "cards": [
            {"id": "x", "keyword": "React Developer", "enabled": True},
            {"id": "y", "keyword": "react developer", "enabled": True}]}]}
        with self.assertRaises(KeywordConfigError):
            self._load(doc)

    def test_non_boolean_enabled_rejected(self):
        doc = {"categories": [{"id": "a", "label": "A", "cards": [
            {"id": "x", "keyword": "React Developer", "enabled": "yes"}]}]}
        with self.assertRaises(KeywordConfigError):
            self._load(doc)


class ScraperUsesCards(unittest.TestCase):
    def test_select_cards_defaults_to_enabled(self):
        import scrape_24h  # noqa: PLC0415
        self.assertEqual(len(scrape_24h.select_cards([], None)), 49)
        self.assertEqual([c["id"] for c in scrape_24h.select_cards(["go-developer"], None)], ["go-developer"])


if __name__ == "__main__":
    unittest.main()
