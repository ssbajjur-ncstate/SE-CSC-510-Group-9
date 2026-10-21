import json
import sqlite3

import pytest

from testbudget.db import (
    load_history_records,
)
from testbudget.migrate import (
    LegacyMigrationError,
    _legacy_test_id,
    main,
    migrate_legacy_history,
    read_legacy_history,
)


def create_legacy_db(
    path,
    rows,
):
    """
    Create a fixture database using TestBudget's prototype schema.
    """

    connection = sqlite3.connect(path)

    connection.execute(
        """
        CREATE TABLE test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            test_name TEXT NOT NULL,
            test_file TEXT,
            status TEXT NOT NULL,
            duration REAL NOT NULL,
            changed_file TEXT,
            created_at TEXT NOT NULL
        )
        """
    )

    connection.executemany(
        """
        INSERT INTO test_runs (
            test_name,
            test_file,
            status,
            duration,
            changed_file,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )

    connection.commit()
    connection.close()


def sample_rows():
    """
    Return a small prototype history fixture.
    """

    return [
        (
            "test_checkout_success",
            "tests.test_checkout",
            "passed",
            2.0,
            "src/checkout.py",
            "2026-10-20 10:00:00",
        ),
        (
            "test_checkout_invalid_card",
            "tests.test_checkout",
            "failed",
            3.0,
            "src/checkout.py",
            "2026-10-20 10:00:00",
        ),
        (
            "test_login_success",
            "tests.test_login",
            "passed",
            1.0,
            "src/auth.py",
            "2026-10-21 10:00:00",
        ),
    ]


def test_legacy_test_id_normalizes_pytest_classname():
    test_id = _legacy_test_id(
        "tests.test_checkout",
        "test_checkout_success",
    )

    assert test_id == ("tests/test_checkout.py::test_checkout_success")


def test_read_legacy_history_groups_rows_into_runs(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    create_legacy_db(
        db_path,
        sample_rows(),
    )

    runs, results = read_legacy_history(db_path)

    assert len(runs) == 2
    assert len(results) == 3

    checkout_run = next(
        run for run in runs if run["changed_files"] == ["src/checkout.py"]
    )

    assert checkout_run["branch"] == "legacy"

    assert checkout_run["sha"].startswith("legacy-")


def test_legacy_results_reference_generated_run(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    create_legacy_db(
        db_path,
        sample_rows(),
    )

    runs, results = read_legacy_history(db_path)

    run_shas = {run["sha"] for run in runs}

    assert all(result["sha"] in run_shas for result in results)

    assert all(result["attempt"] == 1 for result in results)


def test_migration_writes_valid_jsonl_history(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    history_dir = tmp_path / "history"

    create_legacy_db(
        db_path,
        sample_rows(),
    )

    summary = migrate_legacy_history(
        db_path,
        history_dir,
    )

    assert summary["runs_added"] == 2

    assert summary["results_added"] == 3

    runs, results = load_history_records(history_dir)

    assert len(runs) == 2
    assert len(results) == 3


def test_migration_is_idempotent(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    history_dir = tmp_path / "history"

    create_legacy_db(
        db_path,
        sample_rows(),
    )

    migrate_legacy_history(
        db_path,
        history_dir,
    )

    second = migrate_legacy_history(
        db_path,
        history_dir,
    )

    assert second["runs_added"] == 0

    assert second["results_added"] == 0

    assert second["runs_skipped"] == 2

    runs, results = load_history_records(history_dir)

    assert len(runs) == 2
    assert len(results) == 3


def test_migration_preserves_existing_history(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    history_dir = tmp_path / "history"

    history_dir.mkdir()

    create_legacy_db(
        db_path,
        sample_rows(),
    )

    existing_run = {
        "sha": "real123",
        "timestamp": ("2026-10-19T10:00:00Z"),
        "branch": "main",
        "changed_files": ["src/cart.py"],
    }

    existing_result = {
        "sha": "real123",
        "test_id": ("tests/test_cart.py::test_add_item"),
        "status": "passed",
        "duration_s": 0.5,
        "attempt": 1,
    }

    (history_dir / "runs.jsonl").write_text(
        json.dumps(existing_run) + "\n",
        encoding="utf-8",
    )

    (history_dir / "results.jsonl").write_text(
        json.dumps(existing_result) + "\n",
        encoding="utf-8",
    )

    migrate_legacy_history(
        db_path,
        history_dir,
    )

    runs, results = load_history_records(history_dir)

    assert any(run["sha"] == "real123" for run in runs)

    assert any(result["sha"] == "real123" for result in results)

    assert len(runs) == 3
    assert len(results) == 4


def test_missing_database_raises_error(
    tmp_path,
):
    missing = tmp_path / "missing.db"

    with pytest.raises(
        LegacyMigrationError,
        match="does not exist",
    ):
        read_legacy_history(missing)


def test_missing_test_runs_table_raises_error(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE something_else (
            id INTEGER PRIMARY KEY
        )
        """
    )

    connection.commit()
    connection.close()

    with pytest.raises(
        LegacyMigrationError,
        match="test_runs table",
    ):
        read_legacy_history(db_path)


def test_incomplete_legacy_schema_raises_error(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    connection = sqlite3.connect(db_path)

    connection.execute(
        """
        CREATE TABLE test_runs (
            id INTEGER PRIMARY KEY,
            test_name TEXT
        )
        """
    )

    connection.commit()
    connection.close()

    with pytest.raises(
        LegacyMigrationError,
        match="missing required columns",
    ):
        read_legacy_history(db_path)


def test_invalid_legacy_status_raises_error(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    rows = [
        (
            "test_checkout",
            "tests.test_checkout",
            "broken",
            1.0,
            "src/checkout.py",
            "2026-10-20 10:00:00",
        )
    ]

    create_legacy_db(
        db_path,
        rows,
    )

    with pytest.raises(
        LegacyMigrationError,
        match="unsupported status",
    ):
        read_legacy_history(db_path)


def test_negative_legacy_duration_raises_error(
    tmp_path,
):
    db_path = tmp_path / "legacy.db"

    rows = [
        (
            "test_checkout",
            "tests.test_checkout",
            "passed",
            -1.0,
            "src/checkout.py",
            "2026-10-20 10:00:00",
        )
    ]

    create_legacy_db(
        db_path,
        rows,
    )

    with pytest.raises(
        LegacyMigrationError,
        match="invalid duration",
    ):
        read_legacy_history(db_path)


def test_cli_reports_success(
    tmp_path,
    capsys,
):
    db_path = tmp_path / "legacy.db"

    history_dir = tmp_path / "history"

    create_legacy_db(
        db_path,
        sample_rows(),
    )

    exit_code = main(
        [
            "--db",
            str(db_path),
            "--history-dir",
            str(history_dir),
        ]
    )

    output = capsys.readouterr()

    assert exit_code == 0

    assert "TESTBUDGET LEGACY HISTORY MIGRATION" in output.out

    assert "Runs added: 2" in output.out
