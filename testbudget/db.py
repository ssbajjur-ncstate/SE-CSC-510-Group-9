import json
import sqlite3
from pathlib import Path


def get_connection(db_path):
    """
    Create and return a SQLite connection.
    """

    connection = sqlite3.connect(db_path)

    # Makes query results easier to work with:
    # row["test_name"] instead of row[0]
    connection.row_factory = sqlite3.Row

    return connection


def init_db(db_path):
    """
    Initialize the TestBudget SQLite database.
    """

    connection = get_connection(db_path)

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS test_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            test_name TEXT NOT NULL,

            test_file TEXT,

            status TEXT NOT NULL
                CHECK(status IN ('passed', 'failed', 'skipped')),

            duration REAL NOT NULL
                CHECK(duration >= 0),

            changed_file TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


def insert_test_results(db_path, results, changed_file=None):
    """
    Insert normalized test results into SQLite.

    Returns the number of inserted rows.
    """

    init_db(db_path)

    connection = get_connection(db_path)

    rows = []

    for result in results:
        rows.append(
            (
                result["test_name"],
                result.get("test_file", ""),
                result["status"],
                float(result["duration"]),
                changed_file,
            )
        )

    connection.executemany(
        """
        INSERT INTO test_runs (
            test_name,
            test_file,
            status,
            duration,
            changed_file
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )

    connection.commit()

    inserted_count = len(rows)

    connection.close()

    return inserted_count


def get_all_results(db_path):
    """
    Return all stored test executions.
    """

    init_db(db_path)

    connection = get_connection(db_path)

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
        ORDER BY id
        """
    ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


def get_test_stats(db_path):
    """
    Return historical statistics for every test.

    These statistics will later be consumed by the
    TestBudget ranking subsystem.
    """

    init_db(db_path)

    connection = get_connection(db_path)

    rows = connection.execute(
        """
        SELECT
            test_name,

            COUNT(*) AS run_count,

            SUM(
                CASE
                    WHEN status = 'failed' THEN 1
                    ELSE 0
                END
            ) AS failure_count,

            AVG(duration) AS avg_duration,

            MAX(created_at) AS last_seen

        FROM test_runs

        GROUP BY test_name

        ORDER BY test_name
        """
    ).fetchall()

    connection.close()

    stats = []

    for row in rows:
        stats.append(
            {
                "test_name": row["test_name"],
                "run_count": row["run_count"],
                "failure_count": row["failure_count"],
                "avg_duration": round(row["avg_duration"], 3),
                "last_seen": row["last_seen"],
            }
        )

    return stats


class HistoryFormatError(ValueError):
    """
    Raised when a TestBudget history file violates the JSONL history contract.
    """


RUN_REQUIRED_FIELDS = {
    "sha",
    "timestamp",
    "branch",
    "changed_files",
}

RESULT_REQUIRED_FIELDS = {
    "sha",
    "test_id",
    "status",
    "duration_s",
    "attempt",
}

ALLOWED_RESULT_STATUSES = {
    "passed",
    "failed",
    "skipped",
}


def _read_jsonl(path):
    """
    Read JSON objects from a JSONL file.

    Blank lines are ignored. Missing files are treated as empty history.

    Returns:
        A list of tuples containing:
        (line_number, parsed_record)

    Raises:
        HistoryFormatError:
            If a non-empty line is not valid JSON or is not a JSON object.
    """

    path = Path(path)

    if not path.exists():
        return []

    records = []

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        for line_number, line in enumerate(
            file,
            start=1,
        ):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                record = json.loads(stripped)
            except json.JSONDecodeError as error:
                raise HistoryFormatError(
                    f"{path}:{line_number}: invalid JSON"
                ) from error

            if not isinstance(record, dict):
                raise HistoryFormatError(
                    f"{path}:{line_number}: history row must be a JSON object"
                )

            records.append(
                (
                    line_number,
                    record,
                )
            )

    return records


def _require_fields(
    record,
    required_fields,
    path,
    line_number,
):
    """
    Validate that a history record contains all required fields.
    """

    missing = sorted(required_fields - record.keys())

    if missing:
        raise HistoryFormatError(
            f"{path}:{line_number}: missing required fields: {', '.join(missing)}"
        )


def _validate_run_record(
    record,
    path,
    line_number,
):
    """
    Validate one runs.jsonl record.
    """

    _require_fields(
        record,
        RUN_REQUIRED_FIELDS,
        path,
        line_number,
    )

    sha = record["sha"]
    timestamp = record["timestamp"]
    branch = record["branch"]
    changed_files = record["changed_files"]

    if not isinstance(sha, str) or not sha.strip():
        raise HistoryFormatError(
            f"{path}:{line_number}: sha must be a non-empty string"
        )

    if not isinstance(timestamp, str) or not timestamp.strip():
        raise HistoryFormatError(
            f"{path}:{line_number}: timestamp must be a non-empty string"
        )

    if not isinstance(branch, str) or not branch.strip():
        raise HistoryFormatError(
            f"{path}:{line_number}: branch must be a non-empty string"
        )

    if not isinstance(changed_files, list):
        raise HistoryFormatError(f"{path}:{line_number}: changed_files must be a list")

    for changed_file in changed_files:
        if not isinstance(changed_file, str) or not changed_file.strip():
            raise HistoryFormatError(
                f"{path}:{line_number}: changed_files must contain non-empty strings"
            )


def _validate_result_record(
    record,
    path,
    line_number,
):
    """
    Validate one results.jsonl record.
    """

    _require_fields(
        record,
        RESULT_REQUIRED_FIELDS,
        path,
        line_number,
    )

    sha = record["sha"]
    test_id = record["test_id"]
    status = record["status"]
    duration_s = record["duration_s"]
    attempt = record["attempt"]

    if not isinstance(sha, str) or not sha.strip():
        raise HistoryFormatError(
            f"{path}:{line_number}: sha must be a non-empty string"
        )

    if not isinstance(test_id, str) or not test_id.strip():
        raise HistoryFormatError(
            f"{path}:{line_number}: test_id must be a non-empty string"
        )

    if status not in ALLOWED_RESULT_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_RESULT_STATUSES))

        raise HistoryFormatError(
            f"{path}:{line_number}: status must be one of: {allowed}"
        )

    if (
        isinstance(duration_s, bool)
        or not isinstance(
            duration_s,
            (int, float),
        )
        or duration_s < 0
    ):
        raise HistoryFormatError(
            f"{path}:{line_number}: duration_s must be a non-negative number"
        )

    if isinstance(attempt, bool) or not isinstance(attempt, int) or attempt < 1:
        raise HistoryFormatError(
            f"{path}:{line_number}: attempt must be a positive integer"
        )


