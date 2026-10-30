#!/usr/bin/env python3
"""Multi-platform job discovery with strict freshness, scoring and dedup.

Discovery only: no command signs in, creates accounts, applies, or submits
forms. Each platform adapter returns raw listings plus an explicit status
(supported / partial / blocked / failed) so a source that could not be read is
never reported as "zero jobs".

Platforms and access method:
  linkedin      installed linkedin-search CLI (guest search pages)  partial
  greenhouse    boards-api.greenhouse.io public Job Board API        supported
  lever         api.lever.co/v0/postings public Postings API         supported
  ashby         api.ashbyhq.com posting-api public job board API     supported
  zoho_recruit  configured public careers pages (robots-gated)       partial
  apna          blocked: apna.co User Agreement 7.1(d)-(e) forbids automated retrieval

Commands:
  python tools/job_discovery.py run [--platforms a,b] [--resume] [--config PATH]
  python tools/job_discovery.py report [--date YYYY-MM-DD]
"""

import argparse
import csv
import hashlib
import html
import json
import logging
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
DEFAULT_CONFIG = Path(__file__).with_name("discovery_config.json")
USER_AGENT = "mdshahansha/automated-switch-apply/1.0 (job-discovery)"
LINKEDIN_CLI = ".agents/skills/linkedin-search/cli/src/cli.ts"
FUTURE_SKEW = timedelta(minutes=5)
MAX_TZ_OFFSET = timedelta(hours=14)

INDIA_PLACES = ["india", "kolkata", "bengaluru", "bangalore", "mumbai", "pune", "hyderabad",
                "chennai", "delhi", "gurugram", "gurgaon", "noida", "ahmedabad", "jaipur",
                "kochi", "indore", "chandigarh", "coimbatore", "thiruvananthapuram", "bhubaneswar",
                "navi mumbai", "mohali", "nagpur", "vadodara", "lucknow", "mysore", "mysuru"]

log = logging.getLogger("job_discovery")


# ---------------------------------------------------------------- utilities

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") if dt else None


