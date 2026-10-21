import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

from testbudget.db import (
    HistoryFormatError,
    load_history_records,
)


class LegacyMigrationError(ValueError):
    """
    Raised when legacy TestBudget history cannot be migrated safely.
    """


LEGACY_REQUIRED_COLUMNS = {
    "id",
    "test_name",
    "test_file",
    "status",
    "duration",
    "changed_file",
    "created_at",
}

ALLOWED_STATUSES = {
    "passed",
    "failed",
    "skipped",
}


def _get_legacy_columns(connection):
    """
    Return column names from the legacy `test_runs` table.

    Raises:
        LegacyMigrationError:
            If the legacy table does not exist.
    """

    rows = connection.execute("PRAGMA table_info(test_runs)").fetchall()

    if not rows:
        raise LegacyMigrationError("legacy database does not contain a test_runs table")

    return {row[1] for row in rows}


def _validate_legacy_schema(connection):
    """
    Ensure the legacy database contains the columns required for migration.

    Raises:
        LegacyMigrationError:
            If required legacy columns are missing.
    """

    columns = _get_legacy_columns(connection)

    missing = sorted(LEGACY_REQUIRED_COLUMNS - columns)

    if missing:
        raise LegacyMigrationError(
            "legacy test_runs table is missing required columns: " + ", ".join(missing)
        )


def _legacy_test_id(
    test_file,
    test_name,
):
    """
    Convert the prototype test identity into TestBudget's stable test_id.

    Legacy pytest classnames such as:

        tests.test_checkout

    become:

        tests/test_checkout.py::test_checkout_success

    If the old row has no test file, a stable legacy fallback path is used.
    """

    if not isinstance(test_name, str) or not test_name.strip():
        raise LegacyMigrationError("legacy test result has an empty test_name")

    test_name = test_name.strip()

    # Rows ingested after #128 already hold the path::name ID.
    if "::" in test_name:
        return test_name

    if isinstance(test_file, str) and test_file.strip():
        test_file = test_file.strip()

        if test_file.endswith(".py"):
            path = test_file

        else:
            path = test_file.replace(
                ".",
                "/",
            )

            if not path.endswith(".py"):
                path += ".py"

    else:
        path = "legacy/unknown.py"

    return f"{path}::{test_name}"


def _legacy_run_sha(
    created_at,
    changed_file,
):
    """
    Generate a deterministic synthetic run ID for a legacy run.

    The prototype did not record a real Git SHA. Prefixing the digest with
    `legacy-` makes that limitation explicit instead of pretending the value
    is an actual commit SHA.
    """

    raw_value = f"{created_at}\0{changed_file or ''}"

    digest = hashlib.sha1(raw_value.encode("utf-8")).hexdigest()

    return f"legacy-{digest}"


def read_legacy_history(db_path):
    """
    Read prototype SQLite history and convert it into the new history model.

    Legacy rows are grouped by `(created_at, changed_file)`. The prototype
    did not explicitly store a CI run identifier, so this is the most
    reproducible run boundary available from the old schema.

    Args:
        db_path:
            Path to the legacy SQLite database.

    Returns:
        A tuple `(runs, results)` containing dictionaries that follow the
        new JSONL history contracts.

    Raises:
        LegacyMigrationError:
            If the database is missing, malformed, or contains invalid data.
    """

    db_path = Path(db_path)

    if not db_path.exists():
        raise LegacyMigrationError(f"legacy database does not exist: {db_path}")

    connection = sqlite3.connect(db_path)

    connection.row_factory = sqlite3.Row

    try:
        _validate_legacy_schema(connection)

        rows = connection.execute(
            """
            SELECT
                id,
                test_name,
                test_file,
                status,
                duration,
                changed_file,
                created_at

            FROM test_runs

            ORDER BY
                created_at,
                changed_file,
                id
            """
        ).fetchall()

    finally:
        connection.close()

    groups: dict[tuple[str, str | None], list[sqlite3.Row]] = {}

    for row in rows:
        created_at = row["created_at"]
        changed_file = row["changed_file"]

        if not isinstance(created_at, str) or not created_at.strip():
            raise LegacyMigrationError(
                f"legacy row {row['id']} has no created_at timestamp"
            )

        status = row["status"]

        if status not in ALLOWED_STATUSES:
            raise LegacyMigrationError(
                f"legacy row {row['id']} has unsupported status: {status}"
            )

        duration = row["duration"]

        if (
            isinstance(duration, bool)
            or not isinstance(
                duration,
                (int, float),
            )
            or duration < 0
        ):
            raise LegacyMigrationError(f"legacy row {row['id']} has invalid duration")

        key = (
            created_at,
            changed_file,
        )

        if key not in groups:
            groups[key] = []

        groups[key].append(row)

    runs = []
    results = []

    for (
        created_at,
        changed_file,
    ), group_rows in groups.items():
        sha = _legacy_run_sha(
            created_at,
            changed_file,
        )

        changed_files = []

        if isinstance(changed_file, str) and changed_file.strip():
            changed_files.append(changed_file.strip())

        runs.append(
            {
                "sha": sha,
                "timestamp": created_at,
                "branch": "legacy",
                "changed_files": (changed_files),
            }
        )

        for row in group_rows:
            results.append(
                {
                    "sha": sha,
                    "test_id": (
                        _legacy_test_id(
                            row["test_file"],
                            row["test_name"],
                        )
                    ),
                    "status": row["status"],
                    "duration_s": float(row["duration"]),
                    "attempt": 1,
                }
            )

    return runs, results


