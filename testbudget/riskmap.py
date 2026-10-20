"""Change risk from CI history.

Inputs are plain dicts in the shared history contract:
runs are ``{sha, timestamp, branch, changed_files}`` and results are
``{sha, test_id, status, duration_s, attempt}``.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Mapping
from typing import Any, Literal

Record = Mapping[str, Any]
RiskLevel = Literal["low", "medium", "high"]

# Pseudo-runs at the global failure rate added to every file's history.
PRIOR_STRENGTH = 2


def _failing_shas(results: Iterable[Record]) -> set[str]:
    """Return the shas of runs with at least one failed result."""
    return {result["sha"] for result in results if result.get("status") == "failed"}


def global_failure_prior(runs: Iterable[Record], results: Iterable[Record]) -> float:
    """
    Return the observed share of runs with at least one failure.

    Used as the weight of files that have no history, and as the value
    every file weight is shrunk toward. It is not smoothed, so a file that
    appears in every failing run never weighs less than an unseen file.
    Args:
        runs: Run records from the history contract.
        results: Result records from the history contract.
    Returns:
        ``failing_runs / runs`` in [0, 1]; 0.5 for an empty history.
    """
    failing = _failing_shas(results)
    shas = {run["sha"] for run in runs}
    if not shas:
        return 0.5
    return len(shas & failing) / len(shas)


def file_failure_weights(
    runs: Iterable[Record], results: Iterable[Record]
) -> dict[str, float]:
    """
    Return each changed file's failure share, shrunk toward the global prior.

    For every file, the raw weight is the share of runs that changed it and
    had at least one failed result. It is smoothed as
    ``(failing + PRIOR_STRENGTH * prior) / (touched + PRIOR_STRENGTH)`` where
    ``prior`` is ``global_failure_prior``, so a rarely touched file stays
    close to the global failure rate instead of close to 0.5.
    Args:
        runs: Run records from the history contract.
        results: Result records from the history contract.
    Returns:
        Mapping of file path to weight in [0, 1], sorted by path.
        Files never changed in history are absent; pass
        ``global_failure_prior`` to ``change_risk`` as their weight.
    """
    runs = list(runs)
    results = list(results)
    prior = global_failure_prior(runs, results)
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
        path: (failed.get(path, 0) + PRIOR_STRENGTH * prior)
        / (touched[path] + PRIOR_STRENGTH)
        for path in sorted(touched)
    }


def change_risk(
    changed_files: Iterable[str], weights: Mapping[str, float], prior: float
) -> float:
    """
    Return the risk score of a change set.

    Args:
        changed_files: Paths changed by the pull request; duplicates count once.
        weights: Output of ``file_failure_weights``.
        prior: Weight for files absent from ``weights``, normally
            ``global_failure_prior``.
    Returns:
        Sum of the file weights; 0.0 for an empty change set.
    Raises:
        ValueError: If ``prior`` is outside [0, 1].
    """
    if not 0.0 <= prior <= 1.0:
        raise ValueError(f"prior must be in [0, 1], got {prior}")
    # Sort so the floating-point sum is the same for any input order.
    return sum(weights.get(path, prior) for path in sorted(set(changed_files)))


def historical_risk_scores(
    runs: Iterable[Record], weights: Mapping[str, float], prior: float
) -> list[float]:
    """
    Return the change risk of every run in history, in run order.

    Args:
        runs: Run records from the history contract.
        weights: Output of ``file_failure_weights``.
        prior: Weight for files absent from ``weights``.
    Returns:
        One score per run; runs without ``changed_files`` score 0.0.
    """
    return [change_risk(run.get("changed_files") or [], weights, prior) for run in runs]


def risk_thresholds(scores: Iterable[float]) -> tuple[float, float]:
    """
    Return the low/medium and medium/high cut points of historical scores.

    The cut points are the tertiles of the scores, so a history splits into
    roughly equal thirds.
    Args:
        scores: Historical risk scores, e.g. from ``historical_risk_scores``.
    Returns:
        ``(low_max, medium_max)`` with ``low_max <= medium_max``.
    Raises:
        ValueError: If ``scores`` is empty.
    """
    values = sorted(scores)
    if not values:
        raise ValueError("cannot compute risk thresholds from an empty history")
    if len(values) == 1:
        return values[0], values[0]
    low_max, medium_max = statistics.quantiles(values, n=3, method="inclusive")
    return low_max, medium_max


def risk_level(score: float, thresholds: tuple[float, float]) -> RiskLevel:
    """
    Return the risk level of a change risk score.

    Args:
        score: Output of ``change_risk``.
        thresholds: ``(low_max, medium_max)`` from ``risk_thresholds``.
            Scores equal to a cut point fall in the lower level.
    Returns:
        ``"low"``, ``"medium"`` or ``"high"``.
    Raises:
        ValueError: If ``low_max`` is greater than ``medium_max``.
    """
    low_max, medium_max = thresholds
    if low_max > medium_max:
        raise ValueError(
            f"thresholds must be ordered (low_max <= medium_max), got {thresholds}"
        )
    if score <= low_max:
        return "low"
    if score <= medium_max:
        return "medium"
    return "high"
