#!/usr/bin/env python3
"""Check CV experience bullets against the resume bullet formula.

03-writing-style.md asks every experience bullet to read as
action + what was built + measurable result + how. This lint reads the
`\\item` lines of a LaTeX CV and flags bullets that miss one of the parts
it can detect mechanically:

  * no-action  - the bullet does not open with a past-tense or known verb
  * no-number  - no digit anywhere, so no measurable result or scope
  * no-how     - no method clause ("by", "using", "with", "via", "through")

Only bullets under an Experience or Project section are checked; when the
file has no \\section at all, every bullet is. Skill-list items that open with a bold label (`\\item \\textbf{Front end}: ...`)
are category lines, not achievements, and are skipped.

A flag is a prompt to look again, never an instruction to add a number. The
fix for a missing metric is a real metric from 01-candidate-profile.md or a
scope statement, never an invented figure.

Usage:
    python3 tools/bullet_lint.py cv/main_<company>_<role>.tex [--json]

Exit status is 0 when every bullet passes, 1 when any bullet is flagged, and
2 when the file cannot be read.
"""

import argparse
import json
import re
import sys
from pathlib import Path

ACTION_VERBS = {
    "architected", "automated", "built", "cut", "debugged", "delivered",
    "deployed", "designed", "developed", "drove", "implemented", "improved",
    "increased", "integrated", "introduced", "launched", "led", "maintained",
    "mentored", "migrated", "optimized", "owned", "performed", "reduced",
    "refactored", "replaced", "scaled", "shipped", "streamlined", "supported",
    "wrote",
}
HOW_WORDS = re.compile(r"\b(by|using|with|via|through|across)\b", re.IGNORECASE)
SECTION = re.compile(r"^\s*\\section\*?\{([^}]*)\}")
CHECKED_SECTIONS = re.compile(r"experience|project", re.IGNORECASE)
ITEM = re.compile(r"^\s*\\item\b(.*)$")
LATEX_CMD = re.compile(r"\\[a-zA-Z]+\*?(\{([^{}]*)\})?")


def plain_text(latex):
    """Strip simple LaTeX commands, keeping the text inside their braces."""
    text = LATEX_CMD.sub(lambda m: m.group(2) or "", latex)
    return re.sub(r"[{}~]", " ", text).replace("\\%", "%").strip()


def check_bullet(text):
    """Return the list of flags for one bullet's plain text."""
    flags = []
    words = re.findall(r"[A-Za-z]+", text)
    first = words[0].lower() if words else ""
    if not (first in ACTION_VERBS or (first.endswith("ed") and len(first) > 3)):
        flags.append("no-action")
    if not re.search(r"\d", text):
        flags.append("no-number")
    if not HOW_WORDS.search(text):
        flags.append("no-how")
    return flags


def lint(path):
    """Yield (line number, bullet text, flags) for each experience bullet."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    in_scope = not any(SECTION.match(line) for line in lines)
    for lineno, line in enumerate(lines, 1):
        section = SECTION.match(line)
        if section:
            in_scope = bool(CHECKED_SECTIONS.search(section.group(1)))
            continue
        match = ITEM.match(line)
        if not match or not in_scope:
            continue
        body = match.group(1).strip()
        if body.startswith("\\textbf"):
            continue
        text = plain_text(body)
        if text:
            yield lineno, text, check_bullet(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("cv", help="LaTeX CV file to check")
    parser.add_argument("--json", action="store_true", help="print JSON instead of text")
    args = parser.parse_args(argv)
    try:
        rows = list(lint(args.cv))
    except OSError as error:
        print(f"bullet_lint: {error}", file=sys.stderr)
        return 2
    flagged = [r for r in rows if r[2]]
    if args.json:
        print(json.dumps({
            "bullets": len(rows),
            "flagged": [{"line": n, "text": t, "flags": f} for n, t, f in flagged],
        }, indent=2))
    else:
        for n, t, f in flagged:
            print(f"{args.cv}:{n}: {', '.join(f)}: {t[:90]}")
        print(f"{len(rows)} bullets checked, {len(flagged)} flagged")
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
