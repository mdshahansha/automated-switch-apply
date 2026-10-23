"""The shared runner dispatches permitted CLIs and never invents access."""

import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import portal_search as portal  # noqa: E402

NOW = "2026-10-23T12:00:00Z"
LATER = "2026-10-23T13:00:00Z"


class PortalSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.registry = self.root / "registry.json"
        self.registry.write_text(portal.REGISTRY.read_text(encoding="utf-8"), encoding="utf-8")
        self.state = self.root / "state.json"
        self.tracker = self.root / "tracker.csv"
        self.calls = []
        rows = json.loads(self.registry.read_text(encoding="utf-8"))["portals"]
        for row in rows:
            skill = self.root / ".agents" / "skills" / row["id"]
            skill.mkdir(parents=True)
            enabled = row["mode"] in portal.PUBLIC_MODES or row["id"] == "linkedin-search"
            (skill / "SKILL.md").write_text(f"---\nname: {row['id']}\nenabled: {str(enabled).lower()}\n---\n", encoding="utf-8")
            if row["mode"] in portal.PUBLIC_MODES or row["id"] == "linkedin-search":
                (skill / "cli" / "src").mkdir(parents=True)
                (skill / "cli" / "src" / "cli.ts").write_text("// fixture", encoding="utf-8")

    def args(self, selectors=None, **overrides):
        options = dict(selectors=selectors or [], state=self.state, tracker=self.tracker, query="React", location=None,
                       remote=None, experience=None, jobage=None, page=1, limit=20, dry_run=False)
        options.update(overrides)
        return SimpleNamespace(**options)

    def run_search(self, args=None, response=None, now=NOW, which=lambda _: "bun"):
        def run(argv, **kwargs):
            self.calls.append((argv, kwargs))
            return response or SimpleNamespace(returncode=0, stdout=json.dumps({"results": [self.job()], "meta": {"count": 1}}), stderr="")
        return portal.execute_search(args or self.args(["RemoteOK"]), root=self.root, registry_path=self.registry,
                                     run=run, which=which, now=now)

    def job(self, **updates):
        return {"id": "100001", "title": "React Engineer", "company": "Example", "location": "India",
                "url": "https://remoteok.com/remote-jobs/remote-react-engineer-100001",
                "date": "2026-10-22T12:00:00Z", "description": "Build React tools.", **updates}

    def test_all_requested_and_legacy_portals_are_registered(self):
        discovered = portal.discover(self.root, self.registry)
        self.assertEqual(len(discovered), 21)
        self.assertEqual({p["id"] for p in discovered if p["automatic"]}, portal.ADAPTERS)
        self.assertFalse(next(p for p in discovered if p["id"] == "linkedin-search")["automatic"])

    def test_aliases_and_groups_union_without_duplicate_execution(self):
        all_portals = portal.discover(self.root, self.registry)
        selected = portal.select_portals(all_portals, ["India", "remote", "RemoteOK", "WWR", "Y Combinator"])
        self.assertEqual(len(selected), 17)
        self.assertEqual(len({p["id"] for p in selected}), len(selected))
        self.assertEqual({p["id"] for p in portal.select_portals(all_portals, [])}, portal.ADAPTERS)
        with self.assertRaisesRegex(ValueError, "unknown portal"):
            portal.select_portals(all_portals, ["invented"])

    def test_additional_cli_is_discovered_but_not_automatically_trusted(self):
        skill = self.root / ".agents" / "skills" / "future-search"
        (skill / "cli" / "src").mkdir(parents=True)
        (skill / "SKILL.md").write_text("---\nname: future-search\nenabled: true\n---\n", encoding="utf-8")
        (skill / "cli" / "src" / "cli.ts").write_text("// unknown access", encoding="utf-8")
        result = self.run_search(self.args(["future"]))
        self.assertEqual(result["portals"][0]["status"], "unverified")
        self.assertEqual(self.calls, [])

    def test_manual_portals_and_ambiguous_aijobs_make_no_subprocess_calls(self):
        result = self.run_search(self.args(["Hirist", "Instahyre", "Cutshort", "AIJobs", "LinkedIn"]))
        self.assertEqual(self.calls, [])
        self.assertTrue(all(p["status"] == "manual" for p in result["portals"]))
        aijobs = next(p for p in result["portals"] if p["id"] == "aijobs-search")
        self.assertIsNone(aijobs["url"])
        self.assertIn("exact AIJobs", aijobs["reason"])
        self.assertEqual(aijobs["requested_filters"]["query"], "React")

    def test_malformed_registry_and_duplicate_ids_fail_before_execution(self):
        self.registry.write_text('{"portals":[{"id":"../evil-search"}]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "invalid portal"):
            self.run_search()
        self.registry.write_text('{"portals":[{"id":"x-search"},{"id":"x-search"}]}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate registry"):
            self.run_search()
        self.assertEqual(self.calls, [])

    def test_disabled_or_missing_cli_never_runs(self):
        skill = self.root / ".agents" / "skills" / "remoteok-search"
        (skill / "SKILL.md").write_text("---\nenabled: false\n---\n", encoding="utf-8")
        result = self.run_search()
        self.assertEqual(result["portals"][0]["status"], "disabled")
        self.assertEqual(self.calls, [])

    def test_unsupported_filter_is_reported_and_not_silently_discarded(self):
        result = self.run_search(self.args(["RemoteOK"], experience="3"))
        report = result["portals"][0]
        self.assertEqual(report["status"], "unsupported_filters")
        self.assertEqual(report["unsupported_filters"][0]["filter"], "experience")
        self.assertEqual(self.calls, [])
        result = self.run_search(self.args(["Himalayas"], location="Bengaluru"))
        self.assertEqual(result["portals"][0]["unsupported_filters"][0]["filter"], "location")

    def test_remote_only_sources_honor_remote_but_reject_onsite(self):
        result = self.run_search(self.args(["RemoteOK"], remote="remote", dry_run=True))
        self.assertEqual(result["portals"][0]["status"], "operational")
        self.assertNotIn("--remote", self.calls[0][0])
        self.calls.clear()
        result = self.run_search(self.args(["RemoteOK"], remote="onsite"))
        self.assertEqual(result["portals"][0]["status"], "unsupported_filters")
        self.assertEqual(self.calls, [])

    def test_country_seniority_and_feed_description_flag_translation(self):
        discovered = {p["id"]: p for p in portal.discover(self.root, self.registry)}
        flags, bad = portal.build_arguments(discovered["himalayas-search"], self.args(location="India", experience="Senior", remote="remote"))
        self.assertFalse(bad); self.assertIn("IN", flags); self.assertIn("Senior", flags)
        flags, bad = portal.build_arguments(discovered["freehire-search"], self.args(location="Pune", experience="middle", remote="hybrid"))
        self.assertFalse(bad); self.assertIn("--city", flags); self.assertIn("hybrid", flags)
        flags, bad = portal.build_arguments(discovered["weworkremotely-search"], self.args())
        self.assertIn("--include-description", flags)

    def test_subprocess_is_fixed_argv_no_shell_bounded_and_does_not_execute_query(self):
        query = 'React; $(Get-Content secret) "literal"'
        result = self.run_search(self.args(["RemoteOK"], query=query))
        argv, kwargs = self.calls[0]
        self.assertEqual(argv[:2], ["bun", "run"])
        self.assertEqual(argv[argv.index("--query") + 1], query)
        self.assertEqual(kwargs["shell"], False)
        self.assertEqual(kwargs["timeout"], 90)
        self.assertEqual(kwargs["stdin"], subprocess.DEVNULL)
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(result["portals"][0]["status"], "operational")

    def test_missing_bun_and_nonzero_cli_are_explicit_failures(self):
        result = self.run_search(which=lambda _: None)
        self.assertEqual(result["portals"][0]["status"], "unavailable")
        self.assertEqual(self.calls, [])
        result = self.run_search(response=SimpleNamespace(returncode=1, stdout="", stderr='{"error":"HTTP 403"}'))
        self.assertEqual(result["portals"][0]["status"], "blocked")
        self.assertEqual(result["results"], [])

    def test_timeout_and_malformed_response_do_not_become_empty_success(self):
        def timeout(argv, **kwargs):
            raise subprocess.TimeoutExpired(argv, 90)
        result = portal.execute_search(self.args(["RemoteOK"]), root=self.root, registry_path=self.registry,
                                       run=timeout, which=lambda _: "bun", now=NOW)
        self.assertEqual(result["portals"][0]["status"], "failed")
        for stdout in ("not json", "[]", '{"jobs":[]}'):
            result = self.run_search(response=SimpleNamespace(returncode=0, stdout=stdout, stderr=""))
            self.assertEqual(result["portals"][0]["status"], "failed")

    def test_malformed_rows_are_reported_and_all_invalid_rows_fail_portal(self):
        payload = {"results": [self.job(), {"title": "Missing URL"}]}
        result = self.run_search(response=SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr=""))
        self.assertEqual(result["portals"][0]["status"], "operational")
        self.assertEqual(len(result["summary"]["invalid"]), 1)
        result = self.run_search(response=SimpleNamespace(returncode=0, stdout='{"results":[null]}', stderr=""))
        self.assertEqual(result["portals"][0]["status"], "failed")

    def test_repeat_observation_updates_last_seen_and_preserves_last_success_on_failure(self):
        first = self.run_search()
        self.assertEqual(len(first["summary"]["added"]), 1)
        second = self.run_search(now=LATER)
        self.assertEqual(second["summary"]["duplicates_removed"], 1)
        state = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(next(iter(state["seen"].values()))["last_seen"], LATER)
        failed = self.run_search(now="2026-10-23T14:00:00Z", response=SimpleNamespace(returncode=1, stdout="", stderr="down"))
        self.assertEqual(failed["portals"][0]["last_success"], LATER)
        self.assertEqual(json.loads(self.state.read_text(encoding="utf-8"))["portal_status"]["remoteok-search"]["last_success"], LATER)

    def test_expired_jobs_and_last_updated_date_are_normalized_without_false_posting_dates(self):
        expired = self.job(expiresAt="2026-10-22T00:00:00Z")
        result = self.run_search(response=SimpleNamespace(returncode=0, stdout=json.dumps({"results": [expired]}), stderr=""))
        self.assertEqual(result["results"][0]["status"], "expired")
        result = self.run_search(self.args(["Himalayas"], dry_run=True))
        self.assertIsNone(result["results"][0]["posting_date"])
        self.assertEqual(result["results"][0]["date_meaning"], "last_updated")

    def test_dry_run_keeps_search_evidence_in_output_without_writing(self):
        result = self.run_search(self.args(["RemoteOK"], dry_run=True))
        self.assertFalse(self.state.exists())
        self.assertEqual(result["portals"][0]["last_success"], NOW)
        self.assertEqual(len(result["results"]), 1)

    def test_remoteok_feed_legal_attribution_survives_normalization_and_persistence(self):
        attribution = {"name": "Remote OK", "url": "https://remoteok.com", "notice": "Credit Remote OK"}
        response = SimpleNamespace(returncode=0, stdout=json.dumps({"results": [self.job()], "meta": {"attribution": attribution}}), stderr="")
        result = self.run_search(response=response)
        self.assertEqual(result["results"][0]["source_metadata"]["attribution"], attribution)
        saved = json.loads(self.state.read_text(encoding="utf-8"))
        self.assertEqual(next(iter(saved["seen"].values()))["source_metadata"]["attribution"], attribution)

    def test_manual_import_validates_whole_file_before_writing_and_does_not_fetch(self):
        data = self.root / "import.json"
        data.write_text(json.dumps([self.job()]), encoding="utf-8")
        args = SimpleNamespace(portal="Hirist", file=data, state=self.state, tracker=self.tracker, dry_run=False)
        result = portal.execute_import(args, root=self.root, registry_path=self.registry, now=NOW)
        self.assertEqual(result["results"][0]["source"], "manual")
        before = self.state.read_bytes()
        data.write_text(json.dumps([self.job(), {"title": "missing url"}]), encoding="utf-8")
        with self.assertRaises(ValueError):
            portal.execute_import(args, root=self.root, registry_path=self.registry, now=LATER)
        self.assertEqual(self.state.read_bytes(), before)
        args.portal = "India"
        with self.assertRaisesRegex(ValueError, "exactly one"):
            portal.execute_import(args, root=self.root, registry_path=self.registry, now=LATER)

    def test_status_reads_saved_evidence_and_never_turns_configured_into_operational(self):
        args = self.args(["all"])
        empty = portal.execute_status(args, root=self.root, registry_path=self.registry)
        self.assertEqual(empty["summary"]["configured"], 21)
        self.assertEqual(empty["summary"]["operational"], 0)
        self.run_search()
        status = portal.execute_status(args, root=self.root, registry_path=self.registry)
        self.assertEqual(status["summary"]["operational"], 1)
        self.assertEqual(status["summary"]["automatic"], 4)
        self.assertEqual(status["summary"]["jobs_discovered"], 1)
        self.assertIn("duplicates_removed", status["summary"])
        self.assertIn("shortlisted", status["portals"][0])

    def test_cli_parse_errors_are_stderr_json(self):
        for argv in (["search", "--limit", "21"], ["search", "--jobage", "0"], ["search", "--unknown"], ["missing"]):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                self.assertEqual(portal.main(argv), 1)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(json.loads(err.getvalue())["code"], "PORTAL_SEARCH_ERROR")


if __name__ == "__main__":
    unittest.main()