def load_history_records(
    history_dir="history",
):
    """
    Load and validate TestBudget's committed JSONL history.

    Args:
        history_dir:
            Directory containing runs.jsonl and results.jsonl.

    Returns:
        A tuple:
        (runs, results)

    Raises:
        HistoryFormatError:
            For malformed records, duplicate run SHAs, or result records
            that refer to an unknown run SHA.
    """

    history_dir = Path(history_dir)

    runs_path = history_dir / "runs.jsonl"
    results_path = history_dir / "results.jsonl"

    run_rows = _read_jsonl(runs_path)
    result_rows = _read_jsonl(results_path)

    runs = []
    results = []

    known_shas = set()

    for line_number, record in run_rows:
        _validate_run_record(
            record,
            runs_path,
            line_number,
        )

        sha = record["sha"]

        if sha in known_shas:
            raise HistoryFormatError(
                f"{runs_path}:{line_number}: duplicate run sha: {sha}"
            )

        known_shas.add(sha)
        runs.append(record)

    for line_number, record in result_rows:
        _validate_result_record(
            record,
            results_path,
            line_number,
        )

        sha = record["sha"]

        if sha not in known_shas:
            raise HistoryFormatError(
                f"{results_path}:{line_number}: result references unknown sha: {sha}"
            )

        results.append(record)

    return runs, results


def rebuild_history_db(
    history_dir="history",
):
    """
    Rebuild an in-memory SQLite database from committed JSONL history.

    The JSONL files remain the persistent source of truth.
    SQLite is used only as a fast query layer.

    Returns:
        sqlite3.Connection:
            An open in-memory connection containing `runs` and `results`.
    """

    runs, results = load_history_records(history_dir)

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    connection.execute("PRAGMA foreign_keys = ON")

    connection.execute(
        """
        CREATE TABLE runs (
            sha TEXT PRIMARY KEY,
            timestamp TEXT NOT NULL,
            branch TEXT NOT NULL,
            changed_files TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sha TEXT NOT NULL,
            test_id TEXT NOT NULL,
            status TEXT NOT NULL,
            duration_s REAL NOT NULL,
            attempt INTEGER NOT NULL,

            FOREIGN KEY (sha)
                REFERENCES runs(sha)
                ON DELETE CASCADE
        )
        """
    )

    for run in runs:
        connection.execute(
            """
            INSERT INTO runs (
                sha,
                timestamp,
                branch,
                changed_files
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                run["sha"],
                run["timestamp"],
                run["branch"],
                json.dumps(
                    run["changed_files"],
                    separators=(",", ":"),
                ),
            ),
        )

    for result in results:
        connection.execute(
            """
            INSERT INTO results (
                sha,
                test_id,
                status,
                duration_s,
                attempt
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                result["sha"],
                result["test_id"],
                result["status"],
                float(result["duration_s"]),
                int(result["attempt"]),
            ),
        )

    connection.commit()

    return connection


def get_history_test_stats(
    history_dir="history",
):
    """
    Calculate per-test statistics from committed JSONL history.

    Returns:
        A list of dictionaries containing:
        test_id, run_count, failure_count, avg_duration, and last_seen.
    """

    connection = rebuild_history_db(history_dir)

    rows = connection.execute(
        """
        SELECT
            results.test_id AS test_id,

            COUNT(*) AS run_count,

            SUM(
                CASE
                    WHEN results.status = 'failed'
                    THEN 1
                    ELSE 0
                END
            ) AS failure_count,

            AVG(results.duration_s) AS avg_duration,

            MAX(runs.timestamp) AS last_seen

        FROM results

        JOIN runs
            ON runs.sha = results.sha

        GROUP BY results.test_id

        ORDER BY results.test_id
        """
    ).fetchall()

    connection.close()

    stats = []

    for row in rows:
        stats.append(
            {
                "test_id": row["test_id"],
                "run_count": row["run_count"],
                "failure_count": row["failure_count"],
                "avg_duration": round(
                    row["avg_duration"],
                    3,
                ),
                "last_seen": row["last_seen"],
            }
        )

    return stats
