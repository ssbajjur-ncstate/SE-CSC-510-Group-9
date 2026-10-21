import json

import pytest

from testbudget.db import (
    HistoryFormatError,
    get_history_test_stats,
    load_history_records,
    rebuild_history_db,
)


def write_jsonl(path, records):
    """
    Write dictionaries to a JSONL fixture file.
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with path.open(
        "w",
        encoding="utf-8",
    ) as file:
        for record in records:
            file.write(
                json.dumps(record)
            )
            file.write("\n")


def make_valid_history(tmp_path):
    """
    Create a small valid TestBudget history fixture.
    """

    history_dir = tmp_path / "history"

    runs = [
        {
            "sha": "abc123",
            "timestamp": "2026-10-20T10:00:00Z",
            "branch": "main",
            "changed_files": [
                "src/checkout.py",
                "src/payment.py",
            ],
        },
        {
            "sha": "def456",
            "timestamp": "2026-10-21T10:00:00Z",
            "branch": "feature/cart",
            "changed_files": [
                "src/cart.py",
            ],
        },
    ]

    results = [
        {
            "sha": "abc123",
            "test_id": (
                "tests/test_checkout.py"
                "::test_checkout_success"
            ),
            "status": "passed",
            "duration_s": 2.0,
            "attempt": 1,
        },
        {
            "sha": "abc123",
            "test_id": (
                "tests/test_checkout.py"
                "::test_checkout_invalid_card"
            ),
            "status": "failed",
            "duration_s": 3.0,
            "attempt": 1,
        },
        {
            "sha": "def456",
            "test_id": (
                "tests/test_checkout.py"
                "::test_checkout_invalid_card"
            ),
            "status": "passed",
            "duration_s": 1.0,
            "attempt": 1,
        },
    ]

    write_jsonl(
        history_dir / "runs.jsonl",
        runs,
    )

    write_jsonl(
        history_dir / "results.jsonl",
        results,
    )

    return history_dir


def test_load_history_records(
    tmp_path,
):
    history_dir = make_valid_history(
        tmp_path
    )

    runs, results = load_history_records(
        history_dir
    )

    assert len(runs) == 2
    assert len(results) == 3

    assert runs[0]["sha"] == "abc123"

    assert (
        results[1]["status"]
        == "failed"
    )


def test_rebuild_history_db(
    tmp_path,
):
    history_dir = make_valid_history(
        tmp_path
    )

    connection = rebuild_history_db(
        history_dir
    )

    run_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM runs
        """
    ).fetchone()[0]

    result_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM results
        """
    ).fetchone()[0]

    connection.close()

    assert run_count == 2
    assert result_count == 3


def test_history_stats(
    tmp_path,
):
    history_dir = make_valid_history(
        tmp_path
    )

    stats = get_history_test_stats(
        history_dir
    )

    invalid_card = next(
        item
        for item in stats
        if item["test_id"]
        == (
            "tests/test_checkout.py"
            "::test_checkout_invalid_card"
        )
    )

    assert invalid_card["run_count"] == 2
    assert (
        invalid_card["failure_count"]
        == 1
    )
    assert (
        invalid_card["avg_duration"]
        == 2.0
    )


def test_empty_history_is_allowed(
    tmp_path,
):
    history_dir = (
        tmp_path / "history"
    )

    runs, results = load_history_records(
        history_dir
    )

    assert runs == []
    assert results == []

    connection = rebuild_history_db(
        history_dir
    )

    run_count = connection.execute(
        "SELECT COUNT(*) FROM runs"
    ).fetchone()[0]

    connection.close()

    assert run_count == 0


def test_corrupt_jsonl_raises_error(
    tmp_path,
):
    history_dir = (
        tmp_path / "history"
    )

    history_dir.mkdir()

    (
        history_dir / "runs.jsonl"
    ).write_text(
        '{"sha": "abc123"\n',
        encoding="utf-8",
    )

    with pytest.raises(
        HistoryFormatError,
        match="invalid JSON",
    ):
        load_history_records(
            history_dir
        )


def test_duplicate_run_sha_raises_error(
    tmp_path,
):
    history_dir = (
        tmp_path / "history"
    )

    duplicate_runs = [
        {
            "sha": "abc123",
            "timestamp": "2026-10-20T10:00:00Z",
            "branch": "main",
            "changed_files": [],
        },
        {
            "sha": "abc123",
            "timestamp": "2026-10-21T10:00:00Z",
            "branch": "main",
            "changed_files": [],
        },
    ]

    write_jsonl(
        history_dir / "runs.jsonl",
        duplicate_runs,
    )

    write_jsonl(
        history_dir / "results.jsonl",
        [],
    )

    with pytest.raises(
        HistoryFormatError,
        match="duplicate run sha",
    ):
        load_history_records(
            history_dir
        )


def test_result_with_unknown_sha_raises_error(
    tmp_path,
):
    history_dir = (
        tmp_path / "history"
    )

    write_jsonl(
        history_dir / "runs.jsonl",
        [],
    )

    write_jsonl(
        history_dir / "results.jsonl",
        [
            {
                "sha": "unknown123",
                "test_id": (
                    "tests/test_cart.py"
                    "::test_cart"
                ),
                "status": "failed",
                "duration_s": 1.0,
                "attempt": 1,
            }
        ],
    )

    with pytest.raises(
        HistoryFormatError,
        match="unknown sha",
    ):
        load_history_records(
            history_dir
        )


def test_negative_duration_raises_error(
    tmp_path,
):
    history_dir = (
        tmp_path / "history"
    )

    write_jsonl(
        history_dir / "runs.jsonl",
        [
            {
                "sha": "abc123",
                "timestamp": "2026-10-20T10:00:00Z",
                "branch": "main",
                "changed_files": [],
            }
        ],
    )

    write_jsonl(
        history_dir / "results.jsonl",
        [
            {
                "sha": "abc123",
                "test_id": (
                    "tests/test_cart.py"
                    "::test_cart"
                ),
                "status": "failed",
                "duration_s": -1,
                "attempt": 1,
            }
        ],
    )

    with pytest.raises(
        HistoryFormatError,
        match="non-negative",
    ):
        load_history_records(
            history_dir
        )