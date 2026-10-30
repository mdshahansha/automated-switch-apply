#!/usr/bin/env python3
"""Record application preparation, explicit approval and confirmed submission.

This local audit helper never submits an application, fetches a URL, changes
the tracker or writes documents. An operator must check the named portal receipt,
history, employer acknowledgement or explicit user confirmation before recording
`submitted`. Text checks reject incomplete/failure messages; they do not authenticate
a source or prove submission. Quote the actual confirmation, not the whole form.
An approved ambiguous attempt is `unverified`: reconcile it before trying again.
Unapproved legacy attempts require manual reconciliation; never invent prior approval.
"""

import argparse
import copy
import hashlib
import ipaddress
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from job_key import make_key
from rank_state import save_state

ROOT = Path(__file__).resolve().parent.parent
APPLICATIONS = ROOT / "documents" / "applications"
STATUSES = {"drafted", "prepared", "blocked", "manual_handoff", "approved", "submission_unverified", "applied"}
PREPARATION_STATUSES = {"drafted", "blocked", "manual_handoff"}
EVIDENCE_KINDS = {"portal_receipt", "application_history", "employer_acknowledgement", "user_confirmation"}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TIME_FIELDS = ("prepared_at", "approved_at", "submitted_at", "checked_at", "unverified_at")
# Conservative English/Hindi/Hinglish checks on an operator-checked excerpt.
# Unknown wording stays unverified rather than being treated as a receipt.
INCOMPLETE_EVIDENCE = re.compile(
    r"\b(?:not|never|cannot|can't|couldn't|didn't|hasn't|haven't|wasn't|weren't|isn't|aren't|don't|won't)\b"
    r"|\b(?:unable|fail(?:ed|ure|ing)?|unsuccessful(?:ly)?|pending|draft|incomplete|unknown|unconfirmed|unverified|uncertain|errors?|false|awaiting|queued|button)\b"
    r"|\bno\s+(?:application|submission)\b"
    r"|\b(?:try again|please retry|in progress|ready to|plan(?:ning)? to|want to|need to|will submit|will apply)\b"
    r"|\b(?:click|press|select|tap|review|preview)\b.{0,60}\b(?:submit|apply|application)\b"
    r"|\b(?:submit|apply)\b.{0,20}\bbutton\b"
    r"|\b(?:nahi|nahin|nhi|karna hai|karna baaki|karna baki|karunga|karungi)\b"
    r"|नहीं|नही|असफल|विफल|लंबित|अधूरा|प्रतीक्षा|ड्राफ्ट|बाकी"
    r"|\?", re.I)
RECEIPT_CONFIRMATION = re.compile(
    r"\b(?:your|the|this|my|our) application\s+(?:(?:has been|was|is)\s+)?(?:successfully\s+)?(?:submitted|received|accepted)\b"
    r"|\bapplication\s+(?:successfully\s+)?(?:submitted|received)\b"
    r"|\b(?:we have|we've|we)\s+(?:successfully\s+)?received\s+(?:your|the) application\b"
    r"|\bthank(?:s| you) for (?:applying|your application)\b"
    r"|\byou(?: have|'ve)?\s+(?:successfully\s+)?applied\b"
    r"|\b(?:application )?status\s*[:=-]\s*(?:submitted|applied|received)\b"
    r"|(?:आपका|आपकी)\s+(?:आवेदन|एप्लिकेशन)\s+(?:सफलतापूर्वक\s+)?(?:जमा|सबमिट|प्राप्त)\s+(?:हो गया|किया गया|हुआ)"
    r"|हमें\s+आपका\s+आवेदन\s+प्राप्त\s+हुआ", re.I)
