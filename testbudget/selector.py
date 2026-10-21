"""Budget cut over a ranked, rule-ordered test list."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from testbudget.rules import RuleContext, apply_rules


def select_with_budget(
    ranked_tests: list[dict[str, Any]], budget: float
) -> dict[str, Any]:
    """
    Select ranked tests while staying within the supplied time budget.

    Forced tests (``forced=True``, set by the hard rules) are always selected
    and their duration counts against the budget first, even past it. The
    remaining tests are considered in ranking order; a test that does not fit
    is skipped, and later shorter tests may still be selected.
    Args:
        ranked_tests: Ranked tests with ``duration`` and optional ``forced``.
        budget: Time budget in seconds.
    Returns:
        ``{"selected", "skipped", "estimated_runtime", "budget"}``; selected
        tests keep ranking order, skipped tests carry ``skip_reason``.
    Raises:
        ValueError: If ``budget`` is negative.
    """
    if budget < 0:
        raise ValueError("Budget cannot be negative")

    used_time = sum(
        float(test.get("duration", 0.0)) for test in ranked_tests if test.get("forced")
    )
    selected: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for test in ranked_tests:
        duration = float(test.get("duration", 0.0))
        if test.get("forced"):
            selected.append(test)
        elif used_time + duration <= budget:
            selected.append(test)
            used_time += duration
        else:
            skipped_test = dict(test)
            skipped_test["skip_reason"] = "budget exhausted"
            skipped.append(skipped_test)

    return {
        "selected": selected,
        "skipped": skipped,
        "estimated_runtime": round(used_time, 3),
        "budget": float(budget),
    }


def select_with_rules(
    ranked_tests: Iterable[Mapping[str, Any]], budget: float, context: RuleContext
) -> dict[str, Any]:
    """
    Apply the hard rules, then cut the result to the budget.

    Pinned, rotation-limit and full-suite tests are forced: they count
    against the budget but are never cut.

    Args:
        ranked_tests: Output of ``ranker.rank_tests``.
        budget: Time budget in seconds.
        context: Rule context (config, changed files, history, ref).
    Returns:
        ``select_with_budget`` output plus ``run_all`` and ``trigger`` from
        ``rules.apply_rules``.
    Raises:
        ValueError: If ``budget`` is negative or the rule inputs are malformed.
    """
    outcome = apply_rules(ranked_tests, context)
    # Pins are never cut, like rotation-limit and full-suite forced tests.
    tests = [
        {**test, "forced": True} if test.get("rule") == "pinned" else test
        for test in outcome["tests"]
    ]
    plan = select_with_budget(tests, budget)
    plan["run_all"] = outcome["run_all"]
    plan["trigger"] = outcome["trigger"]
    return plan
