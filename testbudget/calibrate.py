"""Calibrate per-risk-level time budgets from replay results.

The replay CSV has one row per (failing run, budget fraction) with columns
``sha, risk_level, budget_fraction, caught``: ``caught`` is 1 if the subset
selected at that fraction of full-suite time ran a failing test.
"""

from __future__ import annotations

import csv
import math
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