USER_CONFIRMATION = re.compile(
    r"\b(?:i|we)(?: have|'ve)?\s+(?:successfully\s+)?(?:applied\b|(?:submitted|sent)\s+(?:my|our|the|this|a|an)\s+(?:job\s+)?application\b)"
    r"|(?:मैंने|हमने)\s+(?:(?:यह|अपना|अपनी)\s+)?(?:आवेदन|एप्लिकेशन)\s+(?:सफलतापूर्वक\s+)?(?:जमा|सबमिट)\s+(?:कर दिया|किया)"
    r"|(?:मैंने|हमने)\s+(?:आवेदन|अप्लाई)\s+कर\s+दिया"
    r"|\b(?:maine|mainne|mene|humne)\s+(?:(?:apna|apni|yeh|ye)\s+)?(?:application\s+)?(?:submit|apply)\s+(?:kar\s+di(?:ya|yi)?|kiya)\b",
    re.I)


def text(value, field: str, *, maximum: int = 8000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        raise ValueError(f"{field} must be non-empty text (at most {maximum} characters)")
    return value.strip()


def timestamp(value: str) -> str:
    value = text(value, "timestamp", maximum=50)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO date-time with timezone") from exc
    if "T" not in value or parsed.tzinfo is None:
        raise ValueError("timestamp must be an ISO date-time with timezone")
    return parsed.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def safe_url(value, field: str) -> str:
    value = text(value, field, maximum=4000)
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        port = parsed.port
    except ValueError as exc:
        raise ValueError(f"{field} must be a public HTTPS URL") from exc
    if (parsed.scheme != "https" or not host or parsed.username is not None
            or parsed.password is not None or port not in (None, 443)
            or any(char.isspace() or ord(char) < 32 for char in value)
            or "\\" in value or host == "localhost" or "." not in host):
        raise ValueError(f"{field} must be a public HTTPS URL without credentials")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-zA-Z0-9.-]+", host) or ".." in host:
            raise ValueError(f"{field} has an invalid host")
    else:
        if not address.is_global:
            raise ValueError(f"{field} must not refer to a private address")
    return value


def validate_job(job: dict) -> dict:
    if not isinstance(job, dict):
        raise ValueError("job must be an object")
    return {
        "title": text(job.get("title"), "job.title", maximum=500),
        "company": text(job.get("company"), "job.company", maximum=500),
        "url": safe_url(job.get("url"), "job.url"),
        "portal": text(job.get("portal"), "job.portal", maximum=100),
        "application_url": safe_url(job.get("application_url"), "job.application_url"),
    }


def validate_documents(documents) -> None:
    if not isinstance(documents, dict) or not documents or "cv" not in documents:
        raise ValueError("documents must contain a CV")
    if set(documents) - {"cv", "cover_letter"}:
        raise ValueError("unknown document kind")
    for kind, attachment in documents.items():
        if not isinstance(attachment, dict):
            raise ValueError(f"documents.{kind} must be an object")
        text(attachment.get("path"), f"documents.{kind}.path", maximum=4000)
        if not isinstance(attachment.get("sha256"), str) or not SHA256.fullmatch(attachment["sha256"]):
            raise ValueError(f"documents.{kind}.sha256 must be a lowercase SHA-256 digest")


def document(path: Path) -> dict:
    path = Path(path).resolve(strict=True)
    if not path.is_file():
        raise ValueError("attachment must be an existing file")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest()}


def binding(state: dict) -> dict:
    fields = ("job_key", "company", "title", "platform", "job_url", "official_destination", "documents")
    if any(key not in state for key in fields):
        raise ValueError("application identity or documents are incomplete; prepare it first")
    return {key: copy.deepcopy(state[key]) for key in fields}


def validate_binding(value) -> None:
    if not isinstance(value, dict):
        raise ValueError("approval.binding must be an object")
    for field in ("job_key", "company", "title", "platform"):
        text(value.get(field), f"approval.binding.{field}", maximum=500)
    safe_url(value.get("job_url"), "approval.binding.job_url")
    safe_url(value.get("official_destination"), "approval.binding.official_destination")
    validate_documents(value.get("documents"))


