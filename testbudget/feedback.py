"""Attribute nightly failures to the PRs whose plan skipped the failing test.

History records follow the shared JSONL contract: runs are
``{sha, timestamp, branch, changed_files}`` and results are
``{sha, test_id, status, duration_s, attempt}``. Plans follow the
``plan.json`` contract and links follow ``links.json``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

Record = Mapping[str, Any]


def nightly_failures(nightly_sha: str, results: Iterable[Record]) -> list[str]:
    """
    Return the tests that really failed on a nightly run.

    A test failed if it has a ``failed`` result on ``nightly_sha`` and no
    ``passed`` result there; a test that passed on a retry is flaky and is
    not a miss.
    Args:
        nightly_sha: Sha of the nightly run.
        results: Result records from the history contract.
    Returns:
        Failing test IDs, sorted.
    """
    failed: set[str] = set()
    passed: set[str] = set()
    for result in results:
        if result["sha"] != nightly_sha:
            continue
        if result.get("status") == "failed":
            failed.add(result["test_id"])
        elif result.get("status") == "passed":
            passed.add(result["test_id"])
    return sorted(failed - passed)


def link_strength(
    test_id: str, changed_files: Iterable[str], links: Mapping[str, Any]
) -> float:
    """
    Return how strongly a test is linked to a set of changed files.

    Args:
        test_id: The test to look up in ``links``.
        changed_files: Files a PR changed; duplicates count once.
        links: ``links.json`` contents, ``{test_id: [{file, source, weight}]}``.
    Returns:
        Sum of the weights of the test's links to changed files, summed in
        sorted file order; 0.0 if the test has no links to them.
    Raises:
        ValueError: If the test's links are not a list of objects with a
            ``file`` string and a non-negative numeric ``weight``.
    """
    entries = links.get(test_id, [])
    if not isinstance(entries, list):
        raise ValueError(f"links for {test_id} must be a list")
    changed = set(changed_files)
    weights: list[tuple[str, float]] = []
    for entry in entries:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("file"), str):
            raise ValueError(f"link for {test_id} must be an object with a file")
        weight = entry.get("weight")
        if (
            isinstance(weight, bool)
            or not isinstance(weight, int | float)
            or weight < 0
        ):
            raise ValueError(
                f"link weight for {test_id} must be a non-negative number, "
                f"got {weight!r}"
            )
        if entry["file"] in changed:
            weights.append((entry["file"], float(weight)))
    return sum(weight for _, weight in sorted(weights))
