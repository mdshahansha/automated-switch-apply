"""Submission audit: approval and checked evidence, without any submission IO."""

import copy
import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import application_record as records


PREPARED = "2026-10-23T08:00:00Z"
APPROVED = "2026-10-23T08:10:00Z"
SENT = "2026-10-23T08:20:00Z"
CHECKED = "2026-10-23T08:21:00Z"


class ApplicationRecordTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.cv = self.root / "Mohammad_Shahansha_Resume.pdf"
        self.letter = self.root / "letter.pdf"
        self.cv.write_bytes(b"CV fixture")
        self.letter.write_bytes(b"Cover letter fixture")
        self.job = {"title": "Full Stack Engineer", "company": "Example", "portal": "himalayas-search",
                    "url": "https://himalayas.app/companies/example/jobs/engineer",
                    "application_url": "https://careers.example.com/apply/123"}

    def prepared(self, state=None, **kwargs):
        return records.prepare(state or {}, self.job, self.cv, self.letter, now=PREPARED, **kwargs)

    def approved(self):
        return records.approve(self.prepared(), "user-message:123 approves reviewed CV and destination", now=APPROVED)

    def confirmed(self, state=None, **kwargs):
        values = {"submitted_at": SENT, "kind": "portal_receipt", "confirmation_text": "Your application was submitted. Receipt 123",
                  "source": "https://careers.example.com/application/123", "now": CHECKED}
        values.update(kwargs)
        return records.submitted(state or self.approved(), **values)

    def test_preparation_hashes_documents_and_does_not_approve_or_submit(self):
        state = self.prepared(status="manual_handoff")
        self.assertEqual(state["status"], "manual_handoff")
        self.assertFalse(state["application_submitted"])
        self.assertFalse(state["submission_verified"])
        self.assertNotIn("approval", state)
        self.assertEqual(state["documents"]["cv"], records.document(self.cv))
        self.assertEqual(state["platform"], self.job["portal"])
        self.assertEqual(state["official_destination"], self.job["application_url"])
        self.assertEqual(state["events"][0]["kind"], "prepared")

    def test_confirmation_requires_explicit_approval(self):
        with self.assertRaisesRegex(ValueError, "approval"):
            self.confirmed(self.prepared())

    def test_approval_requires_nonempty_human_reference_and_unblocked_state(self):
        with self.assertRaises(ValueError):
            records.approve(self.prepared(), " ", now=APPROVED)
        blocked = self.prepared(status="blocked", blocker="Candidate must finish login")
        with self.assertRaisesRegex(ValueError, "unblocked"):
            records.approve(blocked, "user:123", now=APPROVED)

    def test_confirmed_submission_keeps_actual_and_checked_times_and_exact_evidence(self):
        exact = "  Your application was submitted. Receipt #123\n"
        state = self.confirmed(confirmation_text=exact)
        self.assertEqual(state["status"], "applied")
        self.assertTrue(state["submission_verified"])
        self.assertTrue(state["application_submitted"])
        self.assertEqual(state["submitted_at"], SENT)
        self.assertEqual(state["checked_at"], CHECKED)
        self.assertEqual(state["submission_evidence"]["text"], exact)
        self.assertEqual([event["sequence"] for event in state["events"]], [1, 2, 3])

    def test_empty_unknown_and_upload_only_evidence_are_rejected(self):
        for changes in ({"confirmation_text": ""}, {"source": ""}, {"kind": "upload_complete"},
                        {"kind": []}, {"confirmation_text": "Upload complete"},
                        {"confirmation_text": "CV uploaded successfully"}, {"confirmation_text": "upload_complete"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.confirmed(**changes)

    def test_each_documented_confirmation_kind_is_supported(self):
        for kind in sorted(records.EVIDENCE_KINDS):
            with self.subTest(kind=kind):
                self.assertTrue(self.confirmed(kind=kind)["submission_verified"])

    def test_failed_pending_and_form_instructions_never_count_as_submission(self):
        failures = (
            "We could not submit your application. Please try again.",
            "Your application was not submitted.",
            "Submission failed. Please retry.",
            "You have not yet applied for this role.",
            "Application status: pending",
            "Application status: draft",
            "Your application is still in progress.",
            "Review and submit your application",
            "Click the Submit application button",
            "Submit application button",
            "Application submitted button",
            "Application submitted: false",
            "No application submitted",
            "Your application submitted unsuccessfully.",
            "Ready to apply",
            "Form complete and ready to submit",
            "Upload complete",
            "I will submit my application tomorrow.",
            "Application submitted? Please check.",
            "The message says application submitted but the submission failed.",
            "I have not applied. The receipt example says your application was submitted.",
            "आपका आवेदन जमा नहीं हुआ है।",
            "आवेदन लंबित है।",
            "Maine application submit nahi kiya hai.",
            "Mujhe abhi apply karna hai.",
        )
        for kind in sorted(records.EVIDENCE_KINDS):
            for wording in failures:
                state = self.approved()
                before = copy.deepcopy(state)
                with self.subTest(kind=kind, wording=wording), self.assertRaises(ValueError):
                    self.confirmed(state, kind=kind, confirmation_text=wording)
                self.assertEqual(state, before, "rejected evidence must not change state")

    def test_positive_checked_receipt_history_and_user_wording(self):
        confirmations = (
            ("portal_receipt", "Your application has been successfully submitted."),
            ("portal_receipt", "Thank you for applying!"),
            ("application_history", "Application status: applied"),
            ("application_history", "You have applied for this position."),
            ("employer_acknowledgement", "We have received your application."),
            ("user_confirmation", "I have submitted my application successfully."),
            ("user_confirmation", "I applied."),
            ("user_confirmation", "मैंने आवेदन जमा कर दिया है।"),
            ("user_confirmation", "Maine application submit kar diya hai."),
            ("portal_receipt", "आपका आवेदन प्राप्त हो गया है।"),
        )
        for kind, wording in confirmations:
            with self.subTest(kind=kind, wording=wording):
                state = self.confirmed(kind=kind, confirmation_text=wording)
                self.assertEqual(state["submission_evidence"]["text"], wording)
                self.assertTrue(state["submission_verified"])

    def test_unknown_wording_and_mismatched_first_person_source_kind_fail_closed(self):
        for kind, wording in (("portal_receipt", "Everything looks good now."),
                              ("employer_acknowledgement", "I applied."),
                              ("application_history", "Saved successfully."),
                              ("user_confirmation", "All working")):
            with self.subTest(kind=kind, wording=wording), self.assertRaises(ValueError):
                self.confirmed(kind=kind, confirmation_text=wording)

    def test_changed_attachment_after_approval_cannot_be_confirmed(self):
        state = self.approved()
        self.cv.write_bytes(b"Changed CV")
        with self.assertRaisesRegex(ValueError, "attachment changed"):
            self.confirmed(state)

    def test_changed_letter_and_missing_documents_also_reject_approval(self):
        state = self.prepared()
        self.letter.write_bytes(b"Changed letter")
        with self.assertRaises(ValueError):
            records.approve(state, "user:123", now=APPROVED)
        self.letter.unlink()
        with self.assertRaises(OSError):
            records.approve(state, "user:123", now=APPROVED)

    def test_changed_destination_or_job_invalidates_approval(self):
        for field, value in (("official_destination", "https://other.example.com/apply"),
                             ("job_url", "https://himalayas.app/another-job"),
                             ("title", "Senior Engineer"), ("platform", "other-board")):
            state = self.approved()
            state[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, "changed since approval"):
                self.confirmed(state)

    def test_reprepare_invalidates_approval_and_preserves_previous_events(self):
        before = self.approved()
        old_history = copy.deepcopy(before["events"])
        after = records.prepare(before, self.job, self.cv, self.letter, now=SENT)
        self.assertEqual(after["events"][:2], old_history)
        self.assertEqual(before["events"], old_history, "pure function must not mutate its input")
        self.assertNotIn("approval", after)
        self.assertEqual(after["events"][-1]["details"]["superseded_approval"], before["approval"])

    def test_ambiguous_attempt_blocks_reprepare_and_resumes_by_reconciliation(self):
        state = records.unverified(self.approved(), "Tab timed out after candidate pressed submit", now=SENT)
        self.assertEqual(state["status"], "submission_unverified")
        self.assertFalse(state["application_submitted"])
        with self.assertRaisesRegex(ValueError, "reconcile"):
            records.prepare(state, self.job, self.cv, now=CHECKED)
        confirmed = self.confirmed(state)
        self.assertEqual(confirmed["events"][-2]["kind"], "submission_unverified")
        self.assertEqual(confirmed["status"], "applied")

    def test_unapproved_uncertainty_is_rejected_without_changing_state(self):
        for state in (self.prepared(), self.prepared(status="blocked", blocker="Upload is blocked")):
            before = copy.deepcopy(state)
            with self.assertRaisesRegex(ValueError, "prior approval"):
                records.unverified(state, "Candidate may have clicked submit", now=SENT)
            self.assertEqual(state, before)

    def test_uncertain_attempt_requires_same_approved_documents_and_destination(self):
        state = self.approved()
        state["official_destination"] = "https://other.example.com/apply"
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError, "changed since approval"):
            records.unverified(state, "Candidate may have clicked submit", now=SENT)
        self.assertEqual(state, before)
        state = self.approved()
        self.cv.write_bytes(b"Changed CV")
        with self.assertRaisesRegex(ValueError, "attachment changed"):
            records.unverified(state, "Candidate may have clicked submit", now=SENT)

    def test_already_confirmed_application_cannot_be_duplicated_or_reset(self):
        state = self.confirmed()
        with self.assertRaisesRegex(ValueError, "already confirmed"):
            self.confirmed(state)
        with self.assertRaises(ValueError):
            records.prepare(state, self.job, self.cv, now=CHECKED)
        with self.assertRaises(ValueError):
            records.unverified(state, "unknown", now=CHECKED)

    def test_submission_dates_are_timezone_aware_and_ordered(self):
        for value in ("2026-10-23", "2026-10-23T08:20:00", "yesterday", "2026-02-31T00:00:00Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.confirmed(submitted_at=value)
        for value in (PREPARED, "2026-10-23T09:00:00Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.confirmed(submitted_at=value)
        self.assertEqual(records.timestamp("2026-10-23T13:50:00+05:30"), SENT)

    def test_legacy_blocked_state_and_unrelated_evidence_survive_preparation(self):
        legacy = {"company": "Example", "role": "Full Stack Engineer", "source_url": self.job["url"],
                  "platform": "LinkedIn", "status": "blocked", "checked_date": "2026-10-23",
                  "application_submitted": False, "cv_path": str(self.cv),
                  "cv_sha256": records.document(self.cv)["sha256"], "blocker": "Upload permission declined",
                  "verification": {"visual_review": "passed"}, "unknown_evidence": {"receipt": None}}
        state = self.prepared(legacy)
        self.assertEqual(state["status"], "blocked")
        for field in ("cv_path", "cv_sha256", "blocker", "verification", "unknown_evidence", "checked_date"):
            self.assertEqual(state[field], legacy[field])
        self.assertNotIn("events", legacy)

    def test_existing_identity_cannot_be_reused_for_a_different_job(self):
        for field in ("company", "role", "source_url"):
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prepared({field: "https://different.example.com/job" if field == "source_url" else "Different"})

    def test_malformed_prior_states_fail_closed_without_resetting_history(self):
        for bad in ([], {"status": "mystery"}, {"status": []}, {"schema_version": True},
                    {"application_submitted": "false"}, {"cv_sha256": "bad"},
                    {"checked_date": "bad"}, {"prepared_at": "bad"}, {"events": {}},
                    {"events": [{"sequence": 2, "kind": "prepared", "at": PREPARED, "details": {}}]},
                    {"status": "applied", "application_submitted": True}):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                records.prepare(bad, self.job, self.cv, now=PREPARED)

    def test_unsafe_job_and_destination_urls_are_rejected(self):
        for url in ("http://example.com/job", "https://user:secret@example.com/job", "https://localhost/job",
                    "https://127.0.0.1/job", "https://10.0.0.1/job", "https://example.com:3000/job", "file:///tmp/job"):
            for field in ("url", "application_url"):
                job = {**self.job, field: url}
                with self.subTest(url=url, field=field), self.assertRaises(ValueError):
                    records.prepare({}, job, self.cv, now=PREPARED)

    def test_cli_path_is_confined_to_single_application_folder(self):
        root = self.root / "documents" / "applications"
        valid = root / "legacy_company_role" / "application_state.json"
        self.assertEqual(records.cli_state_path(valid, root=root), valid.resolve())
        for path in (self.root / "application_state.json", root / "application_state.json",
                     root / "folder" / "other.json", root / "a" / "b" / "application_state.json"):
            with self.subTest(path=path), self.assertRaises(ValueError):
                records.cli_state_path(path, root=root)

    def test_cli_rejects_external_state_and_does_not_touch_tracker_or_pdf(self):
        tracker = self.root / "job_search_tracker.csv"
        tracker.write_text("date,company,status\n2026-10-23,Example,drafted\n", encoding="utf-8")
        old_csv, old_cv = tracker.read_bytes(), self.cv.read_bytes()
        job_path = self.root / "job.json"
        job_path.write_text(json.dumps(self.job), encoding="utf-8")
        stdout, stderr = io.StringIO(), io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = records.main(["prepare", "--job", str(job_path), "--cv", str(self.cv),
                                 "--state", str(self.root / "application_state.json"), "--now", PREPARED])
        self.assertEqual(code, 1)
        self.assertIn("--state", json.loads(stderr.getvalue())["error"])
        self.assertEqual(tracker.read_bytes(), old_csv)
        self.assertEqual(self.cv.read_bytes(), old_cv)

    def test_atomic_persistence_roundtrip_does_not_change_other_files(self):
        path = self.root / "application_state.json"
        before = {item.name: item.read_bytes() for item in self.root.iterdir() if item.is_file()}
        records.save_state(path, self.confirmed())
        loaded = records.load(path)
        self.assertEqual(loaded["status"], "applied")
        for name, data in before.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual(sorted(item.name for item in self.root.iterdir()), sorted([*before, path.name]))

    def test_cli_prepare_approval_confirmation_and_status_roundtrip(self):
        applications = self.root / "applications"
        job_path = self.root / "job.json"
        job_path.write_text(json.dumps(self.job), encoding="utf-8")
        original_guard = records.cli_state_path

        def call(*args):
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                code = records.main(list(args))
            self.assertEqual(code, 0, stderr.getvalue())
            return json.loads(stdout.getvalue())

        with patch.object(records, "APPLICATIONS", applications), patch.object(
                records, "cli_state_path", side_effect=lambda path: original_guard(path, root=applications)):
            initial = call("prepare", "--job", str(job_path), "--cv", str(self.cv), "--now", PREPARED)
            state_path = initial["state_path"]
            self.assertEqual(Path(state_path).parent.name, "example_full-stack-engineer")
            call("approve", "--state", state_path, "--approval-reference", "user-message:approved", "--now", APPROVED)
            call("submitted", "--state", state_path, "--submitted-at", SENT, "--kind", "user_confirmation",
                 "--confirmation-text", "I submitted this application successfully.", "--confirmation-source", "user-message:confirmed", "--now", CHECKED)
            before = Path(state_path).read_bytes()
            final = call("status", "--state", state_path)
            self.assertTrue(final["application"]["submission_verified"])
            self.assertEqual(Path(state_path).read_bytes(), before, "status must not rewrite state")

    def test_invalid_stored_json_is_not_replaced_or_reinitialized(self):
        path = self.root / "application_state.json"
        path.write_text("{invalid", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "cannot read"):
            records.load(path)
        self.assertEqual(path.read_text(encoding="utf-8"), "{invalid")

    def test_prior_history_cannot_be_backdated(self):
        state = self.approved()
        before = copy.deepcopy(state)
        with self.assertRaisesRegex(ValueError, "precede"):
            records.unverified(state, "Receipt status uncertain", now=PREPARED)
        self.assertEqual(state, before)


if __name__ == "__main__":
    unittest.main()
