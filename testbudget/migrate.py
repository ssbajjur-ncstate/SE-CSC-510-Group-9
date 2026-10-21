import hashlib
import sqlite3
from pathlib import Path


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

    rows = connection.execute(
        "PRAGMA table_info(test_runs)"
    ).fetchall()

    if not rows:
        raise LegacyMigrationError(
            "legacy database does not contain a test_runs table"
        )

    return {
        row[1]
        for row in rows
    }


def _validate_legacy_schema(connection):
    """
    Ensure the legacy database contains the columns required for migration.

    Raises:
        LegacyMigrationError:
            If required legacy columns are missing.
    """

    columns = _get_legacy_columns(
        connection
    )

    missing = sorted(
        LEGACY_REQUIRED_COLUMNS - columns
    )

    if missing:
        raise LegacyMigrationError(
            "legacy test_runs table is missing required columns: "
            + ", ".join(missing)
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

    if (
        not isinstance(test_name, str)
        or not test_name.strip()
    ):
        raise LegacyMigrationError(
            "legacy test result has an empty test_name"
        )

    test_name = test_name.strip()

    if (
        isinstance(test_file, str)
        and test_file.strip()
    ):
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

    raw_value = (
        f"{created_at}\0"
        f"{changed_file or ''}"
    )

    digest = hashlib.sha1(
        raw_value.encode("utf-8")
    ).hexdigest()

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
        raise LegacyMigrationError(
            f"legacy database does not exist: {db_path}"
        )

    connection = sqlite3.connect(
        db_path
    )

    connection.row_factory = (
        sqlite3.Row
    )

    try:
        _validate_legacy_schema(
            connection
        )

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

    groups = {}

    for row in rows:
        created_at = row["created_at"]
        changed_file = row["changed_file"]

        if (
            not isinstance(created_at, str)
            or not created_at.strip()
        ):
            raise LegacyMigrationError(
                f"legacy row {row['id']} "
                "has no created_at timestamp"
            )

        status = row["status"]

        if status not in ALLOWED_STATUSES:
            raise LegacyMigrationError(
                f"legacy row {row['id']} "
                f"has unsupported status: {status}"
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
            raise LegacyMigrationError(
                f"legacy row {row['id']} "
                "has invalid duration"
            )

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

        if (
            isinstance(changed_file, str)
            and changed_file.strip()
        ):
            changed_files.append(
                changed_file.strip()
            )

        runs.append(
            {
                "sha": sha,
                "timestamp": created_at,
                "branch": "legacy",
                "changed_files": (
                    changed_files
                ),
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
                    "status": row[
                        "status"
                    ],
                    "duration_s": float(
                        row["duration"]
                    ),
                    "attempt": 1,
                }
            )

    return runs, results