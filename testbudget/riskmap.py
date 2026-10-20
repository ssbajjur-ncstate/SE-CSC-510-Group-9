"""Change risk from CI history.

Inputs are plain dicts in the shared history contract:
runs are ``{sha, timestamp, branch, changed_files}`` and results are
``{sha, test_id, status, duration_s, attempt}``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

Record = Mapping[str, Any]


def _failing_shas(results: Iterable[Record]) -> set[str]:
    """Return the shas of runs with at least one failed result."""
    return {result["sha"] for result in results if result.get("status") == "failed"}


def global_failure_prior(runs: Iterable[Record], results: Iterable[Record]) -> float:
    """
    Return the Laplace-smoothed share of runs with at least one failure.

    Used as the weight of files that have no history.
    Args:
        runs: Run records from the history contract.
        results: Result records from the history contract.
    Returns:
        ``(failing_runs + 1) / (runs + 2)``; 0.5 for an empty history.
    """
    failing = _failing_shas(results)
    shas = {run["sha"] for run in runs}
    return (len(shas & failing) + 1) / (len(shas) + 2)


def file_failure_weights(
    runs: Iterable[Record], results: Iterable[Record]
) -> dict[str, float]:
    """
    Return each changed file's Laplace-smoothed failure share.

    For every file, the weight is the share of runs that changed it and had
    at least one failed result, smoothed as ``(failing + 1) / (touched + 2)``.
    Args:
        runs: Run records from the history contract.
        results: Result records from the history contract.
    Returns:
        Mapping of file path to weight in (0, 1), sorted by path.
        Files never changed in history are absent; see
        ``global_failure_prior`` for their weight.
    """
    failing = _failing_shas(results)
    touched: dict[str, int] = {}
    failed: dict[str, int] = {}
    seen: set[str] = set()
    for run in runs:
        sha = run["sha"]
        # A sha recorded twice is one run, not two.
        if sha in seen:
            continue
        seen.add(sha)
        for path in set(run.get("changed_files") or []):
            touched[path] = touched.get(path, 0) + 1
            if sha in failing:
                failed[path] = failed.get(path, 0) + 1
    return {
        path: (failed.get(path, 0) + 1) / (touched[path] + 2)
        for path in sorted(touched)
    }
