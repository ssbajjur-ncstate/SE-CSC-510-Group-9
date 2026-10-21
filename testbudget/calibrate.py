"""Calibrate per-risk-level time budgets from replay results.

The replay CSV has one row per (failing run, budget fraction) with columns
``sha, risk_level, budget_fraction, caught``: ``caught`` is 1 if the subset
selected at that fraction of full-suite time ran a failing test.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypedDict

RISK_LEVELS = ("low", "medium", "high")
REPLAY_COLUMNS = ("sha", "risk_level", "budget_fraction", "caught")


class ReplayRow(TypedDict):
    """One row of the replay CSV."""

    sha: str
    risk_level: str
    budget_fraction: float
    caught: int


def _parse_row(raw: dict[str, str | None], where: str) -> ReplayRow:
    """Validate one CSV row and convert its fields."""
    sha = (raw["sha"] or "").strip()
    if not sha:
        raise ValueError(f"{where}: sha is empty")
    level = (raw["risk_level"] or "").strip()
    if level not in RISK_LEVELS:
        raise ValueError(
            f"{where}: risk_level must be one of {', '.join(RISK_LEVELS)}, "
            f"got {level!r}"
        )
    text = (raw["budget_fraction"] or "").strip()
    try:
        fraction = float(text)
    except ValueError:
        raise ValueError(
            f"{where}: budget_fraction is not a number: {text!r}"
        ) from None
    if not math.isfinite(fraction) or not 0.0 < fraction <= 1.0:
        raise ValueError(f"{where}: budget_fraction must be in (0, 1], got {text}")
    caught = (raw["caught"] or "").strip()
    if caught not in ("0", "1"):
        raise ValueError(f"{where}: caught must be 0 or 1, got {caught!r}")
    return {
        "sha": sha,
        "risk_level": level,
        "budget_fraction": fraction,
        "caught": int(caught),
    }


def read_replay_csv(path: str | Path) -> list[ReplayRow]:
    """
    Read and validate a replay CSV.

    Args:
        path: CSV file with a header containing ``sha``, ``risk_level``,
            ``budget_fraction`` and ``caught``; other columns are ignored.
    Returns:
        One row per data line, in file order.
    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file is empty, a column is missing, or a row has a
            bad value; the message names the file and line.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"replay CSV not found: {path}")
    with path.open(encoding="utf-8", newline="") as file:
        reader = csv.DictReader(file)
        header = reader.fieldnames or []
        if not header:
            raise ValueError(f"{path}: replay CSV is empty")
        missing = [column for column in REPLAY_COLUMNS if column not in header]
        if missing:
            raise ValueError(
                f"{path}: replay CSV is missing columns: {', '.join(missing)}"
            )
        rows = [
            _parse_row(raw, f"{path}:{reader.line_num}")
            for raw in reader
            if any((value or "").strip() for value in raw.values())
        ]
    if not rows:
        raise ValueError(f"{path}: replay CSV has a header but no rows")
    return rows


@dataclass(frozen=True)
class CalibrationParams:
    """
    Settings for ``calibrate``, as in ``testbudget.yml``.

    Attributes:
        target_catch_rate: Share of failing runs the budget must catch.
        floor: Smallest budget fraction ever used.
        ceiling: Largest budget fraction ever used.
        min_failing_runs: Failing runs a level needs to be calibrated.
    """

    target_catch_rate: float = 0.9
    floor: float = 0.1
    ceiling: float = 0.6
    min_failing_runs: int = 10

    def __post_init__(self) -> None:
        """Reject settings that cannot produce a budget."""
        if not 0.0 < self.target_catch_rate <= 1.0:
            raise ValueError(
                f"target_catch_rate must be in (0, 1], got {self.target_catch_rate}"
            )
        if not 0.0 <= self.floor <= self.ceiling <= 1.0:
            raise ValueError(
                "floor and ceiling must satisfy 0 <= floor <= ceiling <= 1, "
                f"got floor={self.floor}, ceiling={self.ceiling}"
            )
        if isinstance(self.min_failing_runs, bool) or self.min_failing_runs < 1:
            raise ValueError(
                "min_failing_runs must be a positive integer, "
                f"got {self.min_failing_runs}"
            )


