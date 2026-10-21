"""Hard rules applied to a ranked test list before the budget cut.

Ranked tests are dicts in the shape ``ranker.rank_tests`` returns. The rules
read ``test_name``, add their own keys, and leave every other key alone. Each
rule returns new dicts and never mutates its input. History records follow the
shared JSONL contract: runs are ``{sha, timestamp, branch, changed_files}`` and
results are ``{sha, test_id, status, duration_s, attempt}``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

RankedTest = dict[str, Any]
Record = Mapping[str, Any]


@dataclass(frozen=True)
class RuleContext:
    """
    Everything a rule may read besides the ranked list.

    Attributes:
        config: Parsed ``testbudget.yml``.
        changed_files: Paths changed by the pull request.
        runs: Run records from the history contract.
        results: Result records from the history contract.
        ref: Git ref being planned, e.g. ``refs/heads/main`` or ``refs/tags/v1``.
    """

    config: Mapping[str, Any] = field(default_factory=dict)
    changed_files: Sequence[str] = ()
    runs: Sequence[Record] = ()
    results: Sequence[Record] = ()
    ref: str | None = None


def _promote(
    ranked: Iterable[Mapping[str, Any]], matches: set[str], label: str
) -> list[RankedTest]:
    """Return copies of ``ranked`` with matching tests first, labelled ``label``."""
    front: list[RankedTest] = []
    rest: list[RankedTest] = []
    for test in ranked:
        copy = dict(test)
        if copy["test_name"] in matches:
            copy["rule"] = label
            front.append(copy)
        else:
            rest.append(copy)
    # Both groups keep their ranked order, so the result stays deterministic.
    return front + rest


def pinned_tests(config: Mapping[str, Any]) -> set[str]:
    """
    Return the test IDs pinned in the config.

    Args:
        config: Parsed ``testbudget.yml``. ``pins`` is either a list of test
            IDs or a mapping of test ID to pinned files, as in ``links/pins.py``.
    Returns:
        The pinned test IDs; empty if ``pins`` is absent.
    Raises:
        ValueError: If ``pins`` is another type or holds a non-string ID.
    """
    pins = config.get("pins") or []
    if isinstance(pins, Mapping):
        ids = list(pins.keys())
    elif isinstance(pins, list | tuple):
        ids = list(pins)
    else:
        raise ValueError(
            "pins must be a list of test IDs or a mapping of test ID to files, "
            f"got {type(pins).__name__}"
        )
    for test_id in ids:
        if not isinstance(test_id, str) or not test_id.strip():
            raise ValueError(f"pinned test ID must be a non-empty string: {test_id!r}")
    return set(ids)


def pin_first(
    ranked: Iterable[Mapping[str, Any]], context: RuleContext
) -> list[RankedTest]:
    """
    Move pinned tests to the front of the ranked list.

    Args:
        ranked: Output of ``ranker.rank_tests``.
        context: Rule context; reads ``config["pins"]``.
    Returns:
        New list with pinned tests first, in ranked order, tagged
        ``rule="pinned"``; the other tests follow in ranked order. Pins that
        name a test not in ``ranked`` are ignored.
    Raises:
        ValueError: If ``pins`` is malformed.
    """
    return _promote(ranked, pinned_tests(context.config), "pinned")


def _normalise_path(path: str) -> str:
    """Return ``path`` with forward slashes and no leading ``./``."""
    path = path.replace("\\", "/")
    while path.startswith("./"):
        path = path[2:]
    return path


def file_of_test(test_id: str) -> str:
    """
    Return the file part of a test ID.

    Args:
        test_id: ``path::name`` (pytest) or ``file › title`` (Playwright).
    Returns:
        The path before the first separator, normalised to forward slashes;
        the whole ID if it has no separator.
    """
    cut = [test_id.find(sep) for sep in ("::", " › ") if sep in test_id]
    return _normalise_path(test_id[: min(cut)] if cut else test_id)


def changed_tests_next(
    ranked: Iterable[Mapping[str, Any]], context: RuleContext
) -> list[RankedTest]:
    """
    Move tests whose own test file is in the changed set to the front.

    Args:
        ranked: Output of ``ranker.rank_tests``.
        context: Rule context; reads ``changed_files``.
    Returns:
        New list with matching tests first, in ranked order, tagged
        ``rule="changed test file"``; the other tests follow in ranked order.
    Raises:
        TypeError: If ``changed_files`` is a single string instead of a list.
    """
    if isinstance(context.changed_files, str):
        raise TypeError("changed_files must be a list of paths, not a string")
    changed = {_normalise_path(path) for path in context.changed_files}
    ranked = list(ranked)
    matches = {
        test["test_name"]
        for test in ranked
        if file_of_test(test["test_name"]) in changed
    }
    return _promote(ranked, matches, "changed test file")


DEFAULT_RECENT_FAILURE_WINDOW = 5


def _non_negative_int(config: Mapping[str, Any], key: str, default: int) -> int:
    """Return ``config[key]`` as a non-negative int, or ``default`` if absent."""
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer, got {value!r}")
    return value


def ordered_shas(runs: Iterable[Record]) -> list[str]:
    """
    Return run shas from oldest to newest.

    Args:
        runs: Run records from the history contract.
    Returns:
        Shas sorted by ``(timestamp, sha)``; a sha recorded twice appears once.
        Timestamps are ISO 8601 strings in one format, so they sort as text.
    """
    seen: set[str] = set()
    ordered: list[str] = []
    for run in sorted(runs, key=lambda run: (run["timestamp"], run["sha"])):
        if run["sha"] not in seen:
            seen.add(run["sha"])
            ordered.append(run["sha"])
    return ordered


def recently_failed(
    runs: Iterable[Record], results: Iterable[Record], window: int
) -> set[str]:
    """
    Return the tests that failed in any of the last ``window`` runs.

    Args:
        runs: Run records from the history contract.
        results: Result records from the history contract.
        window: Number of most recent runs to look at; 0 looks at none.
    Returns:
        Test IDs with a ``failed`` result, on any attempt, in those runs.
    Raises:
        ValueError: If ``window`` is negative.
    """
    if window < 0:
        raise ValueError(f"window must be non-negative, got {window}")
    shas = ordered_shas(runs)
    recent = set(shas[len(shas) - window :]) if window else set()
    return {
        result["test_id"]
        for result in results
        if result["sha"] in recent and result.get("status") == "failed"
    }


def recent_failures_next(
    ranked: Iterable[Mapping[str, Any]], context: RuleContext
) -> list[RankedTest]:
    """
    Move tests that failed in the last K runs to the front.

    Args:
        ranked: Output of ``ranker.rank_tests``.
        context: Rule context; reads ``runs``, ``results`` and
            ``config["recent_failure_window"]`` (K, default 5).
    Returns:
        New list with recently failed tests first, in ranked order, tagged
        ``rule="recent failure"``; the other tests follow in ranked order.
    Raises:
        ValueError: If ``recent_failure_window`` is not a non-negative integer.
    """
    window = _non_negative_int(
        context.config, "recent_failure_window", DEFAULT_RECENT_FAILURE_WINDOW
    )
    failed = recently_failed(context.runs, context.results, window)
    return _promote(ranked, failed, "recent failure")


DEFAULT_ROTATION_LIMIT = 10


def compute_skip_debt(
    runs: Iterable[Record], results: Iterable[Record]
) -> dict[str, int]:
    """
    Return each test's skip debt: consecutive recent runs that did not run it.

    A test is selectable from the first run it appears in, so its debt counts
    the runs after the last run that has a result for it. Any result counts as
    run, including ``skipped``, which the test runner reported, not TestBudget.
    Args:
        runs: Run records from the history contract.
        results: Result records from the history contract; results for a sha
            not in ``runs`` are ignored.
    Returns:
        Mapping of test ID to skip debt, sorted by test ID. Tests with no
        result in history are absent and have no debt.
    """
    position = {sha: index for index, sha in enumerate(ordered_shas(runs))}
    last_run: dict[str, int] = {}
    for result in results:
        index = position.get(result["sha"])
        if index is not None:
            test_id = result["test_id"]
            last_run[test_id] = max(index, last_run.get(test_id, index))
    newest = len(position) - 1
    return {test_id: newest - last_run[test_id] for test_id in sorted(last_run)}


def apply_rotation_limit(
    ranked: Iterable[Mapping[str, Any]], context: RuleContext
) -> list[RankedTest]:
    """
    Force in every test whose skip debt has reached the rotation limit.

    Args:
        ranked: Output of ``ranker.rank_tests``.
        context: Rule context; reads ``runs``, ``results`` and
            ``config["rotation_limit"]`` (N, default 10).
    Returns:
        New list in the same order. Every test gets ``skip_debt`` (0 if it
        has no history) and ``forced``, which is True when
        ``skip_debt >= N``. The budget cut must never drop a forced test.
    Raises:
        ValueError: If ``rotation_limit`` is not a positive integer.
    """
    limit = _non_negative_int(context.config, "rotation_limit", DEFAULT_ROTATION_LIMIT)
    if limit == 0:
        raise ValueError("rotation_limit must be a positive integer, got 0")
    debt = compute_skip_debt(context.runs, context.results)
    tests: list[RankedTest] = []
    for test in ranked:
        copy = dict(test)
        copy["skip_debt"] = debt.get(copy["test_name"], 0)
        copy["forced"] = copy["skip_debt"] >= limit
        tests.append(copy)
    return tests
