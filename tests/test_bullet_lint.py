"""Resume bullet formula lint: action + what + measurable result + how."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import bullet_lint


class CheckBulletTest(unittest.TestCase):
    def test_full_formula_passes(self):
        text = "Reduced authorization checks from 80 ms to under 1 ms by caching role lookups in Redis."
        self.assertEqual(bullet_lint.check_bullet(text), [])

    def test_vague_bullet_flags_every_part(self):
        self.assertEqual(
            bullet_lint.check_bullet("Worked on reports and performance."),
            ["no-number", "no-how"],
        )
        self.assertIn("no-action", bullet_lint.check_bullet("Responsible for 5 APIs."))

    def test_latex_is_stripped(self):
        text = bullet_lint.plain_text(r"Cut latency \textbf{60\%} using Redis")
        self.assertEqual(text, "Cut latency 60% using Redis")


class LintFileTest(unittest.TestCase):
    def test_skill_labels_skipped_and_bullets_flagged(self):
        cv = "\n".join([
            r"\item \textbf{Front end}: ReactJS, TypeScript",
            r"\item Built REST APIs for 5 products using Node.js",
            r"\item Team support",
        ])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cv.tex"
            path.write_text(cv, encoding="utf-8")
            rows = list(bullet_lint.lint(path))
            self.assertEqual([r[0] for r in rows], [2, 3])
            self.assertEqual(rows[0][2], [])
            self.assertEqual(rows[1][2], ["no-action", "no-number", "no-how"])
            self.assertEqual(bullet_lint.main([str(path)]), 1)

    def test_only_experience_and_project_sections_checked(self):
        cv = "\n".join([
            r"\section{Experience}",
            r"\item Built REST APIs for 5 products using Node.js",
            r"\section{Languages}",
            r"\item English and Hindi.",
        ])
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "cv.tex"
            path.write_text(cv, encoding="utf-8")
            self.assertEqual([r[0] for r in bullet_lint.lint(path)], [2])

    def test_missing_file_returns_2(self):
        self.assertEqual(bullet_lint.main(["/nonexistent/cv.tex"]), 2)


if __name__ == "__main__":
    unittest.main()
