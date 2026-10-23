"""Normalize public/manual portal observations into the existing /scrape history.

This module never fetches a URL, evaluates a candidate, or records an application.
Unknown job fields remain unknown. Repeated observations refresh provenance while
preserving the ranking and application history already on disk.
"""

import hashlib
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from job_key import make_key
from posting_guard import guard
from rank_state import STATE, TRACKER, load_state, norm, save_state, tracker_pairs

TRACKING_KEYS = {"fbclid", "gclid", "msclkid", "trackingid", "trk"}


def timestamp(value=None) -> str:
    if value is None:
        value = datetime.now(timezone.utc)
    elif isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("now must be an ISO timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise ValueError("now must include a timezone")
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def canonical_url(value) -> str:
    if not isinstance(value, str) or not value.strip() or re.search(r"[\x00-\x20\\]", value):
        raise ValueError("a public http(s) posting URL is required")
    try:
        parts = urlsplit(value.strip())
        port = parts.port
    except ValueError as exc:
        raise ValueError("invalid posting URL") from exc
    if parts.scheme not in ("http", "https") or not parts.hostname or parts.username or parts.password:
        raise ValueError("posting URL must be http(s), without credentials")
    host = parts.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    if port and (parts.scheme, port) not in (("http", 80), ("https", 443)):
        host += f":{port}"
    query = sorted((key, val) for key, val in parse_qsl(parts.query, keep_blank_values=True)
                   if not key.lower().startswith("utm_") and key.lower() not in TRACKING_KEYS)
    return urlunsplit((parts.scheme, host, parts.path.rstrip("/") or "/", urlencode(query), ""))


def text(value):
    return value.strip() if isinstance(value, str) and value.strip() else None


def date_value(value):
    if isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)) and math.isfinite(value):
            return timestamp(datetime.fromtimestamp(value, timezone.utc))
        if isinstance(value, str) and value.strip():
            raw = value.strip()
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
                return datetime.fromisoformat(raw).date().isoformat()
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            return timestamp(parsed) if parsed.tzinfo else None
    except (ValueError, OverflowError, OSError):
        pass
    return None


def first_value(raw, *keys):
    return next((raw[key] for key in keys if raw.get(key) is not None), None)


def source_id(raw, portal, url):
    value = first_value(raw, "job_id", "source_id", "id")
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if text(value):
        return text(value)
    parts = urlsplit(url)
    if portal == "himalayas-search":
        match = re.search(r"/companies/([^/]+)/jobs/([^/]+)$", parts.path)
        return f"{match[1]}/{match[2]}" if match else None
    if portal == "weworkremotely-search":
        return parts.path.rsplit("/", 1)[-1] if "/remote-jobs/" in parts.path else None
    if portal in ("linkedin-search", "remoteok-search", "hirist-search", "iimjobs-search"):
        match = re.search(r"(?:/|-)(\d{5,})$", parts.path)
        if match:
            return match[1]
    for key, val in parse_qsl(parts.query):
        if key.lower() in ("id", "jobid", "job_id", "jk", "gh_jid", "requisitionid") and val:
            return val
    return None


def salary_value(raw, portal):
    supplied = raw.get("salary")
    data = supplied if isinstance(supplied, dict) else raw
    def amount(*keys):
        number = first_value(data, *keys)
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number) or number < 0:
            return None
        return None if portal == "remoteok-search" and number == 0 else number
    result = {"min": amount("min", "minSalary", "salary_min"), "max": amount("max", "maxSalary", "salary_max"),
              "currency": text(first_value(data, "currency", "salary_currency")),
              "period": text(first_value(data, "period", "salaryPeriod", "salary_period")),
              "text": text(supplied) if isinstance(supplied, str) else text(data.get("text"))}
    return result if any(v is not None for v in result.values()) else None


