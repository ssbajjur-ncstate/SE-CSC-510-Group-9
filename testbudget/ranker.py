import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def load_links(path: str | Path) -> dict[str, list[str]]:
    """
    Load the changed-file-to-test mapping from JSON.

    Accepts the shared links contract written by ``links --build``,
    ``{test_id: [{file, source, weight}]}``, and inverts it. The legacy
    ``{changed_file: [test_id]}`` shape is returned unchanged.

    Args:
        path: Path to the links JSON file.

    Returns:
        Mapping of source file to the sorted test IDs linked to it.

    Raises:
        ValueError: If the file is not a JSON object of lists.
    """
    with open(path, encoding="utf-8") as file:
        raw = json.load(file)
    if not isinstance(raw, dict) or not all(
        isinstance(entries, list) for entries in raw.values()
    ):
        raise ValueError(f"links file must map keys to lists: {path}")
    if not any(
        isinstance(entry, dict) for entries in raw.values() for entry in entries
    ):
        links: dict[str, list[str]] = raw
        return links
    inverted: dict[str, set[str]] = {}
    for test_id, entries in raw.items():
        for entry in entries:
            if not isinstance(entry, dict) or "file" not in entry:
                raise ValueError(f"{test_id}: link entry has no file: {path}")
            inverted.setdefault(entry["file"], set()).add(test_id)
    return {file: sorted(tests) for file, tests in sorted(inverted.items())}


def get_linked_tests(
    changed_files: Iterable[str], links: dict[str, list[str]]
) -> set[str]:
    """
    Return all tests linked to any of the changed files.
    """
    linked_tests: set[str] = set()
    for changed_file in changed_files:
        for test_name in links.get(changed_file, []):
            linked_tests.add(test_name)
    return linked_tests


def rank_tests(
    stats: list[dict[str, Any]],
    changed_files: Iterable[str],
    links: dict[str, list[str]],
) -> list[dict[str, Any]]:
    """
    Rank tests using a simple baseline score.
    Inputs:
        stats:
            Historical statistics produced by db.get_test_stats()
        changed_files:
            List of source files changed in the pull request.
        links:
            Mapping of source files to related tests.
    Current baseline scoring:
        +10 if test is linked to changed code
        +5 for each historical failure
        Then divide by average runtime.
    This favors tests that are:
        - relevant to the current change
        - historically failure-prone
        - relatively inexpensive to run
    This is the initial baseline ranker, not the final
    TestBudget research ranking algorithm.
    """
    linked_tests = get_linked_tests(changed_files, links)
    ranked: list[dict[str, Any]] = []
    for test in stats:
        test_name = test["test_name"]
        failure_count = test.get("failure_count", 0)
        avg_duration = float(test.get("avg_duration", 0.0))
        is_linked = test_name in linked_tests

        change_score = 10 if is_linked else 0
        failure_score = failure_count * 5

        # Avoid dividing by zero if runtime data is missing.
        safe_duration = max(avg_duration, 0.1)
        score = (change_score + failure_score) / safe_duration

        reasons: list[str] = []
        if is_linked:
            reasons.append("changed file")
        if failure_count > 0:
            reasons.append(
                f"{failure_count} historical failure"
                if failure_count == 1
                else f"{failure_count} historical failures"
            )
        if not reasons:
            reasons.append("historical runtime")

        ranked.append(
            {
                "test_name": test_name,
                "score": round(score, 3),
                "duration": avg_duration,
                "failure_count": failure_count,
                "linked_to_change": is_linked,
                "reason": " + ".join(reasons),
            }
        )

    # Highest score first.
    # test_name is the secondary sort key so identical inputs
    # always produce the same ordering.
    ranked.sort(key=lambda test: (-test["score"], test["test_name"]))
    return ranked


COVERAGE_DISCOUNT = 0.3
MIN_DURATION_S = 0.1


def _coverage_reason(covered: list[str], failure_count: int) -> str:
    """Return the reason string for a coverage-ranked test."""
    parts = [f"covers {', '.join(covered)}"] if covered else ["no changed file"]
    if failure_count:
        noun = "failure" if failure_count == 1 else "failures"
        parts.append(f"{failure_count} historical {noun}")
    return " + ".join(parts)


def rank_tests_coverage(
    stats: list[dict[str, Any]],
    changed_files: Iterable[str],
    links: dict[str, list[str]],
    file_weights: dict[str, float],
) -> list[dict[str, Any]]:
    """
    Rank tests by greedy budgeted maximum coverage of the changed files.

    Each test covers the changed files linked to it. A file is worth
    ``1 + file_weights.get(file, 0)``. The test with the largest uncovered
    value per second (duration floored at 0.1 s) is picked next, then the
    files it covers keep 0.3 of their remaining value. Tests that cover no
    changed file go last, most recent failure first (``last_failure``, an
    ISO timestamp, if the stats carry it), then by name. Ties break by name.
    Args:
        stats: Historical statistics, as ``db.get_test_stats`` returns.
        changed_files: Source files changed in the pull request.
        links: Mapping of source file to linked test names.
        file_weights: Failure weight per file, e.g. from
            ``riskmap.file_failure_weights``.
    Returns:
        Ranked tests in the shape ``rank_tests`` returns; ``score`` is the
        value per second at the moment the test was picked.
    """
    changed = sorted(set(changed_files))
    covers: dict[str, list[str]] = {}
    for path in changed:
        for test_name in links.get(path, []):
            covers.setdefault(test_name, []).append(path)
    value = {path: 1.0 + file_weights.get(path, 0.0) for path in changed}
    by_name = {test["test_name"]: test for test in stats}

    def entry(test: dict[str, Any], score: float) -> dict[str, Any]:
        covered = covers.get(test["test_name"], [])
        failure_count = test.get("failure_count", 0) or 0
        return {
            "test_name": test["test_name"],
            "score": round(score, 3),
            "duration": float(test.get("avg_duration", 0.0)),
            "failure_count": failure_count,
            "linked_to_change": bool(covered),
            "reason": _coverage_reason(covered, failure_count),
        }

    def duration(name: str) -> float:
        return max(float(by_name[name].get("avg_duration", 0.0)), MIN_DURATION_S)

    ranked: list[dict[str, Any]] = []
    pending = sorted(name for name in by_name if name in covers)
    while pending:
        gains = {
            name: sum(value[path] for path in covers[name]) / duration(name)
            for name in pending
        }
        best = min(pending, key=lambda name: (-gains[name], name))
        ranked.append(entry(by_name[best], gains[best]))
        for path in covers[best]:
            value[path] *= COVERAGE_DISCOUNT
        pending.remove(best)

    rest = sorted(
        (test for name, test in by_name.items() if name not in covers),
        key=lambda test: test["test_name"],
    )
    # Stable sort: most recent failure first, never-failed last, names within.
    rest.sort(key=lambda test: test.get("last_failure") or "", reverse=True)
    ranked.extend(entry(test, 0.0) for test in rest)
    return ranked
