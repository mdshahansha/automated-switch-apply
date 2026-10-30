"""Custom weights flow through the real rank CLI without changing legacy scores."""

import json
import subprocess
import sys

from tests.test_rank_state import RankStateCase, TOOL, entry


class CustomRankWeights(RankStateCase):
    def results(self, result):
        path = self.tmp / "scores.json"
        path.write_text(json.dumps([{"key": "a", "status": "scored", **result}]), encoding="utf-8")
        return str(path)

    def weights(self, value):
        path = self.tmp / "weights.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        return str(path)

    def apply(self, weights, scores, **extra):
        self.write_state({"a": entry()})
        return self.run_tool(
            "apply", "--results", self.results({"scores": scores, **extra}),
            "--weights", self.weights(weights),
        )

    def test_custom_subset_replaces_defaults_and_keeps_exact_rounding(self):
        output = self.apply({"technical": 0.5, "experience": 0.5},
                            {"technical": 59, "experience": 60})
        row = output["ranked"][0]
        self.assertEqual((row["score"], row["verdict"]), (60, "Good Fit"))
        self.assertEqual(row["weights"], {"technical": 0.5, "experience": 0.5})
        self.assertNotIn("behavioral", self.read_state()["a"]["rank_scores"])

    def test_new_optional_dimensions_can_all_contribute(self):
        weights = {"salary": 0.25, "role": 0.25, "freshness": 0.25, "employment": 0.25}
        notes = {"salary": "Disclosed range meets the configured target.",
                 "role": "The posting asks for the configured engineering work.",
                 "freshness": "Verified posted_date is six days old.",
                 "employment": "The stated employment type matches the configured preference."}
        output = self.apply(weights, {"salary": 80, "role": 90, "freshness": 100, "employment": 70},
                            score_notes=notes)
        row = output["ranked"][0]
        self.assertEqual(row["score"], 85)
        self.assertEqual(row["score_notes"], notes)
        stored = self.read_state()["a"]
        self.assertEqual(stored["rank_weights"], weights)
        self.assertEqual(stored["rank_score_notes"], notes)
        self.assertEqual(stored["rank_effective_weights"], weights)

    def test_unknown_optional_data_is_excluded_and_reported(self):
        output = self.apply({"technical": 0.6, "salary": 0.2, "employment": 0.2},
                            {"technical": 73, "salary": None},
                            score_notes={"technical": "Verified matching skills.",
                                         "salary": "No candidate numeric target is configured.",
                                         "employment": "Posting omits the employment type."})
        row = output["ranked"][0]
        self.assertEqual(row["score"], 73)
        self.assertEqual(row["effective_weights"], {"technical": 1.0})
        self.assertEqual(row["unavailable"], ["salary", "employment"])
        self.assertEqual(row["scores"], {"technical": 73, "salary": None, "employment": None})
        self.assertEqual(self.read_state()["a"]["rank_unavailable"], ["salary", "employment"])

    def test_renormalized_halfpoint_rounds_up_exactly(self):
        output = self.apply({"technical": 0.3, "experience": 0.3, "salary": 0.4},
                            {"technical": 29, "experience": 30, "salary": None})
        self.assertEqual(output["ranked"][0]["score"], 30)

    def test_optional_scores_are_not_used_without_configured_weight(self):
        self.write_state({"a": entry()})
        output = self.run_tool("apply", "--results", self.results({"scores": {
            "technical": 80, "experience": 60, "behavioral": 70, "career": 75, "salary": 0,
        }}))
        self.assertEqual(output["ranked"][0]["score"], 72)
        self.assertEqual(set(self.read_state()["a"]["rank_scores"]),
                         {"technical", "experience", "behavioral", "career"})

    def test_zero_weight_core_dimensions_do_not_require_scores(self):
        output = self.apply({"technical": 0, "role": 1}, {"role": 82})
        self.assertEqual(output["ranked"][0]["score"], 82)
        self.assertEqual(output["ranked"][0]["scores"], {"role": 82})

    def test_configured_positive_core_dimension_remains_required(self):
        self.write_state({"a": entry()})
        output = self.run_tool("apply", "--results", self.results({"scores": {"role": 90}}),
                               "--weights", self.weights({"technical": 0.5, "role": 0.5}), expect=1)
        self.assertIn("technical", output["errors"][0]["error"])
        self.assertEqual(self.read_state()["a"], entry())

    def test_no_available_positive_dimensions_is_an_error(self):
        self.write_state({"a": entry()})
        output = self.run_tool("apply", "--results", self.results({"scores": {"salary": None}}),
                               "--weights", self.weights({"salary": 1}), expect=1)
        self.assertIn("no scored dimensions", output["errors"][0]["error"])
        self.assertEqual(self.read_state()["a"], entry())

    def test_invalid_optional_values_never_become_unknown(self):
        for value in (True, -1, 101, "unknown", float("inf"), float("nan")):
            with self.subTest(value=value):
                self.write_state({"a": entry()})
                output = self.run_tool("apply", "--results", self.results({"scores": {"salary": value}}),
                                       "--weights", self.weights({"salary": 1}), expect=1)
                self.assertIn("salary", output["errors"][0]["error"])
                self.assertEqual(self.read_state()["a"], entry())

    def test_invalid_configs_stop_before_any_state_change(self):
        invalid = ({}, [], {"other": 1}, {"technical": True}, {"technical": -1},
                   {"technical": 0}, {"technical": 0.9}, {"technical": 1.1},
                   {"technical": "1"}, {"technical": float("nan")},
                   {"technical": float("inf")}, {"technical": 10 ** 400})
        for weights in invalid:
            with self.subTest(weights=weights):
                self.write_state({"a": entry()})
                before = self.state.read_bytes()
                proc = subprocess.run([
                    sys.executable, str(TOOL), "apply", "--state", str(self.state),
                    "--results", self.results({"scores": {"technical": 80}}),
                    "--weights", self.weights(weights),
                ], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(proc.returncode, 1, proc.stderr)
                self.assertIn("weights", proc.stderr)
                self.assertNotIn("Traceback", proc.stderr)
                self.assertEqual(self.state.read_bytes(), before)

    def test_missing_or_malformed_config_is_an_error(self):
        path = self.tmp / "weights.json"
        for content in (None, "{bad json", '{"technical": 0.5, "technical": 1}'):
            with self.subTest(content=content):
                if content is not None:
                    path.write_text(content, encoding="utf-8")
                self.write_state({"a": entry()})
                proc = subprocess.run([
                    sys.executable, str(TOOL), "apply", "--state", str(self.state),
                    "--results", self.results({"scores": {"technical": 80}}), "--weights", str(path),
                ], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(proc.returncode, 1)
                self.assertIn("cannot load weights", proc.stderr)
                self.assertEqual(self.read_state()["a"], entry())

    def test_hard_constraint_veto_cannot_be_disabled_by_weights(self):
        output = self.apply({"role": 1}, {"role": 100}, preference_gate="FAIL",
                            preference_note="Posting requires foreign work authorization; profile declares India only.")
        self.assertEqual(output["ranked"], [])
        self.assertEqual(output["vetoed"][0]["preference_gate"], "FAIL")
        self.assertIn("work authorization", self.read_state()["a"]["preference_note"])

    def test_preference_flag_is_visible_and_does_not_veto(self):
        output = self.apply({"role": 1}, {"role": 100}, preference_gate="FLAG",
                            preference_note="Posting says remote but does not confirm India hiring.")
        self.assertEqual(output["vetoed"], [])
        self.assertEqual(output["ranked"][0]["preference_gate"], "FLAG")

    def test_invalid_or_unexplained_preference_gate_leaves_entry_untouched(self):
        for gate, note in (("fail", "a reason"), ("FAIL", None), ("FLAG", ""), (False, "a reason"),
                           ([], "a reason"), (None, "a reason")):
            with self.subTest(gate=gate, note=note):
                self.write_state({"a": entry()})
                output = self.run_tool("apply", "--results", self.results({
                    "scores": {"role": 100}, "preference_gate": gate, "preference_note": note,
                }), "--weights", self.weights({"role": 1}), expect=1)
                self.assertEqual(len(output["errors"]), 1)
                self.assertEqual(self.read_state()["a"], entry())

    def test_rescore_replaces_evidence_and_clears_resolved_gate_note(self):
        self.apply({"role": 1}, {"role": 100}, preference_gate="FLAG",
                   preference_note="India eligibility unverified.", score_notes={"role": "Old evidence."})
        output = self.run_tool("apply", "--results", self.results({"scores": {"technical": 80},
                               "score_notes": {"technical": "New posting evidence."}}),
                               "--weights", self.weights({"technical": 1}))
        stored = self.read_state()["a"]
        self.assertEqual(stored["rank_score_notes"], {"technical": "New posting evidence."})
        self.assertNotIn("preference_note", stored)
        self.assertEqual(output["ranked"][0]["preference_gate"], "PASS")

    def test_invalid_explanation_is_not_a_partial_write(self):
        for notes in ([], {"invented": "Not a supported criterion."}, {"role": 90},
                      {"role": ""}, {"role": "x" * 2001}):
            with self.subTest(notes=notes):
                self.write_state({"a": entry()})
                output = self.run_tool("apply", "--results", self.results({
                    "scores": {"role": 90}, "score_notes": notes,
                }), "--weights", self.weights({"role": 1}), expect=1)
                self.assertEqual(len(output["errors"]), 1)
                self.assertEqual(self.read_state()["a"], entry())