def normalize_job(raw: dict, portal: str, *, source="cli", now=None) -> dict:
    if not isinstance(raw, dict) or not text(portal):
        raise ValueError("job must be an object with a portal name")
    if source not in ("cli", "manual", "websearch"):
        raise ValueError("source must be cli, manual, or websearch")
    title = text(raw.get("title"))
    if not title:
        raise ValueError("job title is required")
    original = text(first_value(raw, "original_url", "url", "source_url", "guid"))
    url = canonical_url(original)
    observed = timestamp(now)
    description = text(raw.get("description"))
    findings = None
    if description:
        description, findings = guard(description, "auto")
    published = first_value(raw, "posting_date", "posted_date", "posted_at")
    date_meaning = text(raw.get("date_meaning")) or ("last_updated" if portal == "himalayas-search" else "posting_date")
    if date_meaning not in ("posting_date", "last_updated", "unknown"):
        raise ValueError("unknown date_meaning")
    upstream_date = date_value(first_value(raw, "date", "pubDate", "posted_at"))
    posting_date = date_value(published) if published is not None else (upstream_date if date_meaning == "posting_date" else None)
    updated = date_value(raw.get("updated_at")) or (upstream_date if date_meaning == "last_updated" else None)
    expiry = date_value(first_value(raw, "expires_at", "expiresAt", "expiryDate"))
    deadline = date_value(raw.get("deadline")) or expiry
    expired = raw.get("isActive") is False or raw.get("is_active") is False or raw.get("status") in ("expired", "closed")
    if expiry:
        expired = expired or (expiry < observed if "T" in expiry else expiry < observed[:10])
    if deadline and not expiry:
        expired = expired or deadline[:10] < observed[:10]
    application_url = text(first_value(raw, "application_url", "applicationLink", "apply_url"))
    if application_url:
        canonical_url(application_url)  # Validate without discarding attribution parameters.
    identifier = source_id(raw, portal, url)
    company = text(raw.get("company"))
    if isinstance(raw.get("company"), dict):
        company = text(raw["company"].get("name"))
    company = company or text(raw.get("companyName"))
    metadata = {key: raw[key] for key in ("locationRestrictions", "timezoneRestrictions", "countries", "regions", "seniority", "skills", "tags", "attribution", "upstream_source", "external_id") if key in raw}
    work_mode = text(first_value(raw, "work_mode", "workMode"))
    remote = raw.get("remote") if isinstance(raw.get("remote"), bool) else None
    if remote is None and work_mode in ("remote", "hybrid", "onsite"):
        remote = work_mode == "remote"
    if remote is None and portal in ("himalayas-search", "remoteok-search", "weworkremotely-search"):
        remote = True
    result = {
        "id": identifier, "job_id": identifier, "title": title, "company": company,
        "location": text(raw.get("location")), "description": description, "salary": salary_value(raw, portal),
        "date": upstream_date or posting_date, "posting_date": posting_date,
        "posted_date": posting_date[:10] if posting_date else None, "date_meaning": date_meaning, "updated_at": updated,
        "url": url, "canonical_url": url, "original_url": original, "source_url": original,
        "application_url": application_url, "source": source, "portal": portal,
        "first_seen": observed[:10], "last_seen": observed, "deadline": deadline[:10] if deadline else None,
        "expires_at": expiry, "status": "expired" if expired else "new", "fit": None,
        "remote": remote, "work_mode": work_mode,
        "employment_type": text(first_value(raw, "employment_type", "employmentType", "type")),
        "experience": raw.get("experience") if isinstance(raw.get("experience"), (dict, str)) else None,
        "requisition_id": text(raw.get("requisition_id")), "source_metadata": metadata,
    }
    if findings:
        result["posting_guard"] = {"verdict": findings["verdict"], "counts": {
            key: len(value) if isinstance(value, (list, tuple, dict)) else int(value) if isinstance(value, (int, bool)) else 0
            for key, value in findings.items() if key != "verdict"
        }}
    return result


def _url(entry):
    try:
        return canonical_url(entry.get("url"))
    except ValueError:
        return None


def _identities(entry):
    sources = [entry] + (entry.get("discovery_sources") or [])
    return {(s.get("portal"), str(s.get("job_id") or s.get("id"))) for s in sources
            if isinstance(s, dict) and s.get("portal") and (s.get("job_id") or s.get("id"))}


def is_shortlisted(entry):
    return (entry.get("status") == "ranked" and entry.get("rank_verdict") in ("Strong Fit", "Good Fit")
            and entry.get("location_verdict") != "FAIL" and entry.get("language_gate") != "FAIL"
            and entry.get("preference_gate") != "FAIL")


