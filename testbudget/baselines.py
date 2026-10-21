"""Baseline test orderings for the replay evaluation.

These implement the baselines in docs/eval-protocol.md: the three
pytest-ranking heuristics (recently failed first, most often failed first,
most recently modified first) and import-only. "Original order" and
"random" are done by the replay itself, since they need the suite order
and a seed.

Every function has the same signature as ``testbudget.ranker.rank_tests``
(``stats, changed_files, links``) and returns dicts with the same keys, so
the replay can swap any of them in for the ranker. ``links`` uses the
ranker's shape: ``{changed_file: [test_name, ...]}``.

The two recency baselines read optional fields from each stats entry:
``last_failed_at`` and ``last_modified_at`` (ISO date strings or numbers,
newer is larger). Tests without the field are placed last.
"""

from __future__ import annotations

from testbudget.ranker import get_linked_tests


def _entry(test: dict, linked: bool, score: float, reason: str) -> dict:
    """Build one ranked entry in the same shape the ranker returns."""
    return {
        "test_name": test["test_name"],
        "score": round(score, 3),
        "duration": float(test.get("avg_duration", 0.0)),
        "failure_count": test.get("failure_count", 0),
        "linked_to_change": linked,
        "reason": reason,
    }


def _finish(
    ordered: list[dict], linked: set[str], reasons: dict[str, str]
) -> list[dict]:
    """Turn an ordered list of stats entries into ranked entries
(top = highest score)."""
    total = len(ordered)
    return [
        _entry(t, t["test_name"] in linked, float(total - i), reasons[t["test_name"]])
        for i, t in enumerate(ordered)
    ]


def _newest_first(stats: list[dict], field: str) -> list[dict]:
    """Order by ``field`` descending; tests lacking it come last. Ties break on name."""
    have = sorted(
        (t for t in stats if t.get(field) is not None), key=lambda t: t["test_name"]
    )
    have.sort(key=lambda t: t[field], reverse=True)
    lack = sorted(
        (t for t in stats if t.get(field) is None), key=lambda t: t["test_name"]
    )
    return have + lack


def rank_recently_failed(stats, changed_files, links):
    """pytest-ranking heuristic 1: tests that failed most recently go first."""
    linked = get_linked_tests(changed_files, links)
    ordered = _newest_first(stats, "last_failed_at")
    reasons = {
        t["test_name"]: "failed recently"
        if t.get("last_failed_at") is not None
        else "no failure on record"
        for t in ordered
    }
    return _finish(ordered, linked, reasons)


def rank_most_failed(stats, changed_files, links):
    """pytest-ranking heuristic 2: tests with the most historical failures go first."""
    linked = get_linked_tests(changed_files, links)
    ordered = sorted(stats, key=lambda t: (-t.get("failure_count", 0), t["test_name"]))
    reasons = {
        t["test_name"]: f"{t.get('failure_count', 0)} historical failure(s)"
        if t.get("failure_count", 0)
        else "no failure history"
        for t in ordered
    }
    return _finish(ordered, linked, reasons)


def rank_recently_modified(stats, changed_files, links):
    """pytest-ranking heuristic 3: tests whose files changed most recently go first."""
    linked = get_linked_tests(changed_files, links)
    ordered = _newest_first(stats, "last_modified_at")
    reasons = {
        t["test_name"]: "modified recently"
        if t.get("last_modified_at") is not None
        else "no modification date"
        for t in ordered
    }
    return _finish(ordered, linked, reasons)


def rank_import_only(stats, changed_files, links):
    """Import-only: tests linked to a changed file first, no history used.
Ties break on name."""
    linked = get_linked_tests(changed_files, links)
    ordered = sorted(
        stats, key=lambda t: (t["test_name"] not in linked, t["test_name"])
    )
    reasons = {
        t["test_name"]: "import link" if t["test_name"] in linked else "not linked"
        for t in ordered
    }
    return _finish(ordered, linked, reasons)


BASELINES = {
    "recently_failed": rank_recently_failed,
    "most_failed": rank_most_failed,
    "recently_modified": rank_recently_modified,
    "import_only": rank_import_only,
}
