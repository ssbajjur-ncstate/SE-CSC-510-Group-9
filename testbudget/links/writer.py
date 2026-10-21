"""Read, merge, validate and write links.json."""
from __future__ import annotations

import json
from pathlib import Path

VALID_SOURCES = {"import", "route", "cofail", "pin"}


def validate_links(links: dict[str, list[dict]]) -> None:
    """Raise ValueError if any link entry breaks the links.json contract."""
    for test_id, entries in links.items():
        for e in entries:
            if not e.get("file"):
                raise ValueError(f"{test_id}: link has no file")
            if e.get("source") not in VALID_SOURCES:
                raise ValueError(f"{test_id}: bad source {e.get('source')!r}")
            if e.get("weight", -1) < 0:
                raise ValueError(f"{test_id}: weight must be >= 0")


def merge_links(*sets: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Combine several link sets; entries for the same test are concatenated."""
    merged: dict[str, list[dict]] = {}
    for links in sets:
        for test_id, entries in links.items():
            merged.setdefault(test_id, []).extend(entries)
    return merged


def write_links(links: dict[str, list[dict]], path: str | Path) -> None:
    """Validate then write links as stable, sorted JSON."""
    validate_links(links)
    Path(path).write_text(
        json.dumps(links, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
