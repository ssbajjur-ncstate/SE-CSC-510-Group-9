"""Build and write ``plan.json`` in the shared plan contract.

Contract: ``{sha, risk_level, budget_s, selected: [{test_id, reason,
duration_s}], skipped: [{test_id, skip_reason, skip_debt}],
catch_rate_estimate}``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from testbudget.riskmap import (
    change_risk,
    file_failure_weights,
    global_failure_prior,
    historical_risk_scores,
    risk_level,
    risk_thresholds,
)

Record = Mapping[str, Any]


def plan_risk_level(
    changed_files: Sequence[str], runs: Sequence[Record], results: Sequence[Record]
) -> str:
    """
    Return the risk level of a change set from the risk map.

    Args:
        changed_files: Paths changed by the pull request.
        runs: Run records from the history contract.
        results: Result records from the history contract.
    Returns:
        ``"low"``, ``"medium"`` or ``"high"``; ``"medium"`` when there is no
        run history to calibrate thresholds against.
    """
    if not runs:
        return "medium"
    weights = file_failure_weights(runs, results)
    prior = global_failure_prior(runs, results)
    thresholds = risk_thresholds(historical_risk_scores(runs, weights, prior))
    return risk_level(change_risk(changed_files, weights, prior), thresholds)


def _reason(test: Mapping[str, Any]) -> str:
    """Return why a selected test runs: its hard rule first, else the ranker."""
    if test.get("rule"):
        return str(test["rule"])
    if test.get("skip_debt") and test.get("forced"):
        return "rotation limit"
    return str(test.get("reason", "ranked"))


def catch_rate_estimate(selection: Mapping[str, Any]) -> float:
    """
    Return the share of historical failures held by the selected tests.

    Args:
        selection: Output of ``selector.select_with_budget``.
    Returns:
        Selected ``failure_count`` over total ``failure_count`` in [0, 1],
        rounded to 3 places; 1.0 when no test has failed before.
    """
    caught = sum(t.get("failure_count", 0) for t in selection["selected"])
    total = caught + sum(t.get("failure_count", 0) for t in selection["skipped"])
    return 1.0 if total == 0 else round(caught / total, 3)


def build_plan(
    sha: str, selection: Mapping[str, Any], risk: str, budget_s: float
) -> dict[str, Any]:
    """
    Return a plan dict in the shared ``plan.json`` contract.

    Args:
        sha: Commit being planned.
        selection: Output of ``selector.select_with_rules``.
        risk: Risk level, e.g. from ``plan_risk_level``.
        budget_s: Time budget in seconds.
    Returns:
        The contract dict; selected tests keep run order, skipped tests are
        sorted by test ID.
    Raises:
        ValueError: If ``budget_s`` is negative.
    """
    if budget_s < 0:
        raise ValueError("Budget cannot be negative")
    selected = [
        {
            "test_id": t["test_name"],
            "reason": _reason(t),
            "duration_s": float(t.get("duration", 0.0)),
        }
        for t in selection["selected"]
    ]
    skipped = sorted(
        (
            {
                "test_id": t["test_name"],
                "skip_reason": t.get("skip_reason", "budget exhausted"),
                "skip_debt": int(t.get("skip_debt", 0)),
            }
            for t in selection["skipped"]
        ),
        key=lambda t: t["test_id"],
    )
    return {
        "sha": sha,
        "risk_level": risk,
        "budget_s": float(budget_s),
        "selected": selected,
        "skipped": skipped,
        "catch_rate_estimate": catch_rate_estimate(selection),
    }


def write_plan(plan: Mapping[str, Any], path: str | Path) -> Path:
    """
    Write a plan as JSON.

    Args:
        plan: Output of ``build_plan``.
        path: Destination file; parent directories are created.
    Returns:
        The written path.
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return out