def validate_state(state) -> None:
    """Validate known fields; preserve unrelated legacy fields and history."""
    if not isinstance(state, dict):
        raise ValueError("application state must be an object")
    if "status" in state and (not isinstance(state["status"], str) or state["status"] not in STATUSES):
        raise ValueError("unknown application status; reconcile it without resetting history")
    if "schema_version" in state and (type(state["schema_version"]) is not int or state["schema_version"] != 1):
        raise ValueError("unsupported application state schema")
    if "schema_version" in state:
        validate_binding(binding(state))
    for field in TIME_FIELDS:
        if field in state:
            timestamp(state[field])
    if "checked_date" in state:
        try:
            if not isinstance(state["checked_date"], str):
                raise ValueError()
            date.fromisoformat(state["checked_date"])
        except ValueError as exc:
            raise ValueError("checked_date must be an ISO date") from exc
    for field in ("application_submitted", "submission_verified", "submission_attempted", "new_resume_uploaded"):
        if field in state and not isinstance(state[field], bool):
            raise ValueError(f"{field} must be a boolean")
    for field in ("cv_sha256", "cover_letter_sha256"):
        if field in state and (not isinstance(state[field], str) or not SHA256.fullmatch(state[field])):
            raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    for field in ("job_url", "source_url", "official_destination"):
        if field in state:
            safe_url(state[field], field)
    if "documents" in state:
        validate_documents(state["documents"])
    if "events" in state:
        if not isinstance(state["events"], list):
            raise ValueError("events must be an array; history will not be reset")
        for index, event in enumerate(state["events"], 1):
            if (not isinstance(event, dict) or event.get("sequence") != index
                    or isinstance(event.get("sequence"), bool) or not isinstance(event.get("details"), dict)):
                raise ValueError("invalid application event history")
            text(event.get("kind"), "event.kind", maximum=100)
            timestamp(event.get("at"))
    if "approval" in state:
        approval = state["approval"]
        if not isinstance(approval, dict):
            raise ValueError("approval must be an object")
        text(approval.get("reference"), "approval.reference")
        timestamp(approval.get("approved_at"))
        validate_binding(approval.get("binding"))
    if state.get("submission_verified") or state.get("status") == "applied":
        if (state.get("submission_verified") is not True or state.get("application_submitted") is not True
                or state.get("status") != "applied" or "approval" not in state):
            raise ValueError("inconsistent confirmed submission; reconcile prior state")
        timestamp(state.get("submitted_at"))
        timestamp(state.get("checked_at"))
        validate_evidence(state.get("submission_evidence"))
        if state["approval"]["binding"] != binding(state):
            raise ValueError("confirmed submission identity no longer matches its approval")
        if not timestamp(state["approval"]["approved_at"]) <= timestamp(state["submitted_at"]) <= timestamp(state["checked_at"]):
            raise ValueError("inconsistent submission timestamps")
    elif state.get("application_submitted"):
        raise ValueError("legacy submission has no checked evidence; reconcile it before updating")


def load(path: Path) -> dict:
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read application state: {exc}") from exc
    validate_state(state)
    return state


def event(state: dict, kind: str, at: str, details: dict) -> None:
    history = state.setdefault("events", [])
    if history and timestamp(history[-1]["at"]) > at:
        raise ValueError("event time cannot precede existing history")
    history.append({"sequence": len(history) + 1, "kind": kind, "at": at, "details": copy.deepcopy(details)})


def prepare(state: dict, job: dict, cv: Path, cover_letter: Path | None = None,
            *, status: str | None = None, blocker: str | None = None, now: str | None = None) -> dict:
    validate_state(state)
    if state.get("status") in {"applied", "submission_unverified"}:
        raise ValueError("already submitted or uncertain; reconcile the existing application before preparing again")
    job = validate_job(job)
    status = status or (state.get("status") if state.get("status") in PREPARATION_STATUSES else "drafted")
    if status not in PREPARATION_STATUSES:
        raise ValueError("prepare status must be drafted, blocked or manual_handoff")
    if status == "blocked" and not (blocker or state.get("blocker")):
        raise ValueError("blocked applications require a blocker")
    at = timestamp(now or utc_now())
    documents = {"cv": document(cv)}
    if cover_letter is not None:
        documents["cover_letter"] = document(cover_letter)
    key = make_key(job["company"], job["title"], job["url"])
    prior_company = state.get("company")
    prior_title = state.get("title", state.get("role"))
    prior_url = state.get("job_url", state.get("source_url"))
    for before, after in ((prior_company, job["company"]), (prior_title, job["title"]), (prior_url, job["url"])):
        if before is not None and before != after:
            raise ValueError("existing state belongs to a different job; use its own application folder")
    result = copy.deepcopy(state)
    result.update({"schema_version": 1, "job_key": key, "company": job["company"], "title": job["title"],
                   "platform": job["portal"], "job_url": job["url"], "official_destination": job["application_url"],
                   "documents": documents, "prepared_at": at, "status": status,
                   "application_submitted": False, "submission_verified": False})
    if blocker is not None:
        result["blocker"] = text(blocker, "blocker")
    previous_approval = result.pop("approval", None)
    result.pop("approved_at", None)
    event(result, "prepared", at, {"binding": binding(result), "status": status,
                                  "blocker": result.get("blocker"), "superseded_approval": previous_approval})
    validate_state(result)
    return result


