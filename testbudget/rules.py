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
