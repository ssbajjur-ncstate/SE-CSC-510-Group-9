"""Attribute nightly failures to the PRs whose plan skipped the failing test.

History records follow the shared JSONL contract: runs are
``{sha, timestamp, branch, changed_files}`` and results are
``{sha, test_id, status, duration_s, attempt}``. Plans follow the
``plan.json`` contract and links follow ``links.json``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, TypedDict

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


class Suspect(TypedDict):
    """A merged PR whose plan skipped at least one nightly failure."""

    pr: str
    sha: str
    missed_tests: list[str]
    link_strength: float


class MissRecord(TypedDict):
    """One missed test, ready to append to ``history/misses.jsonl``."""

    nightly_sha: str
    timestamp: str
    test_id: str
    prs: list[str]


class Attribution(TypedDict):
    """Result of ``attribute_misses``."""

    nightly_sha: str
    failed_tests: list[str]
    suspects: list[Suspect]
    misses: list[MissRecord]


def _skipped_tests(pr: str, plan: Any) -> tuple[str, set[str]]:
    """Return a plan's sha and skipped test IDs, validating the contract."""
    if not isinstance(plan, Mapping):
        raise ValueError(f"plan for PR {pr} must be an object")
    sha, skipped = plan.get("sha"), plan.get("skipped")
    if not isinstance(sha, str) or not sha:
        raise ValueError(f"plan for PR {pr} has no sha")
    if not isinstance(skipped, list):
        raise ValueError(f"plan for PR {pr} has no skipped list")
    test_ids: set[str] = set()
    for entry in skipped:
        if not isinstance(entry, Mapping) or not isinstance(entry.get("test_id"), str):
            raise ValueError(f"plan for PR {pr} has a skipped entry without test_id")
        test_ids.add(entry["test_id"])
    return sha, test_ids


def attribute_misses(
    nightly_sha: str,
    runs: Iterable[Record],
    results: Iterable[Record],
    plans: Mapping[str, Any],
    links: Mapping[str, Any],
) -> Attribution:
    """
    Return the PRs whose plan skipped a test that then failed on nightly.

    Args:
        nightly_sha: Sha of the failing nightly run; must be in ``runs``.
        runs: Run records from the history contract. A PR's changed files
            come from the run whose sha is its plan's ``sha``; a PR with no
            such run has no changed files and a link strength of 0.
        results: Result records from the history contract.
        plans: ``plan.json`` of every PR merged since the last green
            nightly, keyed by PR identifier.
        links: ``links.json`` contents.
    Returns:
        The nightly failures, the suspect PRs ranked by link strength (the
        summed strength over their missed tests, ties broken by PR id), and
        one miss record per missed test with its PRs ranked the same way.
        Failures that no plan skipped are in ``failed_tests`` only.
    Raises:
        ValueError: If ``nightly_sha`` is not in ``runs``, or a plan or link
            entry breaks its contract.
    """
    runs_by_sha = {run["sha"]: run for run in runs}
    if nightly_sha not in runs_by_sha:
        raise ValueError(f"nightly sha {nightly_sha} is not in the run history")
    failed = nightly_failures(nightly_sha, results)
    suspects: list[Suspect] = []
    by_test: dict[str, list[tuple[float, str]]] = {}
    for pr in sorted(plans):
        sha, skipped = _skipped_tests(pr, plans[pr])
        missed = sorted(skipped.intersection(failed))
        if not missed:
            continue
        changed = runs_by_sha.get(sha, {}).get("changed_files") or []
        strengths = [link_strength(test_id, changed, links) for test_id in missed]
        for test_id, strength in zip(missed, strengths, strict=True):
            by_test.setdefault(test_id, []).append((strength, pr))
        suspects.append(
            {
                "pr": pr,
                "sha": sha,
                "missed_tests": missed,
                "link_strength": sum(strengths),
            }
        )
    suspects.sort(key=lambda suspect: (-suspect["link_strength"], suspect["pr"]))
    timestamp = runs_by_sha[nightly_sha]["timestamp"]
    misses: list[MissRecord] = [
        {
            "nightly_sha": nightly_sha,
            "timestamp": timestamp,
            "test_id": test_id,
            "prs": [
                pr for _, pr in sorted(by_test[test_id], key=lambda s: (-s[0], s[1]))
            ],
        }
        for test_id in sorted(by_test)
    ]
    return {
        "nightly_sha": nightly_sha,
        "failed_tests": failed,
        "suspects": suspects,
        "misses": misses,
    }