def _write_jsonl(
    path,
    records,
):
    """
    Write a sequence of dictionaries to a JSONL file.
    """

    path = Path(path)

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
                json.dumps(
                    record,
                    sort_keys=True,
                )
            )

            file.write("\n")


def migrate_legacy_history(
    db_path,
    history_dir="history",
):
    """
    Migrate prototype SQLite history into committed JSONL history.

    Existing JSONL history is preserved. Legacy runs that have already
    been migrated are skipped, making migration idempotent.

    The source SQLite database is opened read-only from the application's
    perspective and is never modified or deleted.

    Args:
        db_path:
            Path to the legacy SQLite database.

        history_dir:
            Directory containing runs.jsonl and results.jsonl.

    Returns:
        A summary dictionary containing:
        - legacy_runs_found
        - legacy_results_found
        - runs_added
        - results_added
        - runs_skipped

    Raises:
        LegacyMigrationError:
            If the legacy database cannot be interpreted.

        HistoryFormatError:
            If the existing or generated JSONL history is invalid.
    """

    history_dir = Path(history_dir)

    history_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    existing_runs, existing_results = load_history_records(history_dir)

    legacy_runs, legacy_results = read_legacy_history(db_path)

    existing_shas = {run["sha"] for run in existing_runs}

    new_runs = [run for run in legacy_runs if run["sha"] not in existing_shas]

    new_shas = {run["sha"] for run in new_runs}

    new_results = [result for result in legacy_results if result["sha"] in new_shas]

    combined_runs = existing_runs + new_runs

    combined_results = existing_results + new_results

    # Build and validate the complete candidate history in a temporary
    # directory before replacing the repository history files.
    #
    # This prevents malformed migration output from partially corrupting
    # the committed history.

    with tempfile.TemporaryDirectory(dir=history_dir.parent) as temp_directory:
        temp_history = Path(temp_directory)

        temp_runs = temp_history / "runs.jsonl"

        temp_results = temp_history / "results.jsonl"

        _write_jsonl(
            temp_runs,
            combined_runs,
        )

        _write_jsonl(
            temp_results,
            combined_results,
        )

        # Reuse the canonical loader from PR 1 as the validation oracle.
        load_history_records(temp_history)

        target_runs = history_dir / "runs.jsonl"

        target_results = history_dir / "results.jsonl"

        shutil.copyfile(
            temp_runs,
            target_runs,
        )

        shutil.copyfile(
            temp_results,
            target_results,
        )

    return {
        "legacy_runs_found": len(legacy_runs),
        "legacy_results_found": len(legacy_results),
        "runs_added": len(new_runs),
        "results_added": len(new_results),
        "runs_skipped": (len(legacy_runs) - len(new_runs)),
    }


def build_parser():
    """
    Build the command-line parser for legacy history migration.
    """

    parser = argparse.ArgumentParser(
        description=(
            "Migrate TestBudget's prototype SQLite history "
            "into committed JSONL history."
        )
    )

    parser.add_argument(
        "--db",
        required=True,
        help=("Path to the legacy SQLite database."),
    )

    parser.add_argument(
        "--history-dir",
        default="history",
        help=("Directory containing runs.jsonl and results.jsonl (default: history)."),
    )

    return parser


def main(argv=None):
    """
    Run the legacy history migration command.
    """

    parser = build_parser()

    args = parser.parse_args(argv)

    try:
        summary = migrate_legacy_history(
            db_path=args.db,
            history_dir=(args.history_dir),
        )

    except (
        LegacyMigrationError,
        HistoryFormatError,
    ) as error:
        print(
            f"Migration failed: {error}",
            file=sys.stderr,
        )

        return 1

    print("TESTBUDGET LEGACY HISTORY MIGRATION")

    print(f"Legacy runs found: {summary['legacy_runs_found']}")

    print(f"Legacy results found: {summary['legacy_results_found']}")

    print(f"Runs added: {summary['runs_added']}")

    print(f"Results added: {summary['results_added']}")

    print(f"Runs already migrated: {summary['runs_skipped']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
