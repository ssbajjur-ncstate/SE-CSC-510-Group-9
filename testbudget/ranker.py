import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def load_links(path: str | Path) -> dict[str, list[str]]:
    """
    Load the changed-file-to-test mapping from JSON.
    """
    with open(path, encoding="utf-8") as file:
        links: dict[str, list[str]] = json.load(file)
    return links


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