def strip_html(text):
    if not text:
        return ""
    text = html.unescape(str(text))
    text = re.sub(r"<(br|/p|/li|/div|/h\d)[^>]*>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"[ \t\r\f\v]+", " ", re.sub(r"\n\s*\n+", "\n", text)).strip()


def norm(text):
    text = (text or "").lower()
    text = re.sub(r"\b(private|pvt|limited|ltd|inc|llc|llp|technologies|technology|solutions|corp|co)\b\.?", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def http_get(url, timeout, retries, accept="application/json"):
    """GET with retries and exponential backoff. Raises on final failure.

    4xx other than 429 is not retried: a missing board stays missing."""
    last = None
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            last = e
            if e.code != 429 and 400 <= e.code < 500:
                raise
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
        if attempt < retries:
            time.sleep(1.5 * (2 ** attempt))
    raise last


# ---------------------------------------------------------------- freshness

_REL = re.compile(r"(\d+|an?|one)\s*(minute|min|hour|hr|day|week|month)s?\s+ago", re.I)


def parse_relative(label):
    m = _REL.search(label or "")
    if not m:
        if re.search(r"\b(just now|today|few (minutes|hours) ago)\b", label or "", re.I):
            return timedelta(0)
        return None
    n = m.group(1).lower()
    n = 1 if n in ("a", "an", "one") else int(n)
    unit = m.group(2).lower()
    scale = {"minute": timedelta(minutes=1), "min": timedelta(minutes=1), "hour": timedelta(hours=1),
             "hr": timedelta(hours=1), "day": timedelta(days=1), "week": timedelta(weeks=1),
             "month": timedelta(days=30)}[unit]
    return n * scale


def classify_freshness(raw, collected_at, window_hours=24):
    """Return (freshness, normalized, confidence).

    freshness: confirmed_fresh | stale | uncertain | date_unverified | invalid_future
    confidence: exact | date_only | relative | no_timezone | none
    Only an exact, timezone-aware timestamp can yield confirmed_fresh."""
    window = timedelta(hours=window_hours)
    if raw is None or (isinstance(raw, str) and raw.strip() in ("", "None", "null")):
        return "date_unverified", None, "none"
    ts = None
    if isinstance(raw, (int, float)) or (isinstance(raw, str) and re.fullmatch(r"\d{12,14}", raw.strip())):
        ts = datetime.fromtimestamp(int(raw) / 1000, tz=timezone.utc)
    elif isinstance(raw, str):
        s = raw.strip()
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            day = datetime.strptime(s, "%Y-%m-%d").date()
            # A calendar date in an unknown zone may end up to 14h after UTC
            # midnight; it is provably stale only if that latest instant is
            # already outside the window.
            latest = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1) + MAX_TZ_OFFSET
            if latest < collected_at - window:
                return "stale", s, "date_only"
            return "uncertain", s, "date_only"
        try:
            parsed = datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            delta = parse_relative(s)
            if delta is None:
                return "date_unverified", None, "none"
            # Relative labels are rounded ("1 day ago" can mean 47h).
            return ("stale" if delta >= timedelta(days=2) else "uncertain"), None, "relative"
        if parsed.tzinfo is None:
            if parsed < (collected_at - window - MAX_TZ_OFFSET).replace(tzinfo=None):
                return "stale", s, "no_timezone"
            return "uncertain", s, "no_timezone"
        ts = parsed
    if ts is None:
        return "date_unverified", None, "none"
    delta = collected_at - ts
    if delta < -FUTURE_SKEW:
        return "invalid_future", iso(ts), "exact"
    return ("confirmed_fresh" if delta <= window else "stale"), iso(ts), "exact"


# ---------------------------------------------------------------- scoring

def _has(text, term):
    term = term.lower()
    if term.strip() != term:  # padded terms like " go " match on spaces
        return term in f" {text} "
    return re.search(r"(?<![a-z0-9])" + re.escape(term) + r"(?![a-z0-9])", text) is not None


def parse_years(text):
    """Minimum years from the first experience range the posting states, or None.

    The first mention is usually the headline requirement; later ones tend to
    be per-skill asides ("1 year of Docker") that would understate it."""
    for m in re.finditer(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years|yrs|year)", text, re.I):
        lo = int(m.group(1))
        if lo <= 25:
            return lo
    return None


def _title_excluded(title, cfg):
    padded = f" {title} "
    return next((t.strip() for t in cfg["profile"]["excludeTitles"]
                 if (t in padded if t.strip() != t else _has(title, t))), None)


def score_job(job, cfg):
    """0-100 relevance with breakdown, evidence and hard exclusions."""
    p, th = cfg["profile"], cfg["thresholds"]
    title = (job.get("jobTitle") or "").lower()
    desc = (job.get("description") or "").lower()
    loc = (job.get("location") or "").lower()
    mode = (job.get("workMode") or "").lower()
    reasons, exclusions, bd = [], [], {}

    hit = _title_excluded(title, cfg)
    if hit:
        exclusions.append(f"title excluded ({hit})")
    if any(_has(title, t) for t in p["coreTitles"]):
        bd["title"] = 30
        reasons.append("title matches a core target role")
    elif any(_has(title, t) for t in p["targetTitles"]):
        bd["title"] = 20
        reasons.append("title is adjacent to target roles")
    elif _has(title, "engineer") or _has(title, "developer"):
        bd["title"] = 8
    else:
        bd["title"] = 0
        exclusions.append("unrelated occupation")

    prim = [s for s in p["primarySkills"] if _has(desc, s) or _has(title, s)]
    sec = [s for s in p["secondarySkills"] if _has(desc, s) or _has(title, s)]
    foreign = [s.strip() for s in p["foreignStacks"] if _has(desc, s) or _has(title, s)]
    skills = min(20, 3 * len(prim)) + min(5, len(sec))
    title_foreign = [s.strip() for s in p["foreignStacks"] if _has(title, s)]
    if title_foreign:
        # A stack named in the title is a mandatory requirement, not a keyword.
        bd["title"] = max(0, bd["title"] - 15)
        reasons.append("title requires " + ", ".join(title_foreign))
    if foreign and len(prim) <= 1 and len(foreign) >= 2:
        skills = min(skills, 5)
        reasons.append("core stack appears to be " + ", ".join(foreign[:3]))
    if not desc:
        skills = min(skills, 10)
        reasons.append("no description; skills scored from title only")
    bd["skills"] = skills
    if prim or sec:
        reasons.append("skills: " + ", ".join(prim[:8] + sec[:4]))

    years = parse_years(desc) if desc else None
    if years is None:
        bd["experience"] = 7 if "senior" in title else 9
    elif years <= p["experienceYears"]:
        bd["experience"] = 15
        reasons.append(f"asks {years}+ yrs (fits ~{p['experienceYears']})")
    elif years <= p["maxRequiredYears"]:
        bd["experience"] = 9
        reasons.append(f"asks {years}+ yrs (stretch)")
    else:
        bd["experience"] = 0
        reasons.append(f"asks {years}+ yrs (exceeds profile)")
        if years >= p["maxRequiredYears"] + 2:
            exclusions.append(f"requires {years}+ years")

    remote = "remote" in mode or "remote" in loc
    # Description evidence only counts when the location names no place at
    # all; boilerplate like "we hire in India, US..." must not make a
    # "Remote - US" role look India-eligible.
    bare_remote = re.sub(r"[^a-z]+", " ", loc).strip() in ("", "remote", "anywhere", "worldwide")
    in_india = any(_has(loc, c) for c in INDIA_PLACES) or (remote and bare_remote and "india" in desc)
    home = any(_has(loc, c) for c in p["homeLocations"])
    if not loc:
        bd["location"] = 5
        reasons.append("location not stated")
    elif home:
        bd["location"] = 15
        reasons.append("home location")
    elif in_india:
        bd["location"] = 15 if remote else 12
        reasons.append("India " + ("remote" if remote else "location"))
    elif remote:
        bd["location"] = 0
        exclusions.append("remote but India eligibility not explicit")
    else:
        bd["location"] = 0
        exclusions.append("outside India")

    et = (job.get("employmentType") or "").lower()
    if "intern" in et:
        exclusions.append("internship")
        bd["employment"] = 0
    elif "full" in et or et == "permanent":
        bd["employment"] = 5
    elif "contract" in et or "temp" in et:
        bd["employment"] = 3
    elif "part" in et:
        bd["employment"] = 1
    else:
        bd["employment"] = 3

    q = 0
    if len(desc) > 600:
        q += 5
    elif len(desc) > 150:
        q += 2
    if job.get("applicationUrl") or job.get("canonicalJobUrl"):
        q += 2
    if job.get("status") == "open":
        q += 3
    bd["quality"] = q
    if job.get("status") == "closed":
        exclusions.append("closed")

    score = sum(bd.values())
    if exclusions:
        category = "excluded"
    elif score >= th["high"]:
        category = "high_match"
    elif score >= th["medium"]:
        category = "medium_match"
    else:
        category = "low_match"
    return {"relevanceScore": score, "relevanceCategory": category, "scoreBreakdown": bd,
            "matchReasons": reasons, "exclusionReasons": exclusions,
            "requiredSkills": sorted(set(prim + sec + foreign)),
            "experienceRequirements": f"{years}+ years" if years is not None else job.get("experienceRequirements")}


def title_passes(title, cfg):
    """Cheap pre-filter before spending a detail request."""
    t = (title or "").lower()
    if _title_excluded(t, cfg):
        return False
    return any(_has(t, x) for x in cfg["profile"]["targetTitles"])


# ---------------------------------------------------------------- model

def make_job(platform, **kw):
    job = {"sourcePlatform": platform, "sourceJobId": None, "jobTitle": None, "companyName": None,
           "location": None, "workMode": None, "employmentType": None, "experienceRequirements": None,
           "description": "", "postedAtRaw": None, "status": "unknown", "canonicalJobUrl": None,
           "applicationUrl": None}
    job.update({k: v for k, v in kw.items() if v is not None})
    return job


def validate(job):
    return [f for f in ("jobTitle", "companyName", "canonicalJobUrl") if not job.get(f)]


def dedup_key(job):
    return "|".join([norm(job.get("companyName")), norm(job.get("jobTitle")), norm(job.get("location"))])


def job_id(job):
    if job.get("sourceJobId"):
        return f"{job['sourcePlatform']}:{job['sourceJobId']}"
    return f"{job['sourcePlatform']}:url:" + hashlib.sha1((job.get("canonicalJobUrl") or "").encode()).hexdigest()[:16]


def deduplicate(jobs):
    """Merge only on identical id / canonical URL, or identical normalized
    company+title+location across different platforms. Same company+title in
    another location is flagged for review, never merged."""
    by_id, by_url, by_key, out = {}, {}, {}, []
    dup_count = 0
    for job in jobs:
        url = (job.get("canonicalJobUrl") or "").rstrip("/").lower()
        target = by_id.get(job["id"]) or (by_url.get(url) if url else None)
        key = job["deduplicationKey"]
        if not target and key in by_key and all(key.split("|")):
            cand = by_key[key]
            if cand["sourcePlatform"] != job["sourcePlatform"]:
                target = cand
        if target:
            dup_count += 1
            for src in job["sources"]:
                if src not in target["sources"]:
                    target["sources"].append(src)
            if not target.get("description") and job.get("description"):
                target["description"] = job["description"]
            continue
        by_id[job["id"]] = job
        if url:
            by_url[url] = job
        by_key.setdefault(key, job)
        out.append(job)
    groups = {}
    for job in out:
        groups.setdefault("|".join(job["deduplicationKey"].split("|")[:2]), []).append(job)
    for group in groups.values():
        if len(group) > 1 and len({j["sourcePlatform"] for j in group}) > 1:
            for j in group:
                j["possibleDuplicateOf"] = [o["id"] for o in group if o is not j]
    return out, dup_count


# ---------------------------------------------------------------- adapters

class Adapter:
    name = ""
    method = ""

    def __init__(self, cfg):
        self.cfg = cfg
        self.timeout = cfg.get("requestTimeoutSeconds", 20)
        self.retries = cfg.get("retries", 2)

    def units(self):
        """Independent work units; each is checkpointed separately."""
        return []

    def collect(self, unit):
        raise NotImplementedError

    def get_json(self, url):
        return json.loads(http_get(url, self.timeout, self.retries))


class GreenhouseAdapter(Adapter):
    name, method = "greenhouse", "Greenhouse Job Board API (boards-api.greenhouse.io)"

    def units(self):
        return self.cfg.get("greenhouse", {}).get("boards", [])

    def collect(self, board):
        data = self.get_json(f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs?content=true")
        jobs = []
        for j in data.get("jobs", []):
            # first_published is the original publication time; updated_at is
            # an edit time and must never stand in for it.
            jobs.append(make_job(
                self.name, sourceJobId=str(j.get("id")), jobTitle=j.get("title"),
                companyName=j.get("company_name") or board, location=(j.get("location") or {}).get("name"),
                description=strip_html(j.get("content")), postedAtRaw=j.get("first_published"),
                canonicalJobUrl=j.get("absolute_url"), applicationUrl=j.get("absolute_url"),
                status="open", updatedAt=j.get("updated_at")))
        return jobs


class LeverAdapter(Adapter):
    name, method = "lever", "Lever Postings API (api.lever.co/v0/postings)"

    def units(self):
        return self.cfg.get("lever", {}).get("companies", [])

    def collect(self, company):
        data = self.get_json(f"https://api.lever.co/v0/postings/{company}?mode=json")
        jobs = []
        for j in data:
            cat = j.get("categories") or {}
            parts = [j.get("descriptionPlain") or strip_html(j.get("description"))]
            for lst in j.get("lists") or []:
                parts.append(f"{lst.get('text', '')}\n{strip_html(lst.get('content'))}")
            parts.append(j.get("additionalPlain") or "")
            locs = cat.get("allLocations") or [cat.get("location")]
            jobs.append(make_job(
                self.name, sourceJobId=j.get("id"), jobTitle=j.get("text"), companyName=company,
                location=", ".join(x for x in locs if x) or None, workMode=j.get("workplaceType"),
                employmentType=cat.get("commitment"), description="\n".join(p for p in parts if p).strip(),
                # createdAt (epoch ms) is the only posting time Lever exposes.
                postedAtRaw=j.get("createdAt"), canonicalJobUrl=j.get("hostedUrl"),
                applicationUrl=j.get("applyUrl"), status="open"))
        return jobs


class AshbyAdapter(Adapter):
    name, method = "ashby", "Ashby public Job Board API (api.ashbyhq.com/posting-api)"

    def units(self):
        return self.cfg.get("ashby", {}).get("boards", [])

    def collect(self, board):
        data = self.get_json(f"https://api.ashbyhq.com/posting-api/job-board/{board}")
        jobs = []
        for j in data.get("jobs", []):
            if j.get("isListed") is False:
                continue
            locs = [j.get("location")] + [s.get("location") for s in j.get("secondaryLocations") or []]
            mode = j.get("workplaceType") or ("Remote" if j.get("isRemote") else None)
            jobs.append(make_job(
                self.name, sourceJobId=j.get("id"), jobTitle=j.get("title"), companyName=board,
                location=", ".join(x for x in locs if x) or None, workMode=mode,
                employmentType=j.get("employmentType"),
                description=j.get("descriptionPlain") or strip_html(j.get("descriptionHtml")),
                postedAtRaw=j.get("publishedAt"), canonicalJobUrl=j.get("jobUrl"),
                applicationUrl=j.get("applyUrl"), status="open"))
        return jobs


class ZohoRecruitAdapter(Adapter):
    name, method = "zoho_recruit", "configured public Zoho Recruit careers pages (HTML, robots-gated)"

    def units(self):
        return self.cfg.get("zoho_recruit", {}).get("careerPages", [])

    def collect(self, page):
        from robots_check import gate
        code, verdict = gate(page)
        if code != 0:
            raise PermissionError(f"robots.txt: {verdict}")
        body = html.unescape(http_get(page, self.timeout, self.retries, accept="text/html"))
        return parse_zoho(body, page, self.name)


def parse_zoho(body, page, platform="zoho_recruit"):
    tenant = re.sub(r"^https?://([^.]+)\..*$", r"\1", page)
    jobs = []
    for m in re.finditer(r'<input type="hidden" value="(\[\{.*?\}\])"', body, re.S):
        try:
            rows = json.loads(m.group(1))
        except ValueError:
            continue
        if not rows or not isinstance(rows[0], dict) or "Posting_Title" not in rows[0]:
            continue
        for r in rows:
            if r.get("Publish") is False:
                continue
            url = page.rstrip("/") + "/" + str(r.get("id"))
            # The public career-site payload carries no publication date.
            jobs.append(make_job(
                platform, sourceJobId=str(r.get("id")), jobTitle=r.get("Posting_Title"),
                companyName=r.get("Account_Name") or tenant,
                location=", ".join(x for x in (r.get("City"), r.get("State"), r.get("Country")) if x) or None,
                workMode="remote" if r.get("Remote_Job") else None, employmentType=r.get("Job_Type"),
                postedAtRaw=r.get("Date_Opened"), canonicalJobUrl=url, applicationUrl=url, status="open"))
    return jobs


class LinkedInAdapter(Adapter):
    name, method = "linkedin", "installed linkedin-search CLI (public guest job search)"

    def units(self):
        li = self.cfg.get("linkedin", {})
        return [{"query": q, **s} for q in li.get("queries", []) for s in li.get("searches", [])]

    def _cli(self, *args):
        # Windows installs bun as bun.CMD, which subprocess only finds via which().
        bun = shutil.which("bun")
        if not bun:
            raise RuntimeError("bun not found on PATH")
        r = subprocess.run([bun, "run", LINKEDIN_CLI, *args], cwd=ROOT, capture_output=True,
                           text=True, encoding="utf-8", errors="replace", timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"linkedin-search exit {r.returncode}: {r.stderr.strip()[:200]}")
        return json.loads(r.stdout)

    def collect(self, unit):
        args = ["search", "-q", unit["query"], "-l", unit["location"], "--jobage-minutes",
                str(int(self.cfg["freshnessWindowHours"] * 60)), "-n",
                str(self.cfg["linkedin"].get("perQueryLimit", 25)), "--format", "json"]
        if unit.get("remote"):
            args += ["--remote", unit["remote"]]
        data = self._cli(*args)
        jobs = []
        for j in data.get("results", []):
            # Search cards carry a calendar date only, so freshness is at best
            # "uncertain" even though the query used LinkedIn's 24h filter.
            url = f"https://www.linkedin.com/jobs/view/{j.get('id')}"
            jobs.append(make_job(
                self.name, sourceJobId=j.get("id"), jobTitle=j.get("title"), companyName=j.get("company"),
                location=j.get("location"), workMode=unit.get("remote"), postedAtRaw=j.get("date"),
                canonicalJobUrl=url, applicationUrl=url,
                platformFilter="posted within 24h (LinkedIn filter)"))
        return jobs

    def enrich(self, jobs):
        """Fetch details for title-passing hits, capped and sequential."""
        cap = self.cfg["linkedin"].get("maxDetails", 30)
        done = 0
        for job in jobs:
            if done >= cap or not title_passes(job["jobTitle"], self.cfg):
                continue
            try:
                d = self._cli("detail", job["sourceJobId"], "--format", "json")
            except Exception as e:  # noqa: BLE001 - isolate per-job failure
                job["detailError"] = str(e)[:200]
                continue
            done += 1
            job["description"] = d.get("description") or ""
            job["employmentType"] = d.get("employmentType")
            job["seniority"] = d.get("seniority")
            if d.get("isActive") is False:
                job["status"] = "closed"
            elif d.get("isActive") is True:
                job["status"] = "open"
            time.sleep(1.0)
        return jobs


class ApnaAdapter(Adapter):
    name, method = "apna", "none"
    blocked = ("apna.co User Agreement sections 7.1(d)-(e) prohibit automated monitoring and "
               "systematic retrieval (recorded in .agents/skills/apna-search/SKILL.md); "
               "use that skill's manual browser workflow instead")


ADAPTERS = {a.name: a for a in (LinkedInAdapter, GreenhouseAdapter, AshbyAdapter,
                                 ZohoRecruitAdapter, ApnaAdapter, LeverAdapter)}
PLATFORM_NOTES = {
    "linkedin": "covers only the configured queries; cards carry a date, not a timestamp, so nothing is confirmed",
    "zoho_recruit": "configured tenants only; public payload has no publication date",
    "greenhouse": "configured company boards only; no cross-company search API",
    "lever": "configured company boards only; createdAt used as posting time",
    "ashby": "configured company boards only; no cross-company search API",
}


# ---------------------------------------------------------------- pipeline

def load_config(path=None):
    return json.loads(Path(path or DEFAULT_CONFIG).read_text(encoding="utf-8"))


def finalize(job, collected_at, cfg):
    fresh, posted, conf = classify_freshness(job.get("postedAtRaw"), collected_at, cfg["freshnessWindowHours"])
    job.update({"postedAt": posted, "postedAtConfidence": conf, "freshness": fresh,
                "collectedAt": iso(collected_at)})
    job["id"] = job_id(job)
    job["deduplicationKey"] = dedup_key(job)
    job["sources"] = [{"platform": job["sourcePlatform"], "url": job.get("canonicalJobUrl"),
                       "sourceJobId": job.get("sourceJobId")}]
    job.update(score_job(job, cfg))
    return job


def run_platform(adapter, cfg, checkpoint, save_checkpoint):
    """Run one platform; every unit failure is recorded, never raised."""
    st = {"platform": adapter.name, "method": adapter.method, "units": 0, "unitsOk": 0,
          "rawListings": 0, "errors": []}
    if isinstance(adapter, ApnaAdapter):
        st.update(status="blocked", reason=adapter.blocked)
        return [], st
    units = adapter.units()
    if not units:
        st.update(status="blocked", reason="no boards/queries configured")
        return [], st
    st["units"] = len(units)
    done = checkpoint.setdefault(adapter.name, {})

    def one(unit):
        key = json.dumps(unit, sort_keys=True)
        if key in done:
            return done[key], None
        try:
            return adapter.collect(unit), None
        except urllib.error.HTTPError as e:
            return None, f"HTTP {e.code} {e.reason}"
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {str(e)[:160]}"

    # LinkedIn goes through one CLI at a time to stay polite.
    workers = 1 if isinstance(adapter, LinkedInAdapter) else max(1, cfg.get("concurrency", 4))
    jobs = []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for unit, (got, err) in zip(units, ex.map(one, units)):
            key = json.dumps(unit, sort_keys=True)
            if err:
                st["errors"].append({"unit": unit, "error": err})
                log.warning("%s %s failed: %s", adapter.name, unit, err)
                continue
            st["unitsOk"] += 1
            if key not in done:
                done[key] = got
                save_checkpoint()
            jobs.extend(got)
    st["rawListings"] = len(jobs)
    if isinstance(adapter, LinkedInAdapter) and jobs:
        seen, uniq = set(), []
        for j in jobs:
            if j["sourceJobId"] not in seen:
                seen.add(j["sourceJobId"])
                uniq.append(j)
        jobs = adapter.enrich(uniq)
    if st["unitsOk"] == 0:
        st["status"] = "failed"
    elif st["errors"] or adapter.name in ("linkedin", "zoho_recruit"):
        st["status"] = "partial"
    else:
        st["status"] = "supported"
    st["reason"] = PLATFORM_NOTES.get(adapter.name)
    return jobs, st


def update_store(path, jobs, now_iso):
    """Persist firstSeenAt across reruns, keyed by stable job id."""
    store = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for job in jobs:
        prev = store.get(job["id"])
        job["firstSeenAt"] = prev["firstSeenAt"] if prev else now_iso
        job["lastSeenAt"] = now_iso
        store[job["id"]] = {k: job.get(k) for k in ("firstSeenAt", "lastSeenAt", "jobTitle", "companyName",
                                                      "canonicalJobUrl", "postedAt", "relevanceScore")}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


FRESH_ORDER = {"confirmed_fresh": 0, "uncertain": 1, "date_unverified": 2, "stale": 3, "invalid_future": 4}
CSV_FIELDS = ["id", "freshness", "relevanceCategory", "relevanceScore", "jobTitle", "companyName", "location",
              "workMode", "employmentType", "experienceRequirements", "postedAt", "postedAtConfidence",
              "postedAtRaw", "collectedAt", "sourcePlatform", "sourceJobId", "canonicalJobUrl",
              "applicationUrl", "status", "requiredSkills", "matchReasons", "exclusionReasons",
              "scoreBreakdown", "sources", "possibleDuplicateOf", "deduplicationKey", "firstSeenAt", "lastSeenAt"]


def _posted_ts(job):
    if job.get("postedAtConfidence") == "exact" and job.get("postedAt"):
        return datetime.fromisoformat(job["postedAt"].replace("Z", "+00:00")).timestamp()
    return 0


def sort_jobs(jobs):
    """Verified freshness, then relevance, then newest posting first."""
    return sorted(jobs, key=lambda j: (FRESH_ORDER.get(j["freshness"], 9), -j["relevanceScore"], -_posted_ts(j)))


def write_csv(path, jobs):
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for j in jobs:
            w.writerow({k: (json.dumps(j.get(k), ensure_ascii=False) if isinstance(j.get(k), (list, dict)) else j.get(k))
                        for k in CSV_FIELDS})


def run(cfg, platforms=None, resume=False):
    started = time.monotonic()
    collected_at = utc_now()
    out_dir = ROOT / cfg["outputDir"] / collected_at.strftime("%Y-%m-%d")
    out_dir.mkdir(parents=True, exist_ok=True)
    cp_path = out_dir / "checkpoint.json"
    checkpoint = json.loads(cp_path.read_text(encoding="utf-8")) if resume and cp_path.exists() else {}
    if checkpoint.get("collectedAt"):
        # A resumed run keeps the original reference time so units collected
        # before the interruption are judged against the same window.
        collected_at = datetime.fromisoformat(checkpoint["collectedAt"].replace("Z", "+00:00"))
    checkpoint["collectedAt"] = iso(collected_at)

    def save_cp():
        tmp = cp_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(checkpoint, ensure_ascii=False), encoding="utf-8")
        tmp.replace(cp_path)

    enabled = [p for p in cfg["enabledPlatforms"] if not platforms or p in platforms]
    raw, statuses, malformed = [], [], []
    for name in enabled:
        try:
            jobs, st = run_platform(ADAPTERS[name](cfg), cfg, checkpoint, save_cp)
        except Exception as e:  # noqa: BLE001 - one platform never stops the run
            jobs, st = [], {"platform": name, "status": "failed", "errors": [{"error": f"{type(e).__name__}: {e}"}]}
        for j in jobs:
            miss = validate(j)
            if miss:
                malformed.append({"platform": name, "missing": miss, "sourceJobId": j.get("sourceJobId")})
            else:
                raw.append(finalize(j, collected_at, cfg))
        st["normalized"] = sum(1 for j in raw if j["sourcePlatform"] == name)
        statuses.append(st)
        log.info("%s: %s, %d listings", name, st["status"], st["normalized"])

    jobs, dup_count = deduplicate(raw)
    update_store(ROOT / cfg["storePath"], jobs, iso(collected_at))
    jobs = sort_jobs(jobs)
    relevant = [j for j in jobs if j["relevanceCategory"] != "excluded"
                and j["relevanceScore"] >= cfg["thresholds"].get("minimumScore", 0)]
    confirmed = [j for j in relevant if j["freshness"] == "confirmed_fresh"]
    review = [j for j in relevant if j["freshness"] in ("uncertain", "date_unverified")]

    for nm, data in (("confirmed_fresh", confirmed), ("review_date_unverified", review), ("all_jobs", jobs)):
        (out_dir / f"{nm}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        write_csv(out_dir / f"{nm}.csv", data)

    def count(seq, key, val):
        return sum(1 for j in seq if j.get(key) == val)

    report = {
        "collectedAt": iso(collected_at), "durationSeconds": round(time.monotonic() - started, 1),
        "freshnessWindowHours": cfg["freshnessWindowHours"],
        "totalDiscovered": len(raw), "uniqueAfterDedup": len(jobs), "duplicates": dup_count,
        "confirmedFreshRelevant": len(confirmed),
        "reviewUncertainOrUnverified": len(review),
        "confirmedFreshAll": count(jobs, "freshness", "confirmed_fresh"),
        "dateUnverifiedAll": count(jobs, "freshness", "date_unverified"),
        "uncertainAll": count(jobs, "freshness", "uncertain"),
        "staleAll": count(jobs, "freshness", "stale"),
        "excluded": count(jobs, "relevanceCategory", "excluded"),
        "closed": count(jobs, "status", "closed"),
        "matchCounts": {c: count(relevant, "relevanceCategory", c) for c in ("high_match", "medium_match", "low_match")},
        "malformed": malformed, "platforms": statuses, "outputDir": out_dir.relative_to(ROOT).as_posix(),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return report, confirmed, review


def print_summary(report, confirmed, review, out=sys.stdout):
    w = out.write
    w(f"\nCollected {report['collectedAt']} in {report['durationSeconds']}s "
      f"(window {report['freshnessWindowHours']}h)\n\n")
    w(f"{'platform':<14}{'status':<11}{'units ok':<10}{'listings':<10}errors\n")
    for st in report["platforms"]:
        units = f"{st.get('unitsOk', 0)}/{st.get('units', 0)}"
        w(f"{st['platform']:<14}{st['status']:<11}{units:<10}{st.get('normalized', 0):<10}{len(st.get('errors', []))}\n")
        if st.get("reason"):
            w(f"{'':<14}note: {st['reason']}\n")
        for e in st.get("errors", [])[:5]:
            w(f"{'':<14}! {e.get('unit', '')} {e['error']}\n")
    w(f"\ntotal {report['totalDiscovered']} | unique {report['uniqueAfterDedup']} | duplicates {report['duplicates']}"
      f" | confirmed<24h (any fit) {report['confirmedFreshAll']} | stale {report['staleAll']}"
      f" | date-unverified {report['dateUnverifiedAll']} | excluded {report['excluded']} | closed {report['closed']}\n")
    m = report["matchCounts"]
    w(f"relevant: confirmed fresh {report['confirmedFreshRelevant']} | review (uncertain/unverified date) "
      f"{report['reviewUncertainOrUnverified']} | high {m['high_match']} medium {m['medium_match']} low {m['low_match']}\n")
    for label, rows in (("CONFIRMED <24h", confirmed), ("REVIEW (date not verified), top 25", review[:25])):
        w(f"\n{label}\n")
        for j in rows:
            w(f"  {j['relevanceScore']:>3} {j['relevanceCategory'][:6]:<7}{j['freshness'][:10]:<11}"
              f"{(j['jobTitle'] or '')[:42]:<43}{(j['companyName'] or '')[:18]:<19}{(j['location'] or '')[:24]:<25}"
              f"{j['canonicalJobUrl']}\n")
    w(f"\nsaved to {report['outputDir']}/\n")


def main(argv=None):
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--config")
    r.add_argument("--platforms", help="comma-separated subset")
    r.add_argument("--resume", action="store_true", help="reuse today's checkpoint")
    rep = sub.add_parser("report")
    rep.add_argument("--config")
    rep.add_argument("--date")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        stream=sys.stderr)
    cfg = load_config(args.config)
    if args.cmd == "run":
        plats = set(args.platforms.split(",")) if args.platforms else None
        unknown = (plats or set()) - set(ADAPTERS)
        if unknown:
            ap.error(f"unknown platforms: {', '.join(sorted(unknown))}")
        report, confirmed, review = run(cfg, plats, args.resume)
        print_summary(report, confirmed, review)
        return 0
    d = ROOT / cfg["outputDir"] / (args.date or utc_now().strftime("%Y-%m-%d"))
    report = json.loads((d / "report.json").read_text(encoding="utf-8"))
    confirmed = json.loads((d / "confirmed_fresh.json").read_text(encoding="utf-8"))
    review = json.loads((d / "review_date_unverified.json").read_text(encoding="utf-8"))
    print_summary(report, confirmed, review)
    return 0


if __name__ == "__main__":
    sys.exit(main())
