import csv
import json
from pathlib import Path

from testbudget.replay import (
    BUDGET_FRACTION,
    replay_details,
    run_evaluation,
)


def write_jsonl(path, rows):
    path.write_text(
        "".join(
            json.dumps(row) + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )


def test_temporal_replay_uses_only_prior_runs():
    runs = [
        {
            "sha": "a1",
            "timestamp": "2026-01-01T00:00:00Z",
            "branch": "main",
            "changed_files": ["src/a.py"],
        },
        {
            "sha": "a2",
            "timestamp": "2026-01-02T00:00:00Z",
            "branch": "main",
            "changed_files": ["src/a.py"],
        },
        {
            "sha": "a3",
            "timestamp": "2026-01-03T00:00:00Z",
            "branch": "main",
            "changed_files": ["src/a.py"],
        },
    ]

    results = [
        {
            "sha": "a1",
            "test_id": "tests/test_a.py::test_a",
            "status": "passed",
            "duration_s": 1.0,
            "attempt": 1,
        },
        {
            "sha": "a2",
            "test_id": "tests/test_a.py::test_a",
            "status": "failed",
            "duration_s": 1.0,
            "attempt": 1,
        },
        {
            "sha": "a3",
            "test_id": "tests/test_a.py::test_a",
            "status": "failed",
            "duration_s": 1.0,
            "attempt": 1,
        },
    ]

    rows = replay_details(
        runs,
        results,
    )

    a2 = [
        row
        for row in rows
        if row["sha"] == "a2"
        and row["method"] == "testbudget"
    ][0]

    a3 = [
        row
        for row in rows
        if row["sha"] == "a3"
        and row["method"] == "testbudget"
    ][0]

    assert a2["history_runs_used"] == 1
    assert a3["history_runs_used"] == 2


def test_replay_uses_thirty_percent_budget():
    runs = [
        {
            "sha": "a1",
            "timestamp": "2026-01-01T00:00:00Z",
            "branch": "main",
            "changed_files": [],
        }
    ]

    results = [
        {
            "sha": "a1",
            "test_id": "tests/test_a.py::test_a",
            "status": "failed",
            "duration_s": 1.0,
            "attempt": 1,
        }
    ]

    rows = replay_details(
        runs,
        results,
    )

    assert rows
    assert all(
        row["budget_fraction"]
        == BUDGET_FRACTION
        for row in rows
    )


def test_make_eval_output_has_all_methods(tmp_path):
    history = tmp_path / "history"
    history.mkdir()

    write_jsonl(
        history / "runs.jsonl",
        [
            {
                "sha": "a1",
                "timestamp":
                    "2026-01-01T00:00:00Z",
                "branch": "main",
                "changed_files": ["src/a.py"],
            },
            {
                "sha": "a2",
                "timestamp":
                    "2026-01-02T00:00:00Z",
                "branch": "main",
                "changed_files": ["src/a.py"],
            },
        ],
    )

    write_jsonl(
        history / "results.jsonl",
        [
            {
                "sha": "a1",
                "test_id":
                    "tests/test_a.py::test_a",
                "status": "passed",
                "duration_s": 1.0,
                "attempt": 1,
            },
            {
                "sha": "a2",
                "test_id":
                    "tests/test_a.py::test_a",
                "status": "failed",
                "duration_s": 1.0,
                "attempt": 1,
            },
        ],
    )

    output = tmp_path / "eval.csv"

    run_evaluation(
        history,
        output,
    )

    with output.open(
        newline="",
        encoding="utf-8",
    ) as handle:
        rows = list(
            csv.DictReader(handle)
        )

    methods = {
        row["method"]
        for row in rows
    }

    assert "testbudget" in methods
    assert "original" in methods
    assert "random" in methods
    assert "recently_failed" in methods
    assert "most_failed" in methods
    assert "recently_modified" in methods
    assert "import_only" in methods


def test_small_dataset_is_marked_insufficient(tmp_path):
    history = tmp_path / "history"
    history.mkdir()

    write_jsonl(
        history / "runs.jsonl",
        [
            {
                "sha": "a1",
                "timestamp":
                    "2026-01-01T00:00:00Z",
                "branch": "main",
                "changed_files": [],
            }
        ],
    )

    write_jsonl(
        history / "results.jsonl",
        [
            {
                "sha": "a1",
                "test_id":
                    "tests/test_a.py::test_a",
                "status": "failed",
                "duration_s": 1.0,
                "attempt": 1,
            }
        ],
    )

    output = tmp_path / "eval.csv"

    rows = run_evaluation(
        history,
        output,
    )

    assert rows

    assert all(
        row["data_quality"].startswith(
            "insufficient"
        )
        for row in rows
    )