def unchanged_documents(state: dict) -> None:
    validate_documents(state.get("documents"))
    for attachment in state["documents"].values():
        if document(Path(attachment["path"])) != attachment:
            raise ValueError("attachment changed; prepare and obtain explicit approval again")


def approve(state: dict, reference: str, *, now: str | None = None) -> dict:
    validate_state(state)
    if state.get("status") not in {"drafted", "prepared", "manual_handoff"}:
        raise ValueError("only a prepared, unblocked application can be approved")
    unchanged_documents(state)
    current = binding(state)
    validate_binding(current)
    at = timestamp(now or utc_now())
    approval = {"reference": text(reference, "approval-reference"), "approved_at": at, "binding": current}
    result = copy.deepcopy(state)
    result.update({"status": "approved", "approval": approval, "approved_at": at})
    event(result, "approved", at, approval)
    return result


def validate_evidence(evidence) -> dict:
    """Reject unsafe excerpts; the caller must independently check their source."""
    if (not isinstance(evidence, dict) or not isinstance(evidence.get("kind"), str)
            or evidence.get("kind") not in EVIDENCE_KINDS):
        raise ValueError("confirmation kind must be portal_receipt, application_history, employer_acknowledgement or user_confirmation")
    exact = text(evidence.get("text"), "confirmation-text")
    source = text(evidence.get("source"), "confirmation-source", maximum=4000)
    if source.lower().startswith(("http:", "https:")):
        safe_url(source, "confirmation-source")
    normalized = " ".join(exact.replace("’", "'").replace("_", " ").split())
    # A failure may contain the words "application submitted" in a negated clause.
    # Reject it before looking for affirmative wording, including mixed excerpts.
    if INCOMPLETE_EVIDENCE.search(normalized):
        raise ValueError("confirmation shows failure, uncertainty or an incomplete step; record unverified and reconcile")
    positive = RECEIPT_CONFIRMATION.search(normalized)
    if evidence["kind"] == "user_confirmation":
        positive = positive or USER_CONFIRMATION.search(normalized)
    if not positive:
        raise ValueError("confirmation-text needs an affirmative checked submission confirmation; upload/form completion is insufficient")
    return {"kind": evidence["kind"], "text": evidence["text"], "source": evidence["source"]}


def submitted(state: dict, *, submitted_at: str, kind: str, confirmation_text: str,
              source: str, now: str | None = None) -> dict:
    """Record an operator-checked confirmation; do not infer one from a page."""
    validate_state(state)
    if state.get("status") == "applied":
        raise ValueError("application is already confirmed submitted; do not create a duplicate")
    if state.get("status") not in {"approved", "submission_unverified"} or "approval" not in state:
        raise ValueError("explicit user approval is required before recording submission")
    unchanged_documents(state)
    if state["approval"]["binding"] != binding(state):
        raise ValueError("job, destination or attachments changed since approval")
    sent, checked = timestamp(submitted_at), timestamp(now or utc_now())
    if sent > checked or sent < timestamp(state["approval"]["approved_at"]):
        raise ValueError("submission must be after approval and no later than its evidence check")
    evidence = validate_evidence({"kind": kind, "text": confirmation_text, "source": source})
    result = copy.deepcopy(state)
    result.update({"status": "applied", "application_submitted": True, "submission_verified": True,
                   "submission_attempted": True, "submitted_at": sent, "checked_at": checked,
                   "submission_evidence": evidence})
    event(result, "submission_confirmed", checked, {"submitted_at": sent, "evidence": evidence,
                                                   "binding": binding(result)})
    validate_state(result)
    return result


