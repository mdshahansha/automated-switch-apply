#!/usr/bin/env python3
"""Read-only portal discovery, manual import and integration status.

The registry records access decisions; an installed CLI alone never grants
permission to dispatch it. Existing /scrape CLIs remain independently usable.
No command submits applications, signs in, or fetches a supplied import URL.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

from portal_jobs import STATE, TRACKER, ingest_jobs, normalize_job  # noqa: E402

REGISTRY = Path(__file__).with_name("portal_registry.json")
PUBLIC_MODES = {"public_api", "public_feed"}
ADAPTERS = {"himalayas-search", "remoteok-search", "weworkremotely-search", "freehire-search"}
SENIORITIES = {"entry-level": "Entry-level", "mid-level": "Mid-level", "senior": "Senior",
               "manager": "Manager", "director": "Director", "executive": "Executive"}
FREEHIRE_SENIORITIES = {"intern", "junior", "middle", "senior", "staff", "principal", "lead", "manager", "director", "executive"}
COUNTRIES = {"india": "IN", "united states": "US", "usa": "US", "united kingdom": "GB",
             "uk": "GB", "germany": "DE", "canada": "CA", "australia": "AU", "singapore": "SG"}


def timestamp(now=None):
    if isinstance(now, str):
        value = datetime.fromisoformat(now.replace("Z", "+00:00"))
    else:
        value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        raise ValueError("now must include a timezone")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def read_state(path):
    if not path.exists():
        return {"seen": {}, "portal_status": {}}
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read state: {exc}") from exc
    if not isinstance(doc, dict):
        raise ValueError("state must be a JSON object")
    statuses = doc.get("portal_status", {})
    if not isinstance(statuses, dict):
        raise ValueError("portal_status must be a JSON object")
    return doc


def discover(root=ROOT, registry_path=REGISTRY):
    """Discover skills without granting newly discovered files execution access."""
    try:
        data = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read portal registry: {exc}") from exc
    if not isinstance(data, dict) or not isinstance(data.get("portals"), list):
        raise ValueError("portal registry needs a portals array")
    registered = {}
    for row in data["portals"]:
        if not isinstance(row, dict) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-search", str(row.get("id", ""))):
            raise ValueError("registry contains an invalid portal ID")
        if row["id"] in registered:
            raise ValueError(f"duplicate registry portal: {row['id']}")
        registered[row["id"]] = dict(row)
    skills = root / ".agents" / "skills"
    installed = {p.parent.name: p for p in skills.glob("*/SKILL.md") if p.parent.name.endswith("-search")}
    for portal, path in installed.items():
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*-search", portal):
            continue
        row = registered.setdefault(portal, {"id": portal, "name": portal, "aliases": [portal.removesuffix("-search")],
            "groups": [], "mode": "unverified", "default": False, "url": None,
            "reason": "Discovered skill; access and adapter contract need review before dispatch."})
        content = path.read_text(encoding="utf-8")
        frontmatter = content.split("\n---", 1)[0] if content.startswith("---\n") else ""
        row["skill_enabled"] = not bool(re.search(r"(?m)^enabled:\s*false(?:\s|$)", frontmatter))
    for portal, row in registered.items():
        cli = root / ".agents" / "skills" / portal / "cli" / "src" / "cli.ts"
        # Resolved paths prevent a symlinked CLI from escaping the skills tree.
        contained = cli.resolve().is_relative_to(skills.resolve())
        row["installed"] = portal in installed
        row["cli_installed"] = cli.is_file() and contained
        row.setdefault("skill_enabled", False)
        row["automatic"] = bool(row["mode"] in PUBLIC_MODES and portal in ADAPTERS
                                and row["installed"] and row["cli_installed"] and row["skill_enabled"])
    return list(registered.values())


def token(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def select_portals(portals, selectors):
    if not selectors:
        return [p for p in portals if p.get("default") and p["automatic"]]
    selected = set()
    for selector in selectors:
        wanted = token(selector)
        if wanted == "all":
            selected.update(p["id"] for p in portals)
            continue
        matches = [p for p in portals if wanted in {token(x) for x in [p["id"], p["name"],
                    *p.get("aliases", []), *p.get("groups", [])]}]
        if not matches:
            raise ValueError(f"unknown portal or group: {selector}")
        selected.update(p["id"] for p in matches)
    return [p for p in portals if p["id"] in selected]


def country_code(value):
    if re.fullmatch(r"[A-Za-z]{2}", value):
        return value.upper()
    return COUNTRIES.get(value.casefold())


def build_arguments(portal, args):
    """Translate only capabilities whose actual CLI contract is known."""
    identity = portal["id"]
    flags = ["search", "--format", "json", "--page", str(args.page), "--limit", str(args.limit)]
    unsupported = []

    def reject(name, value, reason):
        unsupported.append({"filter": name, "requested": value, "reason": reason})

    if args.query:
        flags += ["--query", args.query]
    if args.location:
        code = country_code(args.location)
        if identity == "himalayas-search":
            if code:
                flags += ["--country", code]
            else:
                reject("location", args.location, "This adapter supports country names/codes, not city or region matching. Use an ISO alpha-2 code.")
        elif identity == "freehire-search":
            flags += ["--country", code] if code else ["--city", args.location]
        else:
            flags += ["--location", args.location]
    if args.remote and args.remote != "any":
        if identity == "freehire-search":
            flags += ["--remote", args.remote]
        elif args.remote != "remote":
            reject("remote", args.remote, "This source lists remote roles only.")
    if args.experience:
        level = args.experience.casefold()
        if identity == "himalayas-search" and level in SENIORITIES:
            flags += ["--seniority", SENIORITIES[level]]
        elif identity == "freehire-search" and level in FREEHIRE_SENIORITIES:
            flags += ["--seniority", level]
        else:
            reject("experience", args.experience, "No verified numeric experience filter. Only documented seniority labels are supported on Himalayas/freehire; feed adapters have neither.")
    if args.jobage is not None:
        flags += ["--jobage", str(args.jobage)]
    if identity == "freehire-search":
        flags += ["--description-format", "text"]
    elif identity == "weworkremotely-search":
        flags += ["--include-description"]
    return flags, unsupported


def portal_view(portal, previous=None):
    view = {key: portal.get(key) for key in ("id", "name", "mode", "automatic", "installed", "cli_installed", "skill_enabled", "url", "reason", "filters")}
    view.update(last_success=None, last_search=None, jobs_discovered=0, duplicates_removed=0, shortlisted=0)
    view.update({key: value for key, value in (previous or {}).items() if key in {
        "status", "last_checked", "last_search", "last_success", "jobs_discovered", "error", "unsupported_filters",
        "last_import", "jobs_imported", "duplicates_removed", "shortlisted"}})
    return view


def result_rows(payload):
    if not isinstance(payload, dict) or not isinstance(payload.get("results"), list):
        raise ValueError("CLI output must contain a results array")
    return payload["results"]


def imported_rows(payload):
    rows = payload.get("results") if isinstance(payload, dict) and "results" in payload else payload
    if isinstance(rows, dict):
        rows = [rows]
    if not isinstance(rows, list):
        raise ValueError("import needs a job object, job array or {results:[...]} JSON document")
    return rows


def execute_search(args, *, root=ROOT, registry_path=REGISTRY, run=subprocess.run, which=shutil.which, now=None):
    portals = select_portals(discover(root, registry_path), args.selectors)
    stamp = timestamp(now)
    previous = read_state(args.state).get("portal_status", {})
    updates, jobs, reports, invalid = {}, [], [], []
    bun = which("bun")
    for portal in portals:
        identity = portal["id"]
        prior = previous.get(identity, {})
        if not isinstance(prior, dict):
            raise ValueError(f"invalid prior status for {identity}")
        report = portal_view(portal, prior)
        report.update({"jobs_discovered": 0, "duplicates_removed": 0, "shortlisted": 0,
                       "last_checked": stamp, "unsupported_filters": [], "error": None})
        report["requested_filters"] = {key: getattr(args, key) for key in ("query", "location", "remote", "experience", "jobage", "page", "limit")}
        if not portal["automatic"]:
            report["status"] = "unverified" if portal["mode"] == "unverified" else "manual"
            if portal["mode"] in PUBLIC_MODES:
                report["status"] = "disabled" if not portal["skill_enabled"] else "unavailable"
            report["manual_import"] = f"python tools/portal_search.py import --portal {identity} --file jobs.json"
        else:
            flags, unsupported = build_arguments(portal, args)
            report["unsupported_filters"] = unsupported
            if unsupported:
                report["status"] = "unsupported_filters"
            elif not bun:
                report.update(status="unavailable", error="Bun is not on PATH; no search was attempted.")
            else:
                report["last_search"] = stamp
                cli = root / ".agents" / "skills" / identity / "cli" / "src" / "cli.ts"
                try:
                    response = run([bun, "run", str(cli), *flags], cwd=root, shell=False, stdin=subprocess.DEVNULL,
                                   capture_output=True, text=True, encoding="utf-8", timeout=90, check=False)
                    if response.returncode:
                        message = (response.stderr or "CLI exited without an error message").strip()[:800]
                        report.update(status="blocked" if re.search(r"(?:403|401|access denied|forbidden)", message, re.I) else "failed", error=message)
                    else:
                        try:
                            payload = json.loads(response.stdout)
                            rows = result_rows(payload)
                        except (json.JSONDecodeError, ValueError) as exc:
                            raise ValueError(f"invalid CLI response: {exc}") from exc
                        accepted = []
                        for index, row in enumerate(rows):
                            try:
                                metadata = payload.get("meta", {})
                                if isinstance(row, dict) and isinstance(metadata, dict) and metadata.get("attribution") and not row.get("attribution"):
                                    row = {**row, "attribution": metadata["attribution"]}
                                accepted.append(normalize_job(row, identity, source="cli", now=stamp))
                            except (TypeError, ValueError) as exc:
                                invalid.append({"portal": identity, "index": index, "error": str(exc)})
                        if rows and not accepted:
                            raise ValueError("every returned job was malformed")
                        jobs.extend(accepted)
                        report.update(status="operational", last_success=stamp, jobs_discovered=len(accepted),
                                      source_metadata=payload.get("meta", {}))
                except subprocess.TimeoutExpired:
                    report.update(status="failed", error="Portal CLI exceeded the 90-second request budget.")
                except (OSError, ValueError) as exc:
                    report.update(status="failed", error=str(exc))
        reports.append(report)
        # Store only runtime status; current registry capabilities are projected
        # afresh on the next status command rather than duplicated into history.
        updates[identity] = {key: value for key, value in report.items() if key in {
            "status", "last_checked", "last_search", "last_success", "jobs_discovered", "error", "unsupported_filters"}}
    summary = {"added": [], "updated": [], "duplicates_removed": 0, "shortlisted": 0, "invalid": []}
    if not args.dry_run:
        summary = ingest_jobs(jobs, state_path=args.state, tracker_path=args.tracker, portal_updates=updates, now=stamp)
        for report in reports:
            counts = summary.get("per_portal", {}).get(report["id"], {})
            for field in ("duplicates_removed", "shortlisted"):
                if field in counts:
                    report[field] = counts[field]
    return {"command": "search", "dry_run": args.dry_run, "checked_at": stamp, "portals": reports,
            "results": jobs, "summary": {**summary, "invalid": [*invalid, *summary.get("invalid", [])]},
            "coverage": "One selected page per automatic portal. Feed pages/filtering are local; missing feed jobs do not establish closure.",
            "eligibility": "Remote/worldwide labels do not establish India eligibility; verify country, timezone and full description."}


def execute_import(args, *, root=ROOT, registry_path=REGISTRY, now=None):
    selected = select_portals(discover(root, registry_path), [args.portal])
    if len(selected) != 1:
        raise ValueError("import --portal must identify exactly one portal, not a group")
    try:
        payload = json.loads(args.file.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read import: {exc}") from exc
    identity = selected[0]["id"]
    stamp = timestamp(now)
    # Validate the whole file before any mutation. Manual provenance is explicit
    # and no supplied source URL is ever contacted.
    jobs = [normalize_job(row, identity, source="manual", now=stamp) for row in imported_rows(payload)]
    updates = {identity: {"status": "manual", "last_import": stamp, "jobs_imported": len(jobs)}}
    summary = {"added": [], "updated": [], "duplicates_removed": 0, "shortlisted": 0, "invalid": []}
    if not args.dry_run:
        summary = ingest_jobs(jobs, state_path=args.state, tracker_path=args.tracker, portal_updates=updates, now=stamp)
    return {"command": "import", "portal": identity, "dry_run": args.dry_run, "results": jobs, "summary": summary}


def execute_status(args, *, root=ROOT, registry_path=REGISTRY):
    doc = read_state(args.state)
    portals = select_portals(discover(root, registry_path), args.selectors or ["all"])
    statuses = doc.get("portal_status", {})
    reports = []
    for portal in portals:
        prior = statuses.get(portal["id"], {})
        if not isinstance(prior, dict):
            raise ValueError(f"invalid prior status for {portal['id']}")
        report = portal_view(portal, prior)
        report.setdefault("status", "not_checked" if portal["automatic"] else ("unverified" if portal["mode"] == "unverified" else "manual"))
        report.setdefault("last_success", None)
        report.setdefault("jobs_discovered", 0)
        report.setdefault("duplicates_removed", 0)
        report.setdefault("shortlisted", 0)
        reports.append(report)
    seen = doc.get("seen", {})
    shortlisted = sum(isinstance(job, dict) and job.get("status") == "ranked"
                      and job.get("rank_verdict") in {"Strong Fit", "Good Fit"}
                      and all(job.get(gate) != "FAIL" for gate in ("location_verdict", "language_gate", "preference_gate"))
                      for job in seen.values()) if isinstance(seen, dict) else 0
    return {"command": "status", "portals": reports, "summary": {"configured": len(reports),
        "automatic": sum(p["automatic"] for p in reports), "operational": sum(p["status"] == "operational" for p in reports),
        "failed_or_blocked": sum(p["status"] in {"failed", "blocked", "unavailable"} for p in reports),
        "jobs_discovered": sum(p.get("jobs_discovered", 0) for p in reports),
        "duplicates_removed": sum(p.get("duplicates_removed", 0) for p in reports),
        "shortlisted": shortlisted}, "note": "Status reads saved evidence only; it performs no network request."}


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def make_parser():
    parser = Parser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True, parser_class=Parser)
    for command in ("search", "status", "links", "import"):
        sub = commands.add_parser(command)
        sub.add_argument("--state", type=Path, default=STATE)
        sub.add_argument("--tracker", type=Path, default=TRACKER)
        if command != "import":
            sub.add_argument("selectors", nargs="*", help="portal aliases or India/remote/all groups")
        if command in {"search", "import"}:
            sub.add_argument("--dry-run", action="store_true", help="validate and return output without writing state")
        if command == "search":
            sub.add_argument("--query", "-q")
            sub.add_argument("--location", "-l")
            sub.add_argument("--remote", nargs="?", const="remote", choices=("any", "remote", "hybrid", "onsite"))
            sub.add_argument("--experience", help="documented seniority label; numeric years are reported unsupported")
            sub.add_argument("--jobage", type=int)
            sub.add_argument("--page", type=int, default=1)
            sub.add_argument("--limit", type=int, default=20)
        if command == "import":
            sub.add_argument("--portal", required=True)
            sub.add_argument("--file", type=Path, required=True)
    return parser


def main(argv=None):
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        args = make_parser().parse_args(argv)
        if args.command == "search":
            if args.page < 1 or not 1 <= args.limit <= 20 or (args.jobage is not None and not 1 <= args.jobage <= 36500):
                raise ValueError("page must be positive, limit 1..20, and jobage 1..36500")
            for name in ("query", "location", "experience"):
                if getattr(args, name) is not None and not getattr(args, name).strip():
                    raise ValueError(f"{name} must not be empty")
            output = execute_search(args)
        elif args.command == "import":
            output = execute_import(args)
        elif args.command == "status":
            output = execute_status(args)
        else:
            portals = select_portals(discover(), args.selectors or ["all"])
            output = {"command": "links", "portals": [portal_view(p) for p in portals],
                      "note": "These are verified starting pages. No search or authentication was performed."}
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, TypeError, ValueError) as exc:
        print(json.dumps({"error": str(exc), "code": "PORTAL_SEARCH_ERROR"}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
