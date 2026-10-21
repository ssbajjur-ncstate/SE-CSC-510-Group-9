# TestBudget History

TestBudget stores CI history as append-only JSONL files committed to the
repository.

The JSONL files are the persistent source of truth. SQLite is rebuilt from
those files when TestBudget needs to query historical data.

## Why JSONL?

The original TestBudget prototype stored history in a local SQLite database.

That worked for the first vertical slice, but a local database is difficult
to review, merge, reproduce, and share through Git.

The JSONL format makes history:

- visible in Git;
- append-only;
- reproducible from a clean clone;
- usable by replay and calibration;
- mergeable across development branches.

## Run history

`history/runs.jsonl` contains one JSON object per recorded CI run.

Example:

```json
{
  "sha": "abc123",
  "timestamp": "2026-10-21T12:00:00Z",
  "branch": "main",
  "changed_files": [
    "src/cart.py",
    "src/payment.py"
  ]
}


Fields:
- sha: Git commit SHA for the run.
- timestamp: timestamp for the run.
- branch: branch associated with the run.
- changed_files: files changed by the commit or pull request.
A SHA may appear only once in runs.jsonl.
Test result history
history/results.jsonl contains one JSON object per test attempt.
Example:
{
  "sha": "abc123",
  "test_id": "tests/test_cart.py::test_add_item",
  "status": "passed",
  "duration_s": 1.25,
  "attempt": 1
}

Fields:
- sha: run SHA that owns this result.
- test_id: stable TestBudget test identity.
- status: passed, failed, or skipped.
- duration_s: execution time in seconds.
- attempt: retry attempt number beginning at 1.
A result must reference a SHA present in runs.jsonl.
Rebuilding SQLite
Applications should not treat a .db file as persistent history.
Load the committed history using:
from testbudget.db import rebuild_history_dbconnection = rebuild_history_db("history")


The returned SQLite connection contains:
- runs
- results
For example:
rows = connection.execute(    "SELECT test_id, status FROM results").fetchall()


The database exists only as the query layer. The JSONL files remain the
source of truth.
Historical test statistics
Per-test statistics can be obtained with:
from testbudget.db import get_history_test_statsstats = get_history_test_stats("history")



