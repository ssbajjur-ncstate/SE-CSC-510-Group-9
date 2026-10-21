"""Co-failure links: files changed when a test failed become links to it."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


def read_jsonl(path: str | Path) -> list[dict]:
    """Read a JSONL file; a corrupt line raises ValueError naming the line."""
    rows = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{n}: corrupt JSON line") from exc
    return rows


def build_cofail_links(runs: list[dict], results: list[dict]) -> dict[str, list[dict]]:
    """Weight = how often the file changed on failing SHAs, scaled so max is 1.0."""
    changed = {r["sha"]: r.get("changed_files", []) for r in runs}
    seen: set[tuple[str, str]] = set()
    counts: dict[str, Counter] = defaultdict(Counter)
    for row in results:
        key = (row["sha"], row["test_id"])
        if row["status"] != "failed" or key in seen:
            continue
        seen.add(key)
        counts[row["test_id"]].update(changed.get(row["sha"], []))
    links = {}
    for test_id, c in counts.items():
        if not c:
            continue
        top = max(c.values())
        links[test_id] = [
            {"file": f, "source": "cofail", "weight": round(n / top, 3)}
            for f, n in sorted(c.items())
        ]
    return links