class LevelBudget(TypedDict):
    """Calibrated budget for one risk level."""

    budget_fraction: float
    calibrated: bool
    catch_rate: float | None
    failing_runs: int
    note: str


def catch_rates(rows: Iterable[ReplayRow], risk_level: str) -> dict[float, float]:
    """
    Return the catch rate at each budget fraction for one risk level.

    Args:
        rows: Replay rows from ``read_replay_csv``.
        risk_level: ``low``, ``medium`` or ``high``.
    Returns:
        Mapping of budget fraction to the share of that level's rows at that
        fraction with ``caught == 1``, sorted by fraction.
    """
    caught: dict[float, list[int]] = {}
    for row in rows:
        if row["risk_level"] == risk_level:
            # Round so 0.30000000000000004 and 0.3 are one fraction.
            fraction = round(row["budget_fraction"], 6)
            caught.setdefault(fraction, []).append(row["caught"])
    return {
        fraction: sum(values) / len(values)
        for fraction, values in sorted(caught.items())
    }


def _clamp(
    fraction: float, rate: float, params: CalibrationParams
) -> tuple[float, str]:
    """Apply floor and ceiling to a fraction that met the target."""
    if fraction < params.floor:
        return params.floor, f"met target at {fraction:g}; raised to floor"
    if fraction > params.ceiling:
        return params.ceiling, f"met target at {fraction:g}; capped at ceiling"
    return fraction, f"met target at {fraction:g} (catch rate {rate:.3f})"


def _calibrate_level(
    rows: list[ReplayRow], level: str, params: CalibrationParams
) -> LevelBudget:
    """Return the budget of a level with enough failing runs."""
    rates = catch_rates(rows, level)
    failing = len({row["sha"] for row in rows if row["risk_level"] == level})
    met = [f for f, rate in rates.items() if rate >= params.target_catch_rate]
    if not met:
        return {
            "budget_fraction": params.ceiling,
            "calibrated": True,
            "catch_rate": max(rates.values()),
            "failing_runs": failing,
            "note": "target not met at any fraction; using ceiling",
        }
    fraction, note = _clamp(met[0], rates[met[0]], params)
    return {
        "budget_fraction": fraction,
        "calibrated": True,
        "catch_rate": rates[met[0]],
        "failing_runs": failing,
        "note": note,
    }


def calibrate(
    rows: Iterable[ReplayRow], params: CalibrationParams | None = None
) -> dict[str, LevelBudget]:
    """
    Return the budget fraction for each risk level.

    For each level, the budget is the smallest fraction whose catch rate is
    at least ``target_catch_rate``, clamped to ``[floor, ceiling]``; if no
    fraction meets the target, the ceiling. A level with fewer than
    ``min_failing_runs`` distinct failing runs is not calibrated: it inherits
    the next-higher level's budget, and ``high`` falls back to the ceiling.
    Args:
        rows: Replay rows from ``read_replay_csv``.
        params: Calibration settings; defaults to ``CalibrationParams()``.
    Returns:
        ``low``, ``medium`` and ``high`` mapped to their ``LevelBudget``.
    Raises:
        ValueError: If ``rows`` is empty.
    """
    params = params or CalibrationParams()
    rows = list(rows)
    if not rows:
        raise ValueError("cannot calibrate from an empty replay")
    budgets: dict[str, LevelBudget] = {}
    higher: str | None = None
    for level in reversed(RISK_LEVELS):
        failing = len({row["sha"] for row in rows if row["risk_level"] == level})
        if failing >= params.min_failing_runs:
            budgets[level] = _calibrate_level(rows, level, params)
        else:
            if higher is None:
                fraction, source = params.ceiling, "using ceiling"
            else:
                fraction = budgets[higher]["budget_fraction"]
                source = f"inherited from {higher}"
            budgets[level] = {
                "budget_fraction": fraction,
                "calibrated": False,
                "catch_rate": None,
                "failing_runs": failing,
                "note": f"{failing} of {params.min_failing_runs} failing runs; "
                f"{source}",
            }
        higher = level
    return {level: budgets[level] for level in RISK_LEVELS}