def unverified(state: dict, reason: str, *, now: str | None = None) -> dict:
    validate_state(state)
    if state.get("status") == "applied":
        raise ValueError("a confirmed submission cannot be reset to uncertain")
    if state.get("status") not in {"approved", "submission_unverified"} or "approval" not in state:
        raise ValueError("a matching prior approval is required; reconcile unapproved legacy attempts manually without inventing approval")
    unchanged_documents(state)
    if state["approval"]["binding"] != binding(state):
        raise ValueError("job, destination or attachments changed since approval")
    at = timestamp(now or utc_now())
    result = copy.deepcopy(state)
    result.update({"status": "submission_unverified", "application_submitted": False,
                   "submission_verified": False, "submission_attempted": True,
                   "unverified_at": at, "checked_at": at})
    event(result, "submission_unverified", at, {"reason": text(reason, "reason"),
                                               "next_action": "Check portal history or a receipt before any retry."})
    return result


def cli_state_path(path: Path, *, root: Path = APPLICATIONS) -> Path:
    resolved = Path(path).resolve()
    try:
        relative = resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("--state must be inside documents/applications") from exc
    if len(relative.parts) != 2 or relative.name != "application_state.json":
        raise ValueError("--state must be documents/applications/<company>_<role>/application_state.json")
    return resolved


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--state", type=Path)
    common.add_argument("--now", help="checked ISO timestamp with timezone; default now UTC")
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", parents=[common])
    prep.add_argument("--job", type=Path, required=True, help="verified job JSON: title, company, url, portal, application_url")
    prep.add_argument("--cv", type=Path, required=True)
    prep.add_argument("--cover-letter", type=Path)
    prep.add_argument("--status", choices=sorted(PREPARATION_STATUSES))
    prep.add_argument("--blocker")
    approval = commands.add_parser("approve", parents=[common])
    approval.add_argument("--approval-reference", required=True, help="reference to explicit human approval of these documents and destination")
    sent = commands.add_parser("submitted", parents=[common], help="record an operator-checked confirmation; no portal verification or submission")
    sent.add_argument("--submitted-at", required=True)
    sent.add_argument("--kind", choices=sorted(EVIDENCE_KINDS), required=True)
    sent.add_argument("--confirmation-text", required=True)
    sent.add_argument("--confirmation-source", required=True)
    uncertain = commands.add_parser("unverified", parents=[common])
    uncertain.add_argument("--reason", required=True)
    commands.add_parser("status", parents=[common])
    args = parser.parse_args(argv)
    try:
        job = None
        if args.command == "prepare":
            job = validate_job(json.loads(args.job.read_text(encoding="utf-8")))
            path = args.state or APPLICATIONS / make_key(job["company"], job["title"], job["url"]) / "application_state.json"
        else:
            if args.state is None:
                raise ValueError("--state is required")
            path = args.state
        path = cli_state_path(path)
        state = load(path) if path.exists() else {}
        if args.command == "prepare":
            result = prepare(state, job, args.cv, args.cover_letter, status=args.status, blocker=args.blocker, now=args.now)
        elif not path.exists():
            raise ValueError("application state does not exist; prepare it first")
        elif args.command == "approve":
            result = approve(state, args.approval_reference, now=args.now)
        elif args.command == "submitted":
            result = submitted(state, submitted_at=args.submitted_at, kind=args.kind,
                               confirmation_text=args.confirmation_text, source=args.confirmation_source, now=args.now)
        elif args.command == "unverified":
            result = unverified(state, args.reason, now=args.now)
        else:
            result = state
        if args.command != "status":
            path.parent.mkdir(parents=True, exist_ok=True)
            save_state(path, result)
        print(json.dumps({"state_path": str(path), "application": result}, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
