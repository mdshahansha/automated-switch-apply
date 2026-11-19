"""One-shot LinkedIn last-24h scrape, filter and score.

Runs every enabled keyword card (tools/search_keywords.json) x location through
the linkedin-search CLI, merges jobs found by several cards (keeping which
cards found each), drops excluded stacks / tracker duplicates, fetches each
survivor's detail, scores it, and writes a compact CSV. Prints only a short
summary so an agent session spends few tokens.

Experience: a posting asking for more years than the candidate has is NOT
dropped on years alone - tools/experience_fit.py weighs years against stack
and role alignment (candidate advocacy). --max-years remains as an optional,
explicit hard cap and is off by default.

Usage: python tools/scrape_24h.py [--out DIR] [--min-score N] [--max-detail N]
                                  [--card ID ...] [--category ID] [--max-years N]
"""
import argparse
import csv
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from experience_fit import assess  # noqa: E402
from search_keywords import enabled_cards, get_card, load_cards, merge_discoveries  # noqa: E402

CLI = ".agents/skills/linkedin-search/cli/src/cli.ts"

LOCATIONS = ["India", "Kolkata, West Bengal, India", "Bengaluru, Karnataka, India",
             "Hyderabad, Telangana, India", "Pune, Maharashtra, India", "Delhi, India",
             "Mumbai, Maharashtra, India", "Chennai, Tamil Nadu, India"]

# Excluded stacks and non-engineering / people-management roles. Seniority words
# (senior, lead, staff, principal, architect) are NOT here: a senior title is a
# stretch to evaluate with experience_fit, not an automatic rejection.
TITLE_BAD = re.compile(
    r"intern|trainee|\.net|c#|php|\bsap\b|\bqa\b|test|data eng|data scien|flutter|golang|"
    r"\bgo\b|rust|ai/ml|machine learning|\bml\b|\bai engineer|manager|director|"
    r"head of|python|devops|salesforce|android|\bios\b|vue|"
    r"wordpress|shopify|ruby|django|embedded|sales|support|designer|c\+\+|campus",
    re.I)
LOC_OK = re.compile(r"india|remote", re.I)
# platforms the user never wants used (company name or description mention)
BLOCKED_PLATFORMS = re.compile(r"talent\s*500|sourcing\s*xpress|jobgether", re.I)
SKILLS = {"React": r"\bReact(?!\s*Native)", "React Native": r"React Native",
          "Node": r"\bNode", "Express": r"\bExpress", "TypeScript": r"TypeScript",
          "JavaScript": r"JavaScript", "MongoDB": r"MongoDB", "MySQL": r"MySQL",
          "PostgreSQL": r"Postgre", "Java": r"\bJava\b", "Spring": r"Spring",
          "Redis": r"Redis", "Kafka": r"Kafka", "Docker": r"Docker",
          "Next.js": r"Next\.?js", "REST": r"REST", "AWS": r"\bAWS\b"}
def cli(bun, *args):
    r = subprocess.run([bun, "run", CLI, *args], capture_output=True, text=True,
                       encoding="utf-8", cwd=ROOT)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None


def score(desc, title, loc):
    hits = [k for k, p in SKILLS.items() if re.search(p, desc)]
    tech = min(40, 6 * len(hits))
    fit = assess(desc, title, hits)
    exp = fit["experience_score"]
    yrs = fit["requirement"]["min_years"]
    role = 20 if re.search(r"full.?stack|mern|node|react|backend|software|sde|javascript|java",
                           title, re.I) else 10
    mode = "remote" if re.search(r"\bremote\b", desc, re.I) else \
        "hybrid" if re.search(r"\bhybrid\b", desc, re.I) else \
        "onsite" if re.search(r"on-?site|work from office|\bwfo\b", desc, re.I) else "not stated"
    place = 15 if mode == "remote" or "kolkata" in loc.lower() else 12
    sal = re.search(r"(?:₹|INR)\s?[\d,.]+\s*(?:-|–|to)?\s*(?:₹|INR)?\s?[\d,.]*\s*(?:LPA|Lakhs?|Lacs)?"
                    r"|\d+\s*(?:-|–)\s*\d+\s*(?:LPA|Lakhs?|Lacs)", desc, re.I)
    return tech + exp + role + place, yrs, mode, hits, sal.group(0).strip() if sal else "Not Disclosed", fit


