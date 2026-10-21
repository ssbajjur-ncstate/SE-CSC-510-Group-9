"""Summarise a links.json file for the ``testbudget links --report`` command."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def read_links_file(path: str | Path) -> dict:
    """Load links.json; raises FileNotFoundError or ValueError with a clear message."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"links file not found: {path}")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{path}: not valid JSON") from exc
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a JSON object mapping test IDs to links")
    return data


def summarize_links(links: dict) -> dict:
    """Count tests, linked tests and links per source (import/route/cofail/pin)."""
    by_source: Counter = Counter()
    linked = 0
    total = 0
    for entries in links.values():
        if not isinstance(entries, list):
            entries = []
        if entries:
            linked += 1
        for entry in entries:
            if isinstance(entry, dict):
                by_source[entry.get("source", "unknown")] += 1
            else:
                by_source["unlabelled"] += 1
            total += 1
    return {
        "tests": len(links),
        "tests_with_links": linked,
        "tests_without_links": len(links) - linked,
        "total_links": total,
        "by_source": dict(sorted(by_source.items())),
    }


def format_report(summary: dict) -> str:
    """Render a summary as plain text lines."""
    lines = [
        "LINKS REPORT",
        "-" * 32,
        f"Tests: {summary['tests']}",
        f"  with links:    {summary['tests_with_links']}",
        f"  without links: {summary['tests_without_links']}",
        f"Total links: {summary['total_links']}",
        "By source:",
    ]
    if summary["by_source"]:
        lines += [f"  {name}: {count}" for name, count in summary["by_source"].items()]
    else:
        lines.append("  (none)")
    return "\n".join(lines)
