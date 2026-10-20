import sqlite3


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