def select_cards(card_ids, category):
    """Cards for this run: explicit --card ids (even if disabled), else enabled cards."""
    cards = load_cards()
    if card_ids:
        return [get_card(cards, cid) for cid in card_ids]
    return enabled_cards(cards, category)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=f"output/discovery/{dt.date.today()}")
    ap.add_argument("--min-score", type=int, default=70)
    ap.add_argument("--max-detail", type=int, default=80)
    ap.add_argument("--max-years", type=int, default=None,
                    help="optional hard cap: drop postings whose minimum years is at or above this "
                         "(off by default - years are weighed, not used to reject)")
    ap.add_argument("--card", action="append", default=[], help="search only this keyword card id (repeatable)")
    ap.add_argument("--category", help="search only this keyword category id")
    a = ap.parse_args()
    bun = shutil.which("bun")
    if not bun:
        sys.exit("bun not found on PATH")

    tracker = (ROOT / "job_search_tracker.csv").read_text(encoding="utf-8").lower()
    cards = select_cards(a.card, a.category)
    found = []
    for card in cards:
        jobs = []
        for loc in LOCATIONS:
            res = cli(bun, "search", "-q", card["keyword"], "-l", loc, "--jobage", "1")
            jobs.extend((res or {}).get("results", []))
        found.append((card, jobs))
    seen = {j["id"]: j for j in merge_discoveries(found)}

    keep = [j for j in seen.values()
            if not TITLE_BAD.search(j["title"] or "")
            and LOC_OK.search(j["location"] or "")
            and not BLOCKED_PLATFORMS.search(j["company"] or "")
            # T-Mobile (TMUS) India roles tagged [T500-...] are Talent500 postings
            and not re.search(r"\[T500-", j["title"] or "")
            and j["id"] not in tracker
            and (j["company"] or "").lower() not in tracker]
    keep.sort(key=lambda j: j["date"] or "", reverse=True)
    # same posting listed per city: keep first, note other cities
    uniq = {}
    for j in keep:
        k = ((j["company"] or "").lower(), (j["title"] or "").lower())
        if k in uniq:
            uniq[k]["location"] += " / " + (j["location"] or "").split(",")[0]
            for kw in j["discovered_keywords"]:
                if kw not in uniq[k]["discovered_keywords"]:
                    uniq[k]["discovered_keywords"].append(kw)
        else:
            uniq[k] = dict(j, location=j["location"] or "")
    keep = list(uniq.values())

    rows = []
    for j in keep[:a.max_detail]:
        d = cli(bun, "detail", j["id"], "--format", "json")
        desc = (d or {}).get("description") or ""
        if BLOCKED_PLATFORMS.search(desc):
            continue
        s, yrs, mode, hits, sal, fit = score(desc, j["title"], j["location"] or "")
        if fit["decision"] == "reject" or s < a.min_score:
            continue
        if a.max_years is not None and yrs is not None and yrs >= a.max_years:
            continue
        rows.append([j["date"], s, j["company"], j["title"],
                     f"{yrs}+ yrs" if yrs is not None else "Not stated",
                     fit["decision"], j["location"], mode, sal, ",".join(hits),
                     " | ".join(j["discovered_keywords"]),
                     f"https://www.linkedin.com/jobs/view/{j['id']}"])
    rows.sort(key=lambda r: (r[0] or "", r[1]), reverse=True)

    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    path = out / "jobs_24h_auto.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Posted", "Score", "Company", "Title", "Experience", "Fit", "Location",
                    "Work Mode", "Salary", "Matched Skills", "Found By", "Apply Link"])
        w.writerows(rows)
    print(f"cards={len(cards)} raw={len(seen)} filtered={len(keep)} detailed={min(len(keep), a.max_detail)} "
          f"kept={len(rows)} -> {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