def ingest_jobs(jobs: list, state_path: Path = STATE, tracker_path: Path = TRACKER, portal_updates: dict = None, now=None) -> dict:
    """Atomically add observations, retaining legacy keys and existing ranked fields."""
    state_path, tracker_path = Path(state_path), Path(tracker_path)
    observed = timestamp(now)
    if state_path.exists():
        document, seen = load_state(state_path)
        if seen is document:
            document = {"seen": seen}
    else:
        document, seen = {"seen": {}}, {}
        document["seen"] = seen
    if any(not isinstance(entry, dict) for entry in seen.values()):
        raise ValueError("history contains a non-object job; no data written")
    if not isinstance(jobs, list):
        raise ValueError("jobs must be a normalized job array")
    tracked = tracker_pairs(tracker_path)
    selected, updates, invalid = [], [], []
    duplicates = 0
    per_portal = {}
    for index, job in enumerate(jobs):
        try:
            if not isinstance(job, dict) or not text(job.get("title")) or not text(job.get("portal")):
                raise ValueError("normalized job needs title and portal")
            url = canonical_url(job.get("url"))
            if job.get("status") not in ("new", "expired") or job.get("source") not in ("cli", "manual", "websearch"):
                raise ValueError("normalized job has invalid status or source")
            last_seen = timestamp(job.get("last_seen") or observed)
        except ValueError as exc:
            invalid.append({"index": index, "error": str(exc)})
            continue
        incoming_ids = _identities(job)
        metrics = per_portal.setdefault(job["portal"], {"jobs_discovered": 0, "duplicates_removed": 0, "shortlisted": 0})
        metrics["jobs_discovered"] += 1
        match = None
        for key, entry in seen.items():
            existing_ids = _identities(entry)
            same_id = bool(incoming_ids & existing_ids)
            conflicting_id = any(a[0] == b[0] and a[1] != b[1] for a in incoming_ids for b in existing_ids)
            legacy_pair = not existing_ids and text(entry.get("company")) and text(job.get("company")) and (
                norm(entry.get("company")), norm(entry.get("title"))) == (norm(job.get("company")), norm(job.get("title")))
            if same_id or (_url(entry) == url and not conflicting_id) or legacy_pair:
                match = key
                break
        if match is not None:
            entry = seen[match]
            entry["last_seen"] = max(entry.get("last_seen") or last_seen, last_seen)
            provenance = {"portal": job["portal"], "job_id": job.get("job_id"), "url": url,
                          "original_url": job.get("original_url"), "source": job["source"]}
            sources = entry.setdefault("discovery_sources", [])
            if not isinstance(sources, list):
                raise ValueError("invalid discovery_sources in history; no data written")
            if provenance not in sources:
                sources.append(provenance)
            for field in ("description", "salary", "employment_type", "experience", "application_url", "posting_date", "posted_date", "date", "updated_at", "deadline", "expires_at", "posting_guard", "date_meaning", "source_metadata"):
                if entry.get(field) is None and job.get(field) is not None:
                    entry[field] = job[field]
            if job["status"] == "expired":
                entry["status"] = "expired"
                entry["expires_at"] = job.get("expires_at")
            updates.append(match)
            duplicates += 1
            metrics["duplicates_removed"] += 1
        elif text(job.get("company")) and (norm(job["company"]), norm(job["title"])) in tracked:
            duplicates += 1
            metrics["duplicates_removed"] += 1
        else:
            key = make_key(job.get("company"), job["title"], url)
            identity = f"{job['portal']}|{job.get('job_id') or url}"
            if incoming_ids or key in seen:
                key += "-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
            if key in seen:
                invalid.append({"index": index, "error": "conflicting stable identity"})
                continue
            seen[key] = {**job, "url": url, "last_seen": last_seen}
            selected.append(key)
    statuses = document.setdefault("portal_status", {})
    if not isinstance(statuses, dict):
        raise ValueError("invalid portal_status history; no data written")
    for entry in seen.values():
        if is_shortlisted(entry):
            for portal in {entry.get("portal"), *(s.get("portal") for s in entry.get("discovery_sources", []) if isinstance(s, dict))} - {None}:
                per_portal.setdefault(portal, {"jobs_discovered": 0, "duplicates_removed": 0, "shortlisted": 0})["shortlisted"] += 1
    for portal, update in (portal_updates or {}).items():
        prior = statuses.get(portal, {})
        if not isinstance(prior, dict) or not isinstance(update, dict):
            raise ValueError("invalid portal status update")
        merged = {**prior, **update}
        if not update.get("last_success") and prior.get("last_success"):
            merged["last_success"] = prior["last_success"]
        metrics = per_portal.get(portal, {"duplicates_removed": 0, "shortlisted": 0})
        merged.update({key: metrics[key] for key in ("duplicates_removed", "shortlisted")})
        statuses[portal] = merged
    if jobs or portal_updates:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        save_state(state_path, document)
    shortlisted = sum(is_shortlisted(entry) for entry in seen.values())
    return {"added": selected, "updated": list(dict.fromkeys(updates)), "duplicates_removed": duplicates,
            "invalid": invalid, "shortlisted": shortlisted, "per_portal": per_portal}
