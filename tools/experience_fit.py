"""Candidate-advocacy experience evaluation for job postings.

Principle: an experience-years mismatch is a signal to evaluate, not a verdict.
A posting asking for more years than the candidate has stays eligible when the
technical stack and role align; it is rejected only when the overall fit is
poor (weak stack overlap AND an unrelated role), never on years alone.

Integrity: the candidate's own years come only from verified employment dates
(VERIFIED_EMPLOYMENT, from 01-candidate-profile.md). Nothing here inflates or
invents experience; form answers about total experience use
verified_total_years().
"""
import re
from datetime import date

# 01-candidate-profile.md - candidate-corrected dates. The May 2025 gap is not employment.
VERIFIED_EMPLOYMENT = (
    ("CodingNinjas", date(2023, 6, 1), date(2025, 4, 30)),
    ("Osbee Solution Private Limited", date(2025, 6, 1), None),  # present
)

MANDATORY_CUES = re.compile(r"\b(must|minimum|min\.?|at least|required|mandatory|strictly|only)\b", re.I)
PREFERRED_CUES = re.compile(r"\b(prefer(red|ably)?|nice to have|ideally|plus|bonus|good to have|desired)\b", re.I)
YEARS = re.compile(r"(\d{1,2})\s*(?:\+|-|–|to)?\s*(\d{1,2})?\s*\+?\s*(?:years|yrs|yoe)", re.I)
ROLE_RELEVANT = re.compile(
    r"full.?stack|mern|mean|node|react|angular|next\.?js|backend|back-end|frontend|front-end|"
    r"software|sde|developer|engineer|javascript|typescript|java|spring|j2ee|api|ui\b", re.I)

# Decision thresholds. A stretch role (more years asked) only needs real stack overlap.
MIN_SKILL_HITS = 2


def _months(start: date, end: date) -> int:
    return max(0, (end.year - start.year) * 12 + end.month - start.month + (1 if end.day >= start.day else 0))


def verified_total_years(today: date | None = None) -> float:
    """Total professional experience from verified employment dates, one decimal, never rounded up."""
    today = today or date.today()
    months = sum(_months(s, e or today) for _, s, e in VERIFIED_EMPLOYMENT)
    return int(months / 12 * 10) / 10


def years_answer(today: date | None = None) -> str:
    """The text to put in a 'total years of experience' form field: verified, not inflated."""
    return f"{verified_total_years(today):g}"


def parse_requirement(desc: str) -> dict:
    """The posting's minimum years and whether it reads as mandatory, preferred, or unclear.

    Returns {"min_years": int|None, "strength": "mandatory"|"preferred"|"unclear", "evidence": str}.
    The smallest plausible figure is used (a "3-5 years" range asks for 3).
    """
    best = None
    for m in YEARS.finditer(desc or ""):
        n = int(m.group(1))
        if n >= 20:
            continue
        lo = max(0, m.start() - 80)
        sentence = desc[lo:m.end() + 60]
        if best is None or n < best[0]:
            best = (n, sentence)
    if best is None:
        return {"min_years": None, "strength": "unclear", "evidence": ""}
    n, ctx = best
    if PREFERRED_CUES.search(ctx):
        strength = "preferred"
    elif MANDATORY_CUES.search(ctx):
        strength = "mandatory"
    else:
        strength = "unclear"
    return {"min_years": n, "strength": strength, "evidence": " ".join(ctx.split())}


def assess(desc: str, title: str, skill_hits: list[str], today: date | None = None) -> dict:
    """Evaluate the whole fit; years are one factor.

    Returns {"decision": "eligible"|"stretch"|"reject", "experience_score": 0-25,
             "years_gap": float|None, "requirement": {...}, "reasons": [...]}.
    """
    have = verified_total_years(today)
    req = parse_requirement(desc)
    hits = len(skill_hits)
    role_ok = bool(ROLE_RELEVANT.search(title or ""))
    aligned = hits >= MIN_SKILL_HITS and role_ok
    reasons = []

    gap = None if req["min_years"] is None else round(req["min_years"] - have, 1)
    if gap is None:
        exp = 18
        reasons.append("posting states no years requirement")
    elif gap <= 0:
        exp = 25
        reasons.append(f"meets the {req['min_years']}+ years asked ({have} verified)")
    else:
        # Soft penalty, floored when the stack aligns: years never zero out a strong match.
        per_year = 2 if req["strength"] == "preferred" else 3
        floor = 12 if aligned else 0
        exp = max(floor, 25 - int(gap * per_year))
        reasons.append(f"asks {req['min_years']}+ years ({req['strength']}), candidate has {have} verified: "
                       f"gap {gap} - evaluated, not auto-rejected")

    if not role_ok and hits < MIN_SKILL_HITS:
        decision = "reject"
        reasons.append(f"overall mismatch: unrelated role and only {hits} matching skills")
    elif gap is not None and gap > 0:
        if aligned:
            decision = "stretch"
            reasons.append(f"stretch role kept: {hits} matching skills and a relevant title")
        elif hits == 0:
            decision = "reject"
            reasons.append("overall mismatch: more years asked and no matching skills")
        else:
            decision = "stretch"
            reasons.append(f"weak alignment ({hits} skills) - kept for full-JD review")
    else:
        decision = "eligible"
    return {"decision": decision, "experience_score": exp, "years_gap": gap,
            "requirement": req, "candidate_years": have, "reasons": reasons}
