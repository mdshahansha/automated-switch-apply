"""Job-search keyword cards: load, validate, select, and merge discoveries.

The cards live in tools/search_keywords.json, grouped into categories. Every
card is one independently searchable keyword with an id and an enabled flag,
so a run can search all enabled cards, a single card, or one category.

When several cards surface the same job, merge_discoveries() keeps one record
per job and records every card that found it in `discovered_by` (card ids) and
`discovered_keywords` (the keyword strings), in first-seen order.

Usage:
  python tools/search_keywords.py list [--all] [--category ID]
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "tools" / "search_keywords.json"


class KeywordConfigError(ValueError):
    """The keyword-card file is malformed."""


def load_cards(path: Path = CONFIG) -> list[dict]:
    """Every card (enabled or not), each annotated with its category id/label.

    Validates: unique card ids, non-empty keywords, boolean `enabled`, and no
    keyword listed twice (case-insensitive) - a duplicate keyword would search
    the same thing twice and double-count discoveries.
    """
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise KeywordConfigError(f"{path}: {exc}") from exc
    cards, ids, keywords = [], set(), set()
    for cat in doc.get("categories", []):
        cat_id, label = cat.get("id"), cat.get("label")
        if not cat_id or not label:
            raise KeywordConfigError(f"category without id/label: {cat!r}")
        for card in cat.get("cards", []):
            cid, kw, enabled = card.get("id"), (card.get("keyword") or "").strip(), card.get("enabled")
            if not cid or not kw:
                raise KeywordConfigError(f"card without id/keyword in {cat_id}: {card!r}")
            if not isinstance(enabled, bool):
                raise KeywordConfigError(f"card {cid}: enabled must be true/false")
            if cid in ids:
                raise KeywordConfigError(f"duplicate card id: {cid}")
            if kw.casefold() in keywords:
                raise KeywordConfigError(f"duplicate keyword: {kw}")
            ids.add(cid)
            keywords.add(kw.casefold())
            cards.append({**card, "keyword": kw, "category": cat_id, "category_label": label})
    if not cards:
        raise KeywordConfigError(f"{path}: no keyword cards")
    return cards


def enabled_cards(cards: list[dict], category: str | None = None) -> list[dict]:
    """The cards a search run should process, optionally limited to one category."""
    return [c for c in cards if c["enabled"] and (category is None or c["category"] == category)]


def get_card(cards: list[dict], card_id: str) -> dict:
    """One card by id, enabled or not - an explicit single-card search may run a paused card."""
    for c in cards:
        if c["id"] == card_id:
            return c
    raise KeyError(card_id)


def merge_discoveries(results: list[tuple[dict, list[dict]]], key=lambda job: job["id"]) -> list[dict]:
    """Deduplicate jobs found by several cards, preserving which cards found each.

    `results` is a list of (card, jobs) pairs in search order. The first copy of
    a job wins for its fields; later copies only add their card to the metadata.
    """
    merged: dict = {}
    for card, jobs in results:
        for job in jobs:
            k = key(job)
            entry = merged.get(k)
            if entry is None:
                entry = merged[k] = {**job, "discovered_by": [], "discovered_keywords": []}
            if card["id"] not in entry["discovered_by"]:
                entry["discovered_by"].append(card["id"])
                entry["discovered_keywords"].append(card["keyword"])
    return list(merged.values())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="print keyword cards")
    ls.add_argument("--all", action="store_true", help="include disabled cards")
    ls.add_argument("--category", help="limit to one category id")
    a = ap.parse_args(argv)
    cards = load_cards()
    shown = [c for c in cards if (a.all or c["enabled"]) and (a.category is None or c["category"] == a.category)]
    for n, c in enumerate(shown, 1):
        flag = "" if c["enabled"] else "  [disabled]"
        print(f"{n:>2}. [{c['category']}] {c['keyword']} ({c['id']}){flag}")
    print(f"{len(shown)} cards", file=sys.stderr)


if __name__ == "__main__":
    main()
