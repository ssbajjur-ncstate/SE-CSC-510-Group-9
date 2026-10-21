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